"""Manual smoke test hitting every endpoint via FastAPI's TestClient (no live server needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app import db

db.init_db()
client = TestClient(app)


def check(name, resp, expect=200):
    status = "OK" if resp.status_code == expect else "FAIL"
    print(f"[{status}] {name}: {resp.status_code}")
    if status == "FAIL":
        print("   ", resp.text[:500])
    return resp


check("health", client.get("/api/health"))
check("products", client.get("/api/products"))
check("machines", client.get("/api/machines"))
check("orders", client.get("/api/orders"))

check("forecast/train", client.post("/api/forecast/train", json={}))
check("forecast", client.post("/api/forecast", json={"product_id": "P001", "horizon_days": 7}))
check("forecast unknown product", client.post("/api/forecast", json={"product_id": "ZZZZ", "horizon_days": 7}), expect=404)

r = check("planning/generate", client.post("/api/planning/generate", json={"horizon_days": 14}))
approvals = r.json()["recommendations"]
first_with_id = next((x for x in approvals if x["approval_id"]), None)
if first_with_id:
    check("planning/approve", client.post("/api/planning/approve", json={
        "approval_id": first_with_id["approval_id"], "decision": "approved",
        "approved_quantity": first_with_id["recommended_quantity"],
    }))
check("planning/approvals", client.get("/api/planning/approvals"))

check("schedule/optimize", client.post("/api/schedule/optimize", json={"horizon_days": 14, "time_limit_seconds": 10}))
check("schedule/reschedule", client.post("/api/schedule/reschedule", json={"horizon_days": 14, "time_limit_seconds": 10}))
check("schedule/runs", client.get("/api/schedule/runs"))

check("simulation/run breakdown", client.post("/api/simulation/run", json={
    "disruption_type": "machine_breakdown",
    "params": {"machine_id": "M01", "start_datetime": "2026-10-14T08:00:00", "duration_hours": 6, "reason": "test"},
    "horizon_days": 14,
}))
check("simulation/run urgent order", client.post("/api/simulation/run", json={
    "disruption_type": "new_urgent_order",
    "params": {"product_id": "P001", "quantity": 50, "due_date": "2026-10-16", "priority": "high"},
    "horizon_days": 14,
}))

check("metrics", client.get("/api/metrics"))
check("reports", client.get("/api/reports"))

print("\nSmoke test complete.")
