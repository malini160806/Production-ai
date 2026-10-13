import numpy as np
import pandas as pd

from app.ml.features import FEATURE_COLUMNS, build_feature_frame, build_lag_and_rolling_features


def _toy_history(n=40):
    dates = pd.date_range("2026-01-01", periods=n, freq="D").date
    # Strictly increasing series so we can verify lag/rolling values exactly.
    demand = list(range(1, n + 1))
    return pd.DataFrame({"date": dates, "product_id": "P_TEST", "demand_qty": demand})


def test_lag_features_only_use_past_values():
    hist = _toy_history(40)
    feat = build_lag_and_rolling_features(hist)
    # lag_1 on row i should equal demand_qty on row i-1 (never the current or a future value).
    for i in range(1, len(feat)):
        assert feat.loc[i, "lag_1"] == hist.loc[i - 1, "demand_qty"]
    assert pd.isna(feat.loc[0, "lag_1"])


def test_rolling_mean_excludes_current_day():
    hist = _toy_history(40)
    feat = build_lag_and_rolling_features(hist)
    # roll_mean_7 at row i must be the mean of rows [i-7, i-1], excluding row i itself.
    i = 20
    expected = hist.loc[i - 7:i - 1, "demand_qty"].mean()
    assert abs(feat.loc[i, "roll_mean_7"] - expected) < 1e-9


def test_feature_frame_has_no_future_leakage_via_shuffle_invariance():
    """
    Reversing the ORDER in which future rows are appended must not change
    features computed for earlier rows — i.e. truncating history at any
    point produces identical features for all retained rows.
    """
    hist = _toy_history(40)
    full = build_feature_frame(hist)
    truncated = build_feature_frame(hist.iloc[:25])
    common = truncated["date"]
    full_subset = full[full["date"].isin(common)].reset_index(drop=True)
    truncated = truncated.reset_index(drop=True)
    for col in FEATURE_COLUMNS:
        pd.testing.assert_series_equal(
            full_subset[col].reset_index(drop=True), truncated[col].reset_index(drop=True),
            check_names=False,
        )


def test_calendar_features_present():
    hist = _toy_history(10)
    feat = build_feature_frame(hist)
    for col in ["dow", "month", "day_of_month", "is_weekend", "week_of_year"]:
        assert col in feat.columns
