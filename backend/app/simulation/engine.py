"""
Module D orchestration: apply one disruption to an in-memory snapshot of the
operational data, recompute the schedule, and diff it against the schedule
computed just before the disruption — all within a single request so the
comparison is always apples-to-apples for the same baseline.
"""
from datetime import datetime
from typing import Optional

from ..scheduling.cp_sat_scheduler import ScheduleResult
from ..scheduling.runner import run_optimized_schedule
from . import disruptions as D


class UnknownDisruptionType(ValueError):
    pass


def apply_disruption(disruption_type: str, params: dict, data: dict) -> tuple[dict, str]:
    """
    data: dict with keys orders, machines, processing_times, machine_status,
    bill_of_materials, raw_materials, products (DataFrames). Returns a NEW
    data dict (shallow copy with the relevant frame replaced) and a
    description string.
    """
    data = dict(data)  # shallow copy of the mapping; individual frames copied by each simulate_* fn

    if disruption_type == "machine_breakdown":
        start_dt = datetime.fromisoformat(params["start_datetime"])
        df, desc = D.simulate_machine_breakdown(
            data["machine_status"], params["machine_id"], start_dt,
            float(params.get("duration_hours", 4)), params.get("reason", ""),
        )
        data["machine_status"] = df

    elif disruption_type == "machine_restored":
        as_of = datetime.fromisoformat(params["as_of_datetime"]) if params.get("as_of_datetime") else datetime.utcnow()
        df, desc = D.simulate_machine_restored(data["machine_status"], params["machine_id"], as_of)
        data["machine_status"] = df

    elif disruption_type == "material_shortage":
        df, desc = D.simulate_material_shortage(
            data["raw_materials"], params["material_id"], float(params["reduce_by_qty"])
        )
        data["raw_materials"] = df

    elif disruption_type == "new_urgent_order":
        import pandas as pd
        due_date = pd.to_datetime(params["due_date"]).date()
        df, desc = D.simulate_new_urgent_order(
            data["orders"], params["product_id"], float(params["quantity"]), due_date,
            params.get("priority", "high"),
        )
        data["orders"] = df

    elif disruption_type == "order_change":
        import pandas as pd
        new_due = pd.to_datetime(params["new_due_date"]).date() if params.get("new_due_date") else None
        df, desc = D.simulate_order_change(
            data["orders"], params["order_id"], params.get("new_quantity"), new_due,
        )
        data["orders"] = df

    elif disruption_type == "processing_time_change":
        df, desc = D.simulate_processing_time_change(
            data["processing_times"], params["product_id"], params["machine_id"],
            params.get("new_minutes_per_unit"), params.get("new_setup_minutes"),
        )
        data["processing_times"] = df

    else:
        raise UnknownDisruptionType(f"Unknown disruption_type '{disruption_type}'")

    return data, desc


def run_simulation(
    disruption_type: str, params: dict, data: dict, horizon_start, horizon_days: int,
    objective_weights: Optional[dict] = None, time_limit_seconds: int = 8,
) -> dict:
    before_result, _, _ = run_optimized_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start, horizon_days,
        objective_weights, time_limit_seconds,
    )

    new_data, description = apply_disruption(disruption_type, params, data)

    after_result, material_info, _ = run_optimized_schedule(
        new_data["orders"], new_data["machines"], new_data["processing_times"], new_data["machine_status"],
        new_data["bill_of_materials"], new_data["raw_materials"], new_data["products"], horizon_start, horizon_days,
        objective_weights, time_limit_seconds,
    )

    before_by_order = {s.order_id: s for s in before_result.scheduled}
    after_by_order = {s.order_id: s for s in after_result.scheduled}
    after_unscheduled_ids = {u.order_id for u in after_result.unscheduled}

    changed, newly_unscheduled, newly_late, unchanged_count = [], [], [], 0
    all_order_ids = set(before_by_order) | set(after_by_order) | after_unscheduled_ids
    for oid in all_order_ids:
        before = before_by_order.get(oid)
        after = after_by_order.get(oid)
        if after is None and before is not None:
            newly_unscheduled.append({
                "order_id": oid, "product_id": before.product_id,
                "reason": next((u.reason for u in after_result.unscheduled if u.order_id == oid), "No longer schedulable."),
            })
            continue
        if before is None and after is not None:
            changed.append({
                "order_id": oid, "change": "newly_scheduled",
                "new_machine": after.machine_id, "new_start_minute": after.start_minute,
                "new_end_minute": after.end_minute, "on_time": after.on_time,
            })
            continue
        if before and after:
            if before.machine_id != after.machine_id or before.start_minute != after.start_minute:
                changed.append({
                    "order_id": oid, "change": "rescheduled",
                    "old_machine": before.machine_id, "old_start_minute": before.start_minute,
                    "new_machine": after.machine_id, "new_start_minute": after.start_minute,
                    "old_on_time": before.on_time, "new_on_time": after.on_time,
                })
                if before.on_time and not after.on_time:
                    newly_late.append({"order_id": oid, "delay_minutes": after.delay_minutes})
            else:
                unchanged_count += 1

    return {
        "disruption_type": disruption_type,
        "description": description,
        "before": {
            "status": before_result.status,
            "num_scheduled": len(before_result.scheduled),
            "num_unscheduled": len(before_result.unscheduled),
            "total_tardiness_minutes": before_result.total_tardiness_minutes,
            "makespan_minutes": before_result.makespan_minutes,
        },
        "after": {
            "status": after_result.status,
            "num_scheduled": len(after_result.scheduled),
            "num_unscheduled": len(after_result.unscheduled),
            "total_tardiness_minutes": after_result.total_tardiness_minutes,
            "makespan_minutes": after_result.makespan_minutes,
            "scheduled": [s.__dict__ for s in after_result.scheduled],
            "unscheduled": [u.__dict__ for u in after_result.unscheduled],
        },
        "diff": {
            "unchanged_count": unchanged_count,
            "changed_orders": changed,
            "newly_unscheduled": newly_unscheduled,
            "deadlines_at_risk": newly_late,
        },
    }
