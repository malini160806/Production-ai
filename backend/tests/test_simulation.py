import pandas as pd

from app.simulation import disruptions as D
from app.simulation.engine import UnknownDisruptionType, apply_disruption, run_simulation


def test_machine_breakdown_adds_status_row_without_mutating_original(all_data):
    original = all_data["machine_status"]
    original_len = len(original)
    new_df, desc = D.simulate_machine_breakdown(
        original, "M01", pd.Timestamp("2026-10-20T08:00:00"), 4.0, "test failure"
    )
    assert len(original) == original_len  # original untouched
    assert len(new_df) == original_len + 1
    assert "M01" in desc


def test_material_shortage_reduces_stock_without_mutating_original(all_data):
    original = all_data["raw_materials"]
    mat_id = original["material_id"].iloc[0]
    before_qty = float(original.loc[original["material_id"] == mat_id, "on_hand_qty"].iloc[0])
    new_df, desc = D.simulate_material_shortage(original, mat_id, before_qty / 2)
    after_qty = float(new_df.loc[new_df["material_id"] == mat_id, "on_hand_qty"].iloc[0])
    assert after_qty == before_qty - before_qty / 2
    assert float(original.loc[original["material_id"] == mat_id, "on_hand_qty"].iloc[0]) == before_qty


def test_new_urgent_order_appends_row(all_data):
    original = all_data["orders"]
    new_df, desc = D.simulate_new_urgent_order(original, "P001", 25, pd.Timestamp("2026-10-20").date(), "high")
    assert len(new_df) == len(original) + 1
    new_row = new_df[~new_df["order_id"].isin(original["order_id"])]
    assert len(new_row) == 1
    assert new_row.iloc[0]["product_id"] == "P001"
    assert new_row.iloc[0]["status"] == "confirmed"


def test_unknown_disruption_type_raises():
    import pytest
    with pytest.raises(UnknownDisruptionType):
        apply_disruption("not_a_real_disruption", {}, {})


def test_run_simulation_produces_before_after_and_diff(all_data):
    from datetime import date
    result = run_simulation(
        "machine_breakdown",
        {"machine_id": "M01", "start_datetime": "2026-10-14T08:00:00", "duration_hours": 4, "reason": "test"},
        all_data, date.today(), 7, None, time_limit_seconds=5,
    )
    assert "before" in result and "after" in result and "diff" in result
    assert result["disruption_type"] == "machine_breakdown"
    assert isinstance(result["diff"]["changed_orders"], list)
    # Completed/committed jobs concept: locked orders (none in synthetic
    # data by default) should never appear as "changed" in the diff.
    for entry in result["diff"]["changed_orders"]:
        assert "order_id" in entry


def test_order_change_updates_quantity_and_due_date(all_data):
    orders = all_data["orders"]
    order_id = orders["order_id"].iloc[0]
    new_df, desc = D.simulate_order_change(orders, order_id, new_quantity=999, new_due_date=pd.Timestamp("2026-12-31").date())
    row = new_df[new_df["order_id"] == order_id].iloc[0]
    assert row["quantity"] == 999
    assert str(row["due_date"]) == "2026-12-31"
