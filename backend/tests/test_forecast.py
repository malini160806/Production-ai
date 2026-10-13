import numpy as np
import pandas as pd
import pytest

from app.ml.forecast import forecast_product
from app.ml.train import InsufficientHistoryError, chronological_split, train_product_model


def _synthetic_history(n_days=120, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D").date
    base = 50 + 10 * np.sin(np.arange(n_days) * 2 * np.pi / 7)
    noise = rng.normal(0, 3, n_days)
    demand = np.clip(base + noise, 0, None).round()
    return pd.DataFrame({"date": dates, "product_id": "P_TEST", "demand_qty": demand})


def test_chronological_split_preserves_order():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=100), "v": range(100)})
    train, val, test = chronological_split(df)
    assert train["date"].max() < val["date"].min()
    assert val["date"].max() < test["date"].min()
    assert len(train) + len(val) + len(test) == len(df)


def test_train_product_model_beats_or_matches_sane_baseline(tmp_path, monkeypatch):
    from app import config as cfg
    monkeypatch.setattr(cfg, "MODELS_DIR", tmp_path)
    import app.ml.train as train_mod
    monkeypatch.setattr(train_mod, "MODELS_DIR", tmp_path)

    hist = _synthetic_history(120)
    meta = train_product_model(hist, "P_TEST")
    assert "model_metrics" in meta and "baseline_metrics" in meta
    assert meta["model_metrics"]["mae"] >= 0
    assert meta["n_test_rows"] > 0
    # Model should not be dramatically worse than the naive baseline on a
    # reasonably predictable synthetic series.
    assert meta["model_metrics"]["mae"] <= meta["baseline_metrics"]["mae"] * 1.5


def test_insufficient_history_raises():
    hist = _synthetic_history(10)  # below MIN_HISTORY_DAYS
    with pytest.raises(InsufficientHistoryError):
        train_product_model(hist, "P_TEST")


def test_forecast_product_without_trained_model_returns_explicit_status(tmp_path, monkeypatch):
    import app.ml.forecast as forecast_mod
    monkeypatch.setattr(forecast_mod, "MODELS_DIR", tmp_path)
    hist = _synthetic_history(60)
    result = forecast_product(hist, "P_UNKNOWN_NO_MODEL", 7)
    assert result["status"] == "model_not_trained"
    assert result["forecast"] == []


def test_forecast_product_with_empty_history_returns_explicit_status(tmp_path, monkeypatch):
    import app.ml.forecast as forecast_mod
    monkeypatch.setattr(forecast_mod, "MODELS_DIR", tmp_path)
    empty = pd.DataFrame(columns=["date", "product_id", "demand_qty"])
    result = forecast_product(empty, "P_TEST", 7)
    assert result["status"] in ("model_not_trained", "no_history")


def test_forecast_recursive_horizon_length(tmp_path, monkeypatch):
    from app import config as cfg
    monkeypatch.setattr(cfg, "MODELS_DIR", tmp_path)
    import app.ml.train as train_mod
    import app.ml.forecast as forecast_mod
    monkeypatch.setattr(train_mod, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(forecast_mod, "MODELS_DIR", tmp_path)

    hist = _synthetic_history(120)
    train_product_model(hist, "P_TEST")
    result = forecast_product(hist, "P_TEST", 10)
    assert result["status"] == "ok"
    assert len(result["forecast"]) == 10
    # Forecast dates must be strictly increasing and start the day after history ends.
    dates = [pd.Timestamp(p["date"]) for p in result["forecast"]]
    assert dates == sorted(dates)
    assert dates[0] == pd.Timestamp(hist["date"].max()) + pd.Timedelta(days=1)
    assert all(p["predicted_qty"] >= 0 for p in result["forecast"])
