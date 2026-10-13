import pandas as pd

from app.planning.engine import generate_recommendation


def _orders(product_id="P1", confirmed_qty=50, pending_qty=20):
    return pd.DataFrame([
        {"order_id": "O1", "product_id": product_id, "quantity": confirmed_qty, "status": "confirmed",
         "locked": False, "committed_machine_id": ""},
        {"order_id": "O2", "product_id": product_id, "quantity": pending_qty, "status": "pending",
         "locked": False, "committed_machine_id": ""},
    ])


def _history(product_id="P1", avg=10, n=30):
    dates = pd.date_range("2026-01-01", periods=n)
    return pd.DataFrame({"date": dates, "product_id": product_id, "demand_qty": [avg] * n})


def test_net_requirement_formula_basic():
    rec = generate_recommendation(
        product_id="P1", product_name="Test Product", horizon_days=14,
        forecast_qty=100, orders=_orders(confirmed_qty=0, pending_qty=0),
        history=_history(avg=5), inventory_on_hand=20, safety_stock_days=3,
        bom=pd.DataFrame(columns=["product_id", "material_id", "qty_per_unit"]),
        raw_materials=pd.DataFrame(columns=["material_id", "on_hand_qty"]),
        processing_times=pd.DataFrame(columns=["product_id", "machine_id", "processing_minutes_per_unit"]),
    )
    # expected_demand = max(confirmed(0), forecast(100)) = 100
    # safety_stock = 3 * 5 = 15
    # net = max(0, 100 + 15 - 20 - 0) = 95
    assert rec.expected_demand == 100
    assert rec.safety_stock_qty == 15
    assert rec.net_requirement == 95
    assert rec.recommended_quantity == 95


def test_confirmed_orders_do_not_double_count_with_forecast():
    """
    When confirmed orders exceed the forecast, expected demand should be the
    confirmed total (not forecast + confirmed), per the documented formula.
    """
    rec = generate_recommendation(
        product_id="P1", product_name="Test Product", horizon_days=14,
        forecast_qty=30, orders=_orders(confirmed_qty=80, pending_qty=0),
        history=_history(avg=2), inventory_on_hand=0, safety_stock_days=0,
        bom=pd.DataFrame(columns=["product_id", "material_id", "qty_per_unit"]),
        raw_materials=pd.DataFrame(columns=["material_id", "on_hand_qty"]),
        processing_times=pd.DataFrame(columns=["product_id", "machine_id", "processing_minutes_per_unit"]),
    )
    assert rec.confirmed_order_qty == 80
    assert rec.forecast_qty == 30
    assert rec.expected_demand == 80  # NOT 30 + 80 = 110


def test_negative_net_requirement_floors_to_zero():
    rec = generate_recommendation(
        product_id="P1", product_name="Test Product", horizon_days=14,
        forecast_qty=10, orders=_orders(confirmed_qty=0, pending_qty=0),
        history=_history(avg=1), inventory_on_hand=1000, safety_stock_days=0,
        bom=pd.DataFrame(columns=["product_id", "material_id", "qty_per_unit"]),
        raw_materials=pd.DataFrame(columns=["material_id", "on_hand_qty"]),
        processing_times=pd.DataFrame(columns=["product_id", "machine_id", "processing_minutes_per_unit"]),
    )
    assert rec.net_requirement == 0
    assert rec.recommended_quantity == 0


def test_material_shortage_constrains_recommended_quantity():
    bom = pd.DataFrame([{"product_id": "P1", "material_id": "RM1", "qty_per_unit": 2.0}])
    raw_materials = pd.DataFrame([{"material_id": "RM1", "on_hand_qty": 50.0}])
    rec = generate_recommendation(
        product_id="P1", product_name="Test Product", horizon_days=14,
        forecast_qty=100, orders=_orders(confirmed_qty=0, pending_qty=0),
        history=_history(avg=0), inventory_on_hand=0, safety_stock_days=0,
        bom=bom, raw_materials=raw_materials,
        processing_times=pd.DataFrame(columns=["product_id", "machine_id", "processing_minutes_per_unit"]),
    )
    # net_requirement = 100 units, but only 50 units of RM1 available at 2/unit -> 25 units producible
    assert rec.net_requirement == 100
    assert rec.material_constrained_quantity == 25
    assert rec.recommended_quantity == 25
    assert any(not mc.sufficient for mc in rec.material_checks)


def test_explanation_mentions_key_figures():
    rec = generate_recommendation(
        product_id="P1", product_name="Test Product", horizon_days=14,
        forecast_qty=40, orders=_orders(confirmed_qty=10, pending_qty=0),
        history=_history(avg=3), inventory_on_hand=5, safety_stock_days=2,
        bom=pd.DataFrame(columns=["product_id", "material_id", "qty_per_unit"]),
        raw_materials=pd.DataFrame(columns=["material_id", "on_hand_qty"]),
        processing_times=pd.DataFrame(columns=["product_id", "machine_id", "processing_minutes_per_unit"]),
    )
    assert "Net requirement" in rec.explanation
    assert "Recommended production quantity" in rec.explanation
