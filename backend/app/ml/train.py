"""
Training pipeline for per-product XGBoost demand forecasting models.

Splits are strictly chronological (train -> validation -> test, in time
order) to prevent future information from leaking into training, per
project requirements. A naive "same as last week" (lag_7) baseline is
evaluated on the identical test split so improvement claims are grounded
in a real comparison rather than asserted.
"""
import json
from datetime import date, datetime
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from ..config import MIN_HISTORY_DAYS, MODELS_DIR
from .features import FEATURE_COLUMNS, TARGET_COLUMN, build_feature_frame


class InsufficientHistoryError(ValueError):
    pass


def chronological_split(df: pd.DataFrame, train_frac=0.7, val_frac=0.15):
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


def train_product_model(history: pd.DataFrame, product_id: str) -> dict:
    """
    history: full historical_demand rows for ONE product, columns
    [date, product_id, demand_qty], chronologically sortable.
    Returns metadata dict; also persists model + metadata to MODELS_DIR.
    """
    history = history.sort_values("date").reset_index(drop=True)
    if len(history) < MIN_HISTORY_DAYS:
        raise InsufficientHistoryError(
            f"Product {product_id} has only {len(history)} days of history; "
            f"need at least {MIN_HISTORY_DAYS} to train safely."
        )

    feat = build_feature_frame(history).dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
    if len(feat) < 20:
        raise InsufficientHistoryError(
            f"Product {product_id} has only {len(feat)} usable rows after "
            f"feature engineering (lag/rolling windows consume leading rows)."
        )

    train_df, val_df, test_df = chronological_split(feat)
    if len(test_df) < 5:
        # fall back to a smaller val split so test always has a few points
        train_df, val_df, test_df = chronological_split(feat, train_frac=0.75, val_frac=0.10)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN]
    X_val, y_val = val_df[FEATURE_COLUMNS], val_df[TARGET_COLUMN]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COLUMN]

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        early_stopping_rounds=20,
        eval_metric="mae",
    )
    eval_set = [(X_val, y_val)] if len(X_val) >= 5 else [(X_train, y_train)]
    model.fit(X_train, y_train, eval_set=eval_set, verbose=False)

    pred_test = np.clip(model.predict(X_test), 0, None)
    model_metrics = _metrics(y_test.values, pred_test)

    # Baseline: naive "same as 7 days ago" forecast, evaluated on the SAME test rows.
    baseline_pred = test_df["lag_7"].ffill().fillna(y_train.mean()).values
    baseline_metrics = _metrics(y_test.values, baseline_pred)

    improvement_mae_pct = (
        100.0 * (baseline_metrics["mae"] - model_metrics["mae"]) / baseline_metrics["mae"]
        if baseline_metrics["mae"] > 0 else 0.0
    )

    metadata = {
        "product_id": product_id,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "history_start": str(history["date"].min()),
        "history_end": str(history["date"].max()),
        "n_history_days": len(history),
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
        "feature_columns": FEATURE_COLUMNS,
        "model_metrics": model_metrics,
        "baseline_metrics": baseline_metrics,
        "improvement_over_baseline_mae_pct": round(improvement_mae_pct, 2),
        "test_comparison": [
            {
                "date": str(d),
                "actual": float(a),
                "model_pred": float(p),
                "baseline_pred": float(b),
            }
            for d, a, p, b in zip(test_df["date"], y_test.values, pred_test, baseline_pred)
        ],
    }

    model_path = MODELS_DIR / f"{product_id}.joblib"
    meta_path = MODELS_DIR / f"{product_id}_metadata.json"
    joblib.dump(model, model_path)
    meta_path.write_text(json.dumps(metadata, indent=2))
    return metadata


def train_all_products(historical_demand: pd.DataFrame) -> List[dict]:
    results = []
    for product_id, group in historical_demand.groupby("product_id"):
        try:
            results.append(train_product_model(group, product_id))
        except InsufficientHistoryError as e:
            results.append({"product_id": product_id, "error": str(e), "skipped": True})
    return results
