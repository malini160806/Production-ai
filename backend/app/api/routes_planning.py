from fastapi import APIRouter, HTTPException

from .. import data_access as da
from ..data_access import DataValidationError
from .. import db
from ..ml.forecast import forecast_product
from ..planning.engine import generate_recommendation
from ..schemas import PlanningApprovalRequest, PlanningGenerateRequest

router = APIRouter(prefix="/planning", tags=["planning"])


def _forecast_qty_for_horizon(history, product_id: str, horizon_days: int) -> tuple[float, str]:
    """Returns (expected_qty_over_horizon, source_note)."""
    product_history = history[history["product_id"] == product_id]
    result = forecast_product(product_history, product_id, horizon_days)
    if result["status"] == "ok":
        total = sum(p["predicted_qty"] for p in result["forecast"])
        return total, "ML forecast (trained XGBoost model)"
    # Fallback: naive average-based estimate, clearly labelled as such.
    avg_daily = float(product_history["demand_qty"].tail(60).mean()) if not product_history.empty else 0.0
    return avg_daily * horizon_days, f"Naive average-based estimate ({result['status']}: model not available)"


@router.post("/generate")
def generate_plan(req: PlanningGenerateRequest):
    try:
        products = da.load_products()
        history = da.load_historical_demand()
        orders = da.load_orders()
        inventory = da.load_inventory()
        bom = da.load_bom()
        raw_materials = da.load_raw_materials()
        processing_times = da.load_processing_times()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    target_products = products
    if req.product_ids:
        unknown = set(req.product_ids) - set(products["product_id"])
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown product_id(s): {sorted(unknown)}")
        target_products = products[products["product_id"].isin(req.product_ids)]

    recommendations = []
    for _, product in target_products.iterrows():
        pid = product["product_id"]
        forecast_qty, source_note = _forecast_qty_for_horizon(history, pid, req.horizon_days)
        on_hand = float(inventory.loc[inventory["product_id"] == pid, "on_hand_qty"].sum())

        rec = generate_recommendation(
            product_id=pid, product_name=product["product_name"], horizon_days=req.horizon_days,
            forecast_qty=forecast_qty, orders=orders, history=history[history["product_id"] == pid],
            inventory_on_hand=on_hand, safety_stock_days=float(product["safety_stock_days"]),
            bom=bom, raw_materials=raw_materials, processing_times=processing_times,
        )
        rec_dict = rec.to_dict()
        rec_dict["forecast_source"] = source_note
        if rec.recommended_quantity > 0:
            rec_dict["approval_id"] = db.create_planning_approval(pid, rec.recommended_quantity)
        else:
            rec_dict["approval_id"] = None
        recommendations.append(rec_dict)

    return {"horizon_days": req.horizon_days, "recommendations": recommendations}


@router.post("/approve")
def decide_approval(req: PlanningApprovalRequest):
    ok = db.decide_planning_approval(
        req.approval_id, req.decision, req.approved_quantity, req.planner_note
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Approval id {req.approval_id} not found")
    db.log_audit("planning_decision", req.model_dump())
    return {"approval_id": req.approval_id, "decision": req.decision}


@router.get("/approvals")
def list_approvals(limit: int = 100):
    return db.list_planning_approvals(limit=limit)
