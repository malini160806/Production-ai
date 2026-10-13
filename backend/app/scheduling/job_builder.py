"""
Builds JobSpec objects (the scheduler's input) from the raw CSV-backed
DataFrames: orders, processing_times, machines, bill_of_materials,
raw_materials, products.

Material-readiness assumption (documented): raw material stock is a shared
pool allocated to orders in due-date order. If an order's required material
exceeds what remains after earlier-due orders have claimed stock, the order
is marked with a "material shortage" and its ready time is pushed out by
the product's configured `lead_time_days` (used as a proxy for
replenishment lead time) rather than silently scheduling it on insufficient
stock.
"""
from datetime import date as date_cls
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .calendar_utils import WorkTimeMapping
from .cp_sat_scheduler import JobSpec, MachineOption

PRIORITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}


def compute_material_readiness(
    orders_df: pd.DataFrame, bom_df: pd.DataFrame, raw_materials_df: pd.DataFrame, products_df: pd.DataFrame
) -> Dict[str, dict]:
    remaining = dict(zip(raw_materials_df["material_id"], raw_materials_df["on_hand_qty"].astype(float)))
    lead_time_by_product = dict(zip(products_df["product_id"], products_df["lead_time_days"].astype(float)))

    result: Dict[str, dict] = {}
    for _, order in orders_df.sort_values("due_date").iterrows():
        pid = order["product_id"]
        reqs = bom_df[bom_df["product_id"] == pid]
        shortage = False
        detail = []
        for _, r in reqs.iterrows():
            mat_id = r["material_id"]
            qty_needed = float(r["qty_per_unit"]) * float(order["quantity"])
            available = remaining.get(mat_id, 0.0)
            if qty_needed <= available:
                remaining[mat_id] = available - qty_needed
            else:
                shortage = True
                detail.append(f"{mat_id} short by {qty_needed - available:.1f} units")
                remaining[mat_id] = 0.0
        lead_days = lead_time_by_product.get(pid, 3.0)
        result[order["order_id"]] = {
            "ready_minute": int(lead_days * 1440) if shortage else 0,
            "shortage": shortage,
            "detail": "; ".join(detail),
        }
    return result


def _parse_optional_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return None
    return s


def _parse_optional_int(value) -> int | None:
    s = _parse_optional_str(value)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def build_jobs(
    orders_df: pd.DataFrame,
    processing_times_df: pd.DataFrame,
    machines_df: pd.DataFrame,
    bom_df: pd.DataFrame,
    raw_materials_df: pd.DataFrame,
    products_df: pd.DataFrame,
    horizon_start: date_cls,
    horizon_days: int,
    work_time_mapping: WorkTimeMapping,
) -> Tuple[List[JobSpec], Dict[str, dict]]:
    """
    `work_time_mapping` converts calendar minutes (shift/break-aware) to the
    compressed working-minute axis used by the solver — see calendar_utils.
    Ready times and due dates are converted through it so a job's deadline
    and material-readiness time are expressed in the same units as job
    durations (working minutes), which may legitimately span multiple
    shifts/days.
    """
    material_info = compute_material_readiness(orders_df, bom_df, raw_materials_df, products_df)
    known_machine_ids = set(machines_df["machine_id"])

    jobs: List[JobSpec] = []
    for _, order in orders_df.iterrows():
        due_days = (order["due_date"] - horizon_start).days
        due_calendar_minute = max(0, due_days * 1440 + 1440)
        due_minute = work_time_mapping.calendar_to_work(due_calendar_minute)

        priority = str(order.get("priority", "medium")).lower()
        weight = PRIORITY_WEIGHTS.get(priority, 1)

        options: List[MachineOption] = []
        prod_times = processing_times_df[processing_times_df["product_id"] == order["product_id"]]
        for _, pt in prod_times.iterrows():
            m_id = pt["machine_id"]
            if m_id not in known_machine_ids:
                continue
            cost = float(machines_df.loc[machines_df["machine_id"] == m_id, "cost_per_hour"].iloc[0])
            duration = float(pt["setup_minutes"]) + float(pt["processing_minutes_per_unit"]) * float(order["quantity"])
            options.append(MachineOption(m_id, duration, int(pt["setup_minutes"]), cost))

        no_option_reason = None
        if not options:
            no_option_reason = f"No machine is configured to process product '{order['product_id']}'."

        mat = material_info.get(order["order_id"], {"ready_minute": 0, "shortage": False, "detail": ""})
        ready_minute = work_time_mapping.calendar_to_work(int(mat["ready_minute"]))

        committed_machine_id = _parse_optional_str(order.get("committed_machine_id"))
        committed_start_calendar = _parse_optional_int(order.get("committed_start_min"))
        committed_start_minute = (
            work_time_mapping.calendar_to_work(committed_start_calendar)
            if committed_start_calendar is not None else None
        )
        is_locked = bool(order.get("locked", False)) and committed_machine_id is not None and committed_start_minute is not None

        jobs.append(JobSpec(
            order_id=order["order_id"],
            product_id=order["product_id"],
            quantity=float(order["quantity"]),
            due_minute=int(due_minute),
            priority_weight=weight,
            ready_minute=int(ready_minute),
            locked=is_locked,
            committed_machine_id=committed_machine_id if is_locked else None,
            committed_start_minute=committed_start_minute if is_locked else None,
            options=options,
            no_option_reason=no_option_reason,
        ))

    return jobs, material_info
