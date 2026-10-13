"""
Module B: Production planning engine.

Converts demand signals + current factory state into a proposed production
quantity per product, with a fully documented, explainable calculation.

Formula
-------
    expected_demand   = max(confirmed_order_qty_in_horizon, forecast_qty_in_horizon)
    net_requirement    = max(0, expected_demand + safety_stock - on_hand_inventory - planned_receipts)

Why `max()` instead of summing forecast + confirmed orders:
    A demand forecast is meant to approximate TOTAL expected demand for the
    horizon, including the portion that will arrive as confirmed orders. If
    we added forecast + confirmed orders directly we would double-count the
    demand that is already reflected in both numbers. Taking the greater of
    the two uses whichever signal is more informed for that product: once
    confirmed orders exceed the statistical forecast, trust the firm orders;
    otherwise plan to the forecast.

safety_stock = safety_stock_days (product master data) * average daily
    demand observed in history (0 if no history).
planned_receipts = quantity from orders/jobs already committed to a machine
    (locked=True or committed_machine_id set) that have not yet completed —
    i.e. production already planned that will land within the horizon.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd


@dataclass
class MaterialCheck:
    material_id: str
    required_qty: float
    available_qty: float
    shortage_qty: float

    @property
    def sufficient(self) -> bool:
        return self.shortage_qty <= 1e-9


@dataclass
class PlanningRecommendation:
    product_id: str
    product_name: str
    horizon_days: int
    forecast_qty: float
    confirmed_order_qty: float
    expected_demand: float
    safety_stock_qty: float
    on_hand_inventory: float
    planned_receipts: float
    net_requirement: float
    recommended_quantity: float
    material_checks: List[MaterialCheck] = field(default_factory=list)
    material_constrained_quantity: Optional[float] = None
    capacity_minutes_required: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["material_checks"] = [mc.__dict__ for mc in self.material_checks]
        return d


def _avg_daily_demand(history: pd.DataFrame) -> float:
    if history.empty:
        return 0.0
    return float(history["demand_qty"].tail(60).mean())


def generate_recommendation(
    product_id: str,
    product_name: str,
    horizon_days: int,
    forecast_qty: float,
    orders: pd.DataFrame,
    history: pd.DataFrame,
    inventory_on_hand: float,
    safety_stock_days: float,
    bom: pd.DataFrame,
    raw_materials: pd.DataFrame,
    processing_times: pd.DataFrame,
) -> PlanningRecommendation:
    product_orders = orders[orders["product_id"] == product_id]
    confirmed_order_qty = float(
        product_orders[product_orders["status"] == "confirmed"]["quantity"].sum()
    )
    has_committed_machine = (
        product_orders["committed_machine_id"].notna()
        & (product_orders["committed_machine_id"].astype(str).str.strip() != "")
        if "committed_machine_id" in product_orders.columns
        else pd.Series(False, index=product_orders.index)
    )
    is_locked = product_orders["locked"] if "locked" in product_orders.columns else pd.Series(False, index=product_orders.index)
    planned_receipts = float(product_orders[is_locked.astype(bool) | has_committed_machine]["quantity"].sum())

    expected_demand = max(confirmed_order_qty, forecast_qty)
    avg_daily = _avg_daily_demand(history)
    safety_stock_qty = avg_daily * safety_stock_days

    net_requirement = max(0.0, expected_demand + safety_stock_qty - inventory_on_hand - planned_receipts)
    recommended_quantity = net_requirement

    # Raw material feasibility check
    material_checks: List[MaterialCheck] = []
    product_bom = bom[bom["product_id"] == product_id]
    material_constrained_quantity = None
    if not product_bom.empty and recommended_quantity > 0:
        max_producible_by_material = float("inf")
        for _, row in product_bom.iterrows():
            mat_id = row["material_id"]
            qty_per_unit = float(row["qty_per_unit"])
            available = float(
                raw_materials.loc[raw_materials["material_id"] == mat_id, "on_hand_qty"].sum()
            )
            required = qty_per_unit * recommended_quantity
            shortage = max(0.0, required - available)
            material_checks.append(MaterialCheck(mat_id, required, available, shortage))
            if qty_per_unit > 0:
                max_producible_by_material = min(max_producible_by_material, available / qty_per_unit)
        if any(not mc.sufficient for mc in material_checks):
            material_constrained_quantity = max(0.0, min(recommended_quantity, max_producible_by_material))

    final_quantity = (
        material_constrained_quantity
        if material_constrained_quantity is not None
        else recommended_quantity
    )

    capacity_minutes = 0.0
    prod_times = processing_times[processing_times["product_id"] == product_id]
    if not prod_times.empty:
        capacity_minutes = float(prod_times["processing_minutes_per_unit"].min()) * final_quantity

    explanation_parts = [
        f"Forecasted demand over {horizon_days} days: {forecast_qty:.1f} units.",
        f"Confirmed customer orders in horizon: {confirmed_order_qty:.1f} units.",
        f"Expected demand taken as max(forecast, confirmed orders) = {expected_demand:.1f} "
        f"(avoids double-counting demand already reflected in the forecast).",
        f"Safety stock target: {safety_stock_days:.1f} days x {avg_daily:.1f} avg daily demand "
        f"= {safety_stock_qty:.1f} units.",
        f"Current finished-goods inventory on hand: {inventory_on_hand:.1f} units.",
        f"Already planned/committed production landing in horizon: {planned_receipts:.1f} units.",
        f"Net requirement = max(0, {expected_demand:.1f} + {safety_stock_qty:.1f} - "
        f"{inventory_on_hand:.1f} - {planned_receipts:.1f}) = {net_requirement:.1f} units.",
    ]
    if material_constrained_quantity is not None:
        explanation_parts.append(
            f"Raw material availability limits producible quantity to "
            f"{material_constrained_quantity:.1f} units (below the {net_requirement:.1f} unit requirement)."
        )
    explanation_parts.append(f"Recommended production quantity: {final_quantity:.1f} units.")

    return PlanningRecommendation(
        product_id=product_id,
        product_name=product_name,
        horizon_days=horizon_days,
        forecast_qty=round(forecast_qty, 1),
        confirmed_order_qty=round(confirmed_order_qty, 1),
        expected_demand=round(expected_demand, 1),
        safety_stock_qty=round(safety_stock_qty, 1),
        on_hand_inventory=round(inventory_on_hand, 1),
        planned_receipts=round(planned_receipts, 1),
        net_requirement=round(net_requirement, 1),
        recommended_quantity=round(final_quantity, 1),
        material_checks=material_checks,
        material_constrained_quantity=(
            round(material_constrained_quantity, 1) if material_constrained_quantity is not None else None
        ),
        capacity_minutes_required=round(capacity_minutes, 1),
        explanation=" ".join(explanation_parts),
    )
