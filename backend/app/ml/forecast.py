"""
Inference: load a trained per-product model and produce an N-day-ahead
forecast using recursive (iterative) prediction — each predicted day is
appended to the working history so subsequent lag/rolling features for
later horizon days are computed from the model's own prior predictions.
"""
import json
from datetime import timedelta
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd

from ..config import MODELS_DIR
from .features import FEATURE_COLUMNS, latest_feature_row


class ModelNotFoundError(FileNotFoundError):
    pass


def model_paths(product_id: str):
    return MODELS_DIR / f"{product_id}.joblib", MODELS_DIR / f"{product_id}_metadata.json"


def load_model_metadata(product_id: str) -> Optional[dict]:
    _, meta_path = model_paths(product_id)
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())


def forecast_product(history: pd.DataFrame, product_id: str, horizon_days: int) -> dict:
    """
    history: historical_demand rows for this product (date, product_id, demand_qty).
    Returns dict with forecast rows and the model's evaluation metadata, or
    an explicit error payload if the model/data is unavailable — never
    silently fabricates a number.
    """
    model_path, meta_path = model_paths(product_id)
    if not model_path.exists() or not meta_path.exists():
        return {
            "product_id": product_id,
            "status": "model_not_trained",
            "message": f"No trained model for product '{product_id}'. "
                       f"Call POST /api/forecast/train first.",
            "forecast": [],
        }
    if history.empty:
        return {
            "product_id": product_id,
            "status": "no_history",
            "message": f"No historical demand rows found for product '{product_id}'.",
            "forecast": [],
        }

    model = joblib.load(model_path)
    metadata = json.loads(meta_path.read_text())

    working_history = history[["date", "product_id", "demand_qty"]].sort_values("date").copy()
    last_date = pd.Timestamp(working_history["date"].max()).date()

    forecast_rows = []
    cursor = last_date
    for _ in range(horizon_days):
        feat_row = latest_feature_row(working_history, cursor)
        X = pd.DataFrame([feat_row[FEATURE_COLUMNS].to_dict()])
        pred = float(max(0.0, model.predict(X)[0]))
        next_date = cursor + timedelta(days=1)
        forecast_rows.append({"date": next_date.isoformat(), "predicted_qty": round(pred, 1)})
        working_history = pd.concat([
            working_history,
            pd.DataFrame([{"date": next_date, "product_id": product_id, "demand_qty": pred}]),
        ], ignore_index=True)
        cursor = next_date

    return {
        "product_id": product_id,
        "status": "ok",
        "forecast": forecast_rows,
        "model_metrics": metadata["model_metrics"],
        "baseline_metrics": metadata["baseline_metrics"],
        "improvement_over_baseline_mae_pct": metadata["improvement_over_baseline_mae_pct"],
        "trained_at": metadata["trained_at"],
        "history_range": {"start": metadata["history_start"], "end": metadata["history_end"]},
    }
