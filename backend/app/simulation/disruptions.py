"""
Module D: disruption-management primitives.

Each function takes the relevant DataFrame(s) and returns a NEW, modified
copy plus a human-readable description — the originals (and therefore the
CSV source-of-truth files) are never mutated by a simulation run. Only an
explicit "commit" action (not implemented as a disruption) would persist
changes back to CSV.

No predictive-maintenance / failure-prediction model is included here.
Per project requirements, we do not fabricate a machine-failure classifier
from arbitrary synthetic labels — breakdowns are user-simulated events, not
model predictions.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pandas as pd


def simulate_machine_breakdown(
    machine_status_df: pd.DataFrame, machine_id: str, start_dt: datetime, duration_hours: float, reason: str = ""
) -> Tuple[pd.DataFrame, str]:
    end_dt = start_dt + timedelta(hours=duration_hours)
    new_row = {
        "machine_id": machine_id, "status": "breakdown",
        "status_start": start_dt.isoformat(), "status_end": end_dt.isoformat(),
        "reason": reason or "Simulated breakdown",
    }
    df = pd.concat([machine_status_df, pd.DataFrame([new_row])], ignore_index=True)
    desc = f"Machine {machine_id} breaks down from {start_dt.isoformat()} to {end_dt.isoformat()} ({reason or 'unspecified cause'})."
    return df, desc


def simulate_machine_restored(machine_status_df: pd.DataFrame, machine_id: str, as_of: datetime) -> Tuple[pd.DataFrame, str]:
    df = machine_status_df.copy()
    mask = (df["machine_id"] == machine_id) & (df["status"].isin(["breakdown", "down", "maintenance"]))
    # Close out any open/future downtime window for this machine as of `as_of`.
    for idx in df[mask].index:
        try:
            end_dt = pd.to_datetime(df.loc[idx, "status_end"])
        except Exception:
            end_dt = as_of
        if pd.isna(end_dt) or end_dt > as_of:
            df.loc[idx, "status_end"] = as_of.isoformat()
    desc = f"Machine {machine_id} returns to service at {as_of.isoformat()}."
    return df, desc


def simulate_material_shortage(
    raw_materials_df: pd.DataFrame, material_id: str, reduce_by_qty: float
) -> Tuple[pd.DataFrame, str]:
    df = raw_materials_df.copy()
    idx = df.index[df["material_id"] == material_id]
    if len(idx) == 0:
        return df, f"Material {material_id} not found; no change applied."
    before = float(df.loc[idx[0], "on_hand_qty"])
    after = max(0.0, before - reduce_by_qty)
    df.loc[idx[0], "on_hand_qty"] = after
    desc = f"Material {material_id} stock reduced from {before:.1f} to {after:.1f} units (shortage of {reduce_by_qty:.1f})."
    return df, desc


def simulate_new_urgent_order(
    orders_df: pd.DataFrame, product_id: str, quantity: float, due_date, priority: str = "high"
) -> Tuple[pd.DataFrame, str]:
    df = orders_df.copy()
    next_num = len(df) + 1
    while f"ORD-URG-{next_num:04d}" in set(df["order_id"]):
        next_num += 1
    order_id = f"ORD-URG-{next_num:04d}"
    new_row = {
        "order_id": order_id, "product_id": product_id, "quantity": quantity,
        "order_date": datetime.utcnow().date(), "due_date": due_date,
        "priority": priority, "status": "confirmed", "locked": False,
        "committed_machine_id": "", "committed_start_min": "", "committed_end_min": "",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    desc = f"New urgent order {order_id} for {quantity:.0f} units of {product_id}, due {due_date}."
    return df, desc


def simulate_order_change(
    orders_df: pd.DataFrame, order_id: str, new_quantity: Optional[float] = None, new_due_date=None
) -> Tuple[pd.DataFrame, str]:
    df = orders_df.copy()
    idx = df.index[df["order_id"] == order_id]
    if len(idx) == 0:
        return df, f"Order {order_id} not found; no change applied."
    changes = []
    if new_quantity is not None:
        old = df.loc[idx[0], "quantity"]
        df.loc[idx[0], "quantity"] = new_quantity
        changes.append(f"quantity {old} -> {new_quantity}")
    if new_due_date is not None:
        old = df.loc[idx[0], "due_date"]
        df.loc[idx[0], "due_date"] = new_due_date
        changes.append(f"due date {old} -> {new_due_date}")
    desc = f"Order {order_id} updated: {', '.join(changes) if changes else 'no fields changed'}."
    return df, desc


def simulate_processing_time_change(
    processing_times_df: pd.DataFrame, product_id: str, machine_id: str,
    new_minutes_per_unit: Optional[float] = None, new_setup_minutes: Optional[float] = None,
) -> Tuple[pd.DataFrame, str]:
    df = processing_times_df.copy()
    idx = df.index[(df["product_id"] == product_id) & (df["machine_id"] == machine_id)]
    if len(idx) == 0:
        return df, f"No processing-time record for {product_id} on {machine_id}; no change applied."
    changes = []
    if new_minutes_per_unit is not None:
        old = df.loc[idx[0], "processing_minutes_per_unit"]
        df.loc[idx[0], "processing_minutes_per_unit"] = new_minutes_per_unit
        changes.append(f"minutes/unit {old} -> {new_minutes_per_unit}")
    if new_setup_minutes is not None:
        old = df.loc[idx[0], "setup_minutes"]
        df.loc[idx[0], "setup_minutes"] = new_setup_minutes
        changes.append(f"setup minutes {old} -> {new_setup_minutes}")
    desc = f"Processing time for {product_id} on {machine_id} updated: {', '.join(changes) if changes else 'no change'}."
    return df, desc
