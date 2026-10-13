from fastapi import APIRouter, HTTPException

from .. import data_access as da
from ..data_access import DataValidationError
from ..ml.forecast import forecast_product
from ..ml.train import InsufficientHistoryError, train_all_products, train_product_model
from ..schemas import ForecastRequest, ForecastResponse, ForecastTrainRequest

router = APIRouter(prefix="/forecast", tags=["forecasting"])


@router.post("/train")
def train(req: ForecastTrainRequest):
    try:
        history = da.load_historical_demand()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.product_ids:
        known = set(history["product_id"].unique())
        unknown = set(req.product_ids) - known
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown product_id(s): {sorted(unknown)}")
        results = []
        for pid in req.product_ids:
            try:
                results.append(train_product_model(history[history["product_id"] == pid], pid))
            except InsufficientHistoryError as e:
                results.append({"product_id": pid, "skipped": True, "error": str(e)})
    else:
        results = train_all_products(history)

    trained = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]
    return {"trained_count": len(trained), "skipped_count": len(skipped), "results": results}


@router.post("", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    try:
        history = da.load_historical_demand()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    all_products = set(history["product_id"].unique()) | set(da.load_products()["product_id"])
    if req.product_id not in all_products:
        raise HTTPException(status_code=404, detail=f"Unknown product_id '{req.product_id}'")

    product_history = history[history["product_id"] == req.product_id]
    result = forecast_product(product_history, req.product_id, req.horizon_days)
    return result
