import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture()
def client(all_data):
    db.init_db()
    return TestClient(app)


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "products" in body["data_sources"]


def test_products_and_machines_and_orders(client):
    assert client.get("/api/products").status_code == 200
    assert client.get("/api/machines").status_code == 200
    assert client.get("/api/orders").status_code == 200


def test_forecast_requires_valid_horizon(client):
    r = client.post("/api/forecast", json={"product_id": "P001", "horizon_days": 0})
    assert r.status_code == 422  # Pydantic validation: horizon_days >= 1


def test_forecast_unknown_product_returns_404(client):
    r = client.post("/api/forecast", json={"product_id": "NOT_A_PRODUCT", "horizon_days": 7})
    assert r.status_code == 404


def test_forecast_train_unknown_product_returns_400(client):
    r = client.post("/api/forecast/train", json={"product_ids": ["NOT_A_PRODUCT"]})
    assert r.status_code == 400


def test_schedule_optimize_rejects_bad_baseline_rule(client):
    r = client.post("/api/schedule/optimize", json={"horizon_days": 7, "baseline_rule": "NOT_A_RULE"})
    assert r.status_code == 422


def test_schedule_optimize_returns_valid_payload_shape(client):
    r = client.post("/api/schedule/optimize", json={
        "horizon_days": 7, "time_limit_seconds": 5, "compare_baseline": True, "persist": False,
    })
    assert r.status_code == 200
    body = r.json()
    for key in ("status", "scheduled", "unscheduled", "metrics", "baseline_comparison"):
        assert key in body
    assert body["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN")


def test_simulation_requires_known_disruption_type(client):
    r = client.post("/api/simulation/run", json={
        "disruption_type": "not_a_real_type", "params": {}, "horizon_days": 7,
    })
    assert r.status_code == 400


def test_simulation_missing_param_returns_400(client):
    r = client.post("/api/simulation/run", json={
        "disruption_type": "machine_breakdown", "params": {}, "horizon_days": 7,
    })
    assert r.status_code == 400


def test_planning_approve_unknown_id_returns_404(client):
    r = client.post("/api/planning/approve", json={
        "approval_id": 999999, "decision": "approved",
    })
    assert r.status_code == 404


def test_planning_approve_rejects_bad_decision_value(client):
    r = client.post("/api/planning/approve", json={
        "approval_id": 1, "decision": "maybe",
    })
    assert r.status_code == 422


def test_metrics_and_reports(client):
    assert client.get("/api/metrics").status_code == 200
    assert client.get("/api/reports").status_code == 200
