import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.config import FILES
from app import data_access as da


@pytest.fixture(scope="session", autouse=True)
def ensure_synthetic_data():
    """Generate synthetic data once for the test session if it doesn't already exist."""
    if not FILES["products"].exists():
        from scripts.generate_synthetic_data import main
        import sys as _sys
        old_argv = _sys.argv
        _sys.argv = ["generate_synthetic_data.py"]
        try:
            main()
        finally:
            _sys.argv = old_argv
    yield


@pytest.fixture()
def all_data():
    return {
        "orders": da.load_orders(),
        "machines": da.load_machines(),
        "processing_times": da.load_processing_times(),
        "machine_status": da.load_machine_status(),
        "bill_of_materials": da.load_bom(),
        "raw_materials": da.load_raw_materials(),
        "products": da.load_products(),
        "historical_demand": da.load_historical_demand(),
        "inventory": da.load_inventory(),
    }
