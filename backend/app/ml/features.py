"""
Time-series-safe feature engineering for demand forecasting.

All lag and rolling features are computed using only information available
strictly BEFORE the target date (shift(1) before any rolling window), so no
future information leaks into a given row's features.
"""
from typing import List

import numpy as np
import pandas as pd

from ..config import LAG_DAYS, ROLLING_WINDOWS

FEATURE_COLUMNS: List[str] = (
    ["dow", "month", "day_of_month", "is_weekend", "week_of_year"]
    + [f"lag_{d}" for d in LAG_DAYS]
    + [f"roll_mean_{w}" for w in ROLLING_WINDOWS]
    + [f"roll_std_{w}" for w in ROLLING_WINDOWS]
)
TARGET_COLUMN = "demand_qty"


def build_calendar_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    d = pd.to_datetime(df[date_col])
    df = df.copy()
    df["dow"] = d.dt.weekday
    df["month"] = d.dt.month
    df["day_of_month"] = d.dt.day
    df["is_weekend"] = (d.dt.weekday >= 5).astype(int)
    df["week_of_year"] = d.dt.isocalendar().week.astype(int)
    return df


def build_lag_and_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects df sorted ascending by date for a SINGLE product, with a
    continuous or near-continuous `demand_qty` series (missing dates are
    tolerated but will produce NaN lags near gaps).
    """
    df = df.sort_values("date").reset_index(drop=True).copy()
    series = df[TARGET_COLUMN]

    for lag in LAG_DAYS:
        df[f"lag_{lag}"] = series.shift(lag)

    # shift(1) first so the rolling window never includes the current day's value
    shifted = series.shift(1)
    for w in ROLLING_WINDOWS:
        df[f"roll_mean_{w}"] = shifted.rolling(window=w, min_periods=max(2, w // 2)).mean()
        df[f"roll_std_{w}"] = shifted.rolling(window=w, min_periods=max(2, w // 2)).std()

    return df


def build_feature_frame(history: pd.DataFrame) -> pd.DataFrame:
    """
    history: DataFrame with columns [date, product_id, demand_qty] for ONE product,
    chronologically ordered, no duplicate dates.
    Returns a frame with FEATURE_COLUMNS + TARGET_COLUMN + date, with leading
    rows that lack sufficient lag history dropped (NaN rows).
    """
    df = build_calendar_features(history)
    df = build_lag_and_rolling_features(df)
    feature_df = df[["date", "product_id"] + FEATURE_COLUMNS + [TARGET_COLUMN]]
    return feature_df


def latest_feature_row(history: pd.DataFrame, as_of_date) -> pd.Series:
    """
    Build a single feature row to predict the day AFTER `as_of_date`, using
    only history up to and including as_of_date. Used for recursive multi-step
    forecasting where predicted values are appended to history for the next step.
    """
    df = build_calendar_features(
        pd.DataFrame({"date": [as_of_date + pd.Timedelta(days=1)]})
    )
    row = df.iloc[0].to_dict()

    hist_sorted = history.sort_values("date")
    series = hist_sorted.set_index("date")[TARGET_COLUMN]

    for lag in LAG_DAYS:
        target_date = pd.Timestamp(as_of_date) + pd.Timedelta(days=1) - pd.Timedelta(days=lag)
        row[f"lag_{lag}"] = series.get(target_date.date(), np.nan)

    for w in ROLLING_WINDOWS:
        window_vals = series.iloc[-w:] if len(series) >= 1 else pd.Series(dtype=float)
        row[f"roll_mean_{w}"] = window_vals.mean() if len(window_vals) else np.nan
        row[f"roll_std_{w}"] = window_vals.std() if len(window_vals) > 1 else 0.0

    return pd.Series(row)
