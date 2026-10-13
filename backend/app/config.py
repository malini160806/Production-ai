"""
Central configuration for file paths, time conventions, and scheduling defaults.

Time convention: all dates in CSV data are calendar dates (no timezone).
All intra-day timestamps (shift start/end, schedule start/finish) are stored
and computed as MINUTES SINCE THE START OF THE PLANNING HORIZON (local factory
time, no DST). This avoids tz ambiguity in the solver while remaining human
readable via `minutes_to_datetime` / `datetime_to_minutes` helpers.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models_store"
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "operational.db")))

MODELS_DIR.mkdir(exist_ok=True, parents=True)
DATA_DIR.mkdir(exist_ok=True, parents=True)
DB_PATH.parent.mkdir(exist_ok=True, parents=True)

# ---- Data file names (source of truth CSVs) ----
FILES = {
    "historical_demand": DATA_DIR / "historical_demand.csv",
    "orders": DATA_DIR / "orders.csv",
    "machines": DATA_DIR / "machines.csv",
    "processing_times": DATA_DIR / "processing_times.csv",
    "products": DATA_DIR / "products.csv",
    "inventory": DATA_DIR / "inventory.csv",
    "bill_of_materials": DATA_DIR / "bill_of_materials.csv",
    "raw_materials": DATA_DIR / "raw_materials.csv",
    "machine_status": DATA_DIR / "machine_status.csv",
    "production_history": DATA_DIR / "production_history.csv",
}

# ---- Forecasting defaults ----
LAG_DAYS = [1, 7, 14, 28]
ROLLING_WINDOWS = [7, 14, 28]
MIN_HISTORY_DAYS = 35  # minimum days of history required to train a per-product model
DEFAULT_FORECAST_HORIZON = 14

# ---- Scheduling defaults ----
SHIFT_START_MIN = 8 * 60       # 08:00 in minutes-from-midnight
SHIFT_END_MIN = 18 * 60        # 18:00
BREAK_START_MIN = 12 * 60      # 12:00 lunch break
BREAK_END_MIN = 12 * 60 + 30   # 12:30
WORK_MINUTES_PER_DAY = (SHIFT_END_MIN - SHIFT_START_MIN) - (BREAK_END_MIN - BREAK_START_MIN)
PLANNING_HORIZON_DAYS = 14
SOLVER_TIME_LIMIT_SECONDS = 10

DEFAULT_OBJECTIVE_WEIGHTS = {
    "weighted_tardiness": 10.0,
    "num_late_orders": 50.0,
    "makespan": 1.0,
    "idle_time": 0.5,
    "setup_cost": 0.0,
    "production_cost": 0.0,
}

SYNTHETIC_DATA_LABEL = "SYNTHETIC"
