"""
Data access layer. Loads the CSV source-of-truth files into validated
pandas DataFrames. CSV remains the source of truth; SQLite (db.py) is used
only for operational records that mutate at runtime (schedules, audit log,
disruption events) so the originals are never silently overwritten.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import FILES


class DataValidationError(ValueError):
    pass


REQUIRED_COLUMNS = {
    "products": ["product_id", "product_name", "category", "unit", "unit_cost",
                 "safety_stock_days", "lead_time_days"],
    "machines": ["machine_id", "machine_name", "machine_type", "capacity_units_per_hour",
                 "shift_start_min", "shift_end_min", "cost_per_hour"],
    "processing_times": ["product_id", "machine_id", "processing_minutes_per_unit", "setup_minutes"],
    "historical_demand": ["date", "product_id", "demand_qty"],
    "inventory": ["product_id", "on_hand_qty", "as_of_date"],
    "raw_materials": ["material_id", "material_name", "unit", "on_hand_qty"],
    "bill_of_materials": ["product_id", "material_id", "qty_per_unit"],
    "orders": ["order_id", "product_id", "quantity", "order_date", "due_date",
               "priority", "status"],
    "machine_status": ["machine_id", "status", "status_start", "status_end", "reason"],
    "production_history": ["date", "product_id", "machine_id", "quantity_produced",
                            "start_time", "end_time"],
}


def _validate(df: pd.DataFrame, name: str) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    if missing:
        raise DataValidationError(f"{name}.csv missing required columns: {missing}")
    return df


def _read_csv(name: str) -> pd.DataFrame:
    path: Path = FILES[name]
    if not path.exists():
        raise DataValidationError(
            f"Required data file not found: {path}. Run "
            f"backend/scripts/generate_synthetic_data.py to create synthetic data, "
            f"or supply real CSVs at this location."
        )
    df = pd.read_csv(path)
    return _validate(df, name)


def load_products() -> pd.DataFrame:
    df = _read_csv("products")
    dup = df[df.duplicated("product_id", keep=False)]
    if not dup.empty:
        raise DataValidationError(f"Duplicate product_id values: {dup['product_id'].tolist()}")
    return df


def load_machines() -> pd.DataFrame:
    df = _read_csv("machines")
    dup = df[df.duplicated("machine_id", keep=False)]
    if not dup.empty:
        raise DataValidationError(f"Duplicate machine_id values: {dup['machine_id'].tolist()}")
    return df


def load_processing_times() -> pd.DataFrame:
    df = _read_csv("processing_times")
    products = set(load_products()["product_id"])
    machines = set(load_machines()["machine_id"])
    bad_products = set(df["product_id"]) - products
    bad_machines = set(df["machine_id"]) - machines
    if bad_products:
        raise DataValidationError(f"processing_times references unknown product_id(s): {bad_products}")
    if bad_machines:
        raise DataValidationError(f"processing_times references unknown machine_id(s): {bad_machines}")
    return df


def load_historical_demand() -> pd.DataFrame:
    df = _read_csv("historical_demand")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values(["product_id", "date"]).reset_index(drop=True)
    if df["demand_qty"].lt(0).any():
        raise DataValidationError("historical_demand contains negative demand_qty values")
    before = len(df)
    df = df.drop_duplicates(subset=["product_id", "date"], keep="last")
    if len(df) < before:
        pass  # duplicates collapsed silently is acceptable for history; logged via caller if needed
    return df


def load_inventory() -> pd.DataFrame:
    return _read_csv("inventory")


def load_raw_materials() -> pd.DataFrame:
    return _read_csv("raw_materials")


def load_bom() -> pd.DataFrame:
    df = _read_csv("bill_of_materials")
    materials = set(load_raw_materials()["material_id"])
    bad = set(df["material_id"]) - materials
    if bad:
        raise DataValidationError(f"bill_of_materials references unknown material_id(s): {bad}")
    return df


def load_orders() -> pd.DataFrame:
    df = _read_csv("orders")
    products = set(load_products()["product_id"])
    bad = set(df["product_id"]) - products
    if bad:
        raise DataValidationError(f"orders references unknown product_id(s): {bad}")
    df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
    df["due_date"] = pd.to_datetime(df["due_date"]).dt.date
    if "locked" not in df.columns:
        df["locked"] = False
    df["locked"] = df["locked"].fillna(False).astype(bool)
    return df


def load_machine_status() -> pd.DataFrame:
    return _read_csv("machine_status")


def load_production_history() -> pd.DataFrame:
    df = _read_csv("production_history")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def data_health_summary() -> dict:
    """Used by /api/health to confirm the data layer is loadable."""
    summary = {}
    loaders = {
        "products": load_products, "machines": load_machines,
        "processing_times": load_processing_times, "historical_demand": load_historical_demand,
        "inventory": load_inventory, "raw_materials": load_raw_materials,
        "bill_of_materials": load_bom, "orders": load_orders,
        "machine_status": load_machine_status, "production_history": load_production_history,
    }
    for name, fn in loaders.items():
        try:
            df = fn()
            summary[name] = {"ok": True, "rows": len(df)}
        except DataValidationError as e:
            summary[name] = {"ok": False, "error": str(e)}
    return summary
