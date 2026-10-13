"""
Reproducible synthetic data generator for the AI-Based Production Planning and
Scheduling System.

IMPORTANT: This generator only runs when the target CSVs do not already exist,
unless --force is passed. It will NEVER silently overwrite real operational
data. All generated rows are clearly labelled synthetic in
backend/data/SYNTHETIC_DATA_NOTICE.txt.

Usage:
    python generate_synthetic_data.py [--force] [--seed 42]
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import DATA_DIR, FILES, SYNTHETIC_DATA_LABEL  # noqa: E402

RNG_SEED_DEFAULT = 42
HISTORY_DAYS = 180
TODAY = date.today()
HISTORY_START = TODAY - timedelta(days=HISTORY_DAYS)

PRODUCTS = [
    ("P001", "Steel Bracket A", "Metal Parts", "unit", 4.50, 3, 2),
    ("P002", "Steel Bracket B", "Metal Parts", "unit", 5.20, 3, 2),
    ("P003", "Plastic Housing X", "Plastics", "unit", 2.80, 4, 1),
    ("P004", "Plastic Housing Y", "Plastics", "unit", 3.10, 4, 1),
    ("P005", "Aluminum Panel", "Metal Parts", "unit", 7.90, 5, 3),
    ("P006", "Circuit Enclosure", "Electronics", "unit", 12.40, 5, 3),
]

MACHINES = [
    ("M01", "CNC Mill 1", "milling", 60, 480, 1080, 25.0),
    ("M02", "CNC Mill 2", "milling", 60, 480, 1080, 25.0),
    ("M03", "Injection Molder 1", "molding", 90, 480, 1080, 18.0),
    ("M04", "Injection Molder 2", "molding", 90, 480, 1080, 18.0),
    ("M05", "Assembly Line 1", "assembly", 40, 480, 1080, 15.0),
]

# product_id -> list of (machine_id, minutes_per_unit, setup_minutes)
PROCESSING = {
    "P001": [("M01", 4.0, 20), ("M02", 4.2, 20)],
    "P002": [("M01", 5.0, 25), ("M02", 5.1, 25)],
    "P003": [("M03", 2.5, 30), ("M04", 2.6, 30)],
    "P004": [("M03", 2.8, 30), ("M04", 2.9, 30)],
    "P005": [("M01", 6.0, 25), ("M02", 6.2, 25), ("M05", 3.0, 15)],
    "P006": [("M05", 5.5, 20)],
}

MATERIALS = [
    ("RM01", "Steel Sheet", "kg", 5000),
    ("RM02", "ABS Resin", "kg", 4000),
    ("RM03", "Aluminum Sheet", "kg", 2000),
    ("RM04", "Electronic Components Kit", "unit", 1500),
]

BOM = {
    "P001": [("RM01", 1.2)],
    "P002": [("RM01", 1.5)],
    "P003": [("RM02", 0.8)],
    "P004": [("RM02", 0.9)],
    "P005": [("RM03", 1.0)],
    "P006": [("RM04", 1.0), ("RM02", 0.3)],
}


def gen_historical_demand(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    dates = [HISTORY_START + timedelta(days=i) for i in range(HISTORY_DAYS)]
    base_levels = {"P001": 40, "P002": 30, "P003": 55, "P004": 35, "P005": 20, "P006": 15}
    trend_per_day = {"P001": 0.03, "P002": 0.01, "P003": 0.05, "P004": -0.01, "P005": 0.02, "P006": 0.015}
    for pid, base in base_levels.items():
        for i, d in enumerate(dates):
            dow = d.weekday()
            weekend_factor = 0.4 if dow >= 5 else 1.0
            seasonal = 1.0 + 0.15 * np.sin(2 * np.pi * i / 28.0)
            trend = 1.0 + trend_per_day[pid] * i / 10.0
            noise = rng.normal(0, 0.12)
            qty = max(0, base * weekend_factor * seasonal * trend * (1 + noise))
            rows.append({"date": d.isoformat(), "product_id": pid, "demand_qty": round(qty)})
    return pd.DataFrame(rows)


def gen_products() -> pd.DataFrame:
    return pd.DataFrame(PRODUCTS, columns=[
        "product_id", "product_name", "category", "unit", "unit_cost",
        "safety_stock_days", "lead_time_days",
    ])


def gen_machines() -> pd.DataFrame:
    return pd.DataFrame(MACHINES, columns=[
        "machine_id", "machine_name", "machine_type", "capacity_units_per_hour",
        "shift_start_min", "shift_end_min", "cost_per_hour",
    ])


def gen_processing_times() -> pd.DataFrame:
    rows = []
    for pid, options in PROCESSING.items():
        for mid, mpu, setup in options:
            rows.append({
                "product_id": pid, "machine_id": mid,
                "processing_minutes_per_unit": mpu, "setup_minutes": setup,
            })
    return pd.DataFrame(rows)


def gen_inventory(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for pid, *_ in PRODUCTS:
        on_hand = int(rng.integers(50, 400))
        rows.append({"product_id": pid, "on_hand_qty": on_hand, "as_of_date": TODAY.isoformat()})
    return pd.DataFrame(rows)


def gen_raw_materials() -> pd.DataFrame:
    return pd.DataFrame(MATERIALS, columns=["material_id", "material_name", "unit", "on_hand_qty"])


def gen_bom() -> pd.DataFrame:
    rows = []
    for pid, mats in BOM.items():
        for mid, qty in mats:
            rows.append({"product_id": pid, "material_id": mid, "qty_per_unit": qty})
    return pd.DataFrame(rows)


def gen_orders(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    order_num = 1
    for pid, *_ in PRODUCTS:
        n_orders = int(rng.integers(3, 7))
        for _ in range(n_orders):
            order_date = TODAY - timedelta(days=int(rng.integers(0, 5)))
            lead = int(rng.integers(3, 12))
            due_date = order_date + timedelta(days=lead)
            qty = int(rng.integers(20, 150))
            priority = rng.choice(["high", "medium", "low"], p=[0.2, 0.5, 0.3])
            status = rng.choice(["confirmed", "confirmed", "pending"])
            rows.append({
                "order_id": f"ORD{order_num:04d}",
                "product_id": pid,
                "quantity": qty,
                "order_date": order_date.isoformat(),
                "due_date": due_date.isoformat(),
                "priority": priority,
                "status": status,
                "locked": False,
                "committed_machine_id": "",
                "committed_start_min": "",
                "committed_end_min": "",
            })
            order_num += 1
    return pd.DataFrame(rows)


def gen_machine_status(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for mid, *_ in MACHINES:
        if rng.random() < 0.4:
            start_day = int(rng.integers(1, 10))
            duration_h = int(rng.integers(2, 8))
            rows.append({
                "machine_id": mid,
                "status": "maintenance",
                "status_start": (TODAY + timedelta(days=start_day)).isoformat() + "T08:00:00",
                "status_end": (TODAY + timedelta(days=start_day)).isoformat() + f"T{8+duration_h:02d}:00:00",
                "reason": "Scheduled preventive maintenance (synthetic)",
            })
    if not rows:
        rows.append({
            "machine_id": MACHINES[0][0], "status": "available",
            "status_start": "", "status_end": "", "reason": "",
        })
    return pd.DataFrame(rows)


def gen_production_history(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for i in range(30):
        d = TODAY - timedelta(days=30 - i)
        for pid, *_ in PRODUCTS:
            if rng.random() < 0.6:
                mid = rng.choice([m[0] for m in MACHINES if PROCESSING.get(pid) and
                                   m[0] in [p[0] for p in PROCESSING[pid]]])
                qty = int(rng.integers(10, 80))
                rows.append({
                    "date": d.isoformat(), "product_id": pid, "machine_id": mid,
                    "quantity_produced": qty,
                    "start_time": d.isoformat() + "T08:00:00",
                    "end_time": d.isoformat() + "T16:00:00",
                })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing CSVs")
    parser.add_argument("--seed", type=int, default=RNG_SEED_DEFAULT)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    generators = {
        "products": gen_products,
        "machines": gen_machines,
        "processing_times": gen_processing_times,
        "historical_demand": lambda: gen_historical_demand(rng),
        "inventory": lambda: gen_inventory(rng),
        "raw_materials": gen_raw_materials,
        "bill_of_materials": gen_bom,
        "orders": lambda: gen_orders(rng),
        "machine_status": lambda: gen_machine_status(rng),
        "production_history": lambda: gen_production_history(rng),
    }

    created, skipped = [], []
    for name, gen_fn in generators.items():
        path = FILES[name]
        if path.exists() and not args.force:
            skipped.append(str(path))
            continue
        df = gen_fn()
        df.to_csv(path, index=False)
        created.append(str(path))

    notice_path = DATA_DIR / "SYNTHETIC_DATA_NOTICE.txt"
    notice_path.write_text(
        f"{SYNTHETIC_DATA_LABEL} DATA\n"
        f"All CSV files in this directory were generated by "
        f"backend/scripts/generate_synthetic_data.py (seed={args.seed}).\n"
        f"They do not represent any real factory, product, or customer.\n"
        f"Generated/refreshed on: {date.today().isoformat()}\n",
        encoding="utf-8",
    )

    print(f"Created ({len(created)}):")
    for p in created:
        print(f"  {p}")
    print(f"Skipped, already exist ({len(skipped)}):")
    for p in skipped:
        print(f"  {p}")


if __name__ == "__main__":
    main()
