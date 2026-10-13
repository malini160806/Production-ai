import pandas as pd
import pytest

from app import data_access as da
from app.data_access import DataValidationError


def test_all_sources_load(all_data):
    for name, df in all_data.items():
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, f"{name} loaded but is empty"


def test_no_duplicate_product_ids():
    df = da.load_products()
    assert df["product_id"].is_unique


def test_no_duplicate_machine_ids():
    df = da.load_machines()
    assert df["machine_id"].is_unique


def test_orders_reference_known_products(all_data):
    orders = all_data["orders"]
    products = set(all_data["products"]["product_id"])
    assert set(orders["product_id"]).issubset(products)


def test_processing_times_reference_known_machines_and_products(all_data):
    pt = all_data["processing_times"]
    assert set(pt["product_id"]).issubset(set(all_data["products"]["product_id"]))
    assert set(pt["machine_id"]).issubset(set(all_data["machines"]["machine_id"]))


def test_bom_references_known_materials(all_data):
    bom = all_data["bill_of_materials"]
    materials = set(all_data["raw_materials"]["material_id"])
    assert set(bom["material_id"]).issubset(materials)


def test_historical_demand_no_negative_values(all_data):
    assert (all_data["historical_demand"]["demand_qty"] >= 0).all()


def test_missing_file_raises_clear_error(tmp_path, monkeypatch):
    from app import config as cfg
    bogus_path = tmp_path / "does_not_exist.csv"
    monkeypatch.setitem(cfg.FILES, "products", bogus_path)
    with pytest.raises(DataValidationError):
        da.load_products()


def test_data_health_summary_reports_ok(all_data):
    summary = da.data_health_summary()
    assert all(v["ok"] for v in summary.values())
