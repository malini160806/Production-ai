"""
SQLite persistence for operational records that mutate at runtime: schedule
run history, the audit trail of schedule changes, planner approvals of
production-planning recommendations, and logged disruption events.

The CSV files under backend/data remain the source of truth for master
data (products, machines, orders, etc). This database never overwrites
them; it only records what the system DID (schedules produced, decisions
made) so there is a durable audit trail, per project requirements.

Kept deliberately modular (a thin set of functions, no ORM) so it can be
swapped for another database later without touching calling code beyond
this module's public functions.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedule_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    mode TEXT NOT NULL,              -- 'optimized' or 'baseline'
    status TEXT NOT NULL,
    horizon_start TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    objective_weights_json TEXT,
    metrics_json TEXT
);

CREATE TABLE IF NOT EXISTS schedule_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES schedule_runs(id),
    order_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity REAL NOT NULL,
    machine_id TEXT,
    start_minute INTEGER,
    end_minute INTEGER,
    due_minute INTEGER,
    delay_minutes INTEGER,
    on_time INTEGER,
    unscheduled_reason TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS planning_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    recommended_quantity REAL NOT NULL,
    approved_quantity REAL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at TEXT NOT NULL,
    decided_at TEXT,
    planner_note TEXT
);

CREATE TABLE IF NOT EXISTS disruption_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    disruption_type TEXT NOT NULL,
    params_json TEXT,
    description TEXT
);
"""


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_audit(action: str, details: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, action, details_json) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat() + "Z", action, json.dumps(details, default=str)),
        )


def save_schedule_run(mode: str, status: str, horizon_start: str, horizon_days: int,
                       objective_weights: dict, metrics: dict, jobs: list) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO schedule_runs (created_at, mode, status, horizon_start, horizon_days, "
            "objective_weights_json, metrics_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat() + "Z", mode, status, horizon_start, horizon_days,
             json.dumps(objective_weights), json.dumps(metrics, default=str)),
        )
        run_id = cur.lastrowid
        for j in jobs:
            conn.execute(
                "INSERT INTO schedule_jobs (run_id, order_id, product_id, quantity, machine_id, "
                "start_minute, end_minute, due_minute, delay_minutes, on_time, unscheduled_reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, j.get("order_id"), j.get("product_id"), j.get("quantity"), j.get("machine_id"),
                 j.get("start_minute"), j.get("end_minute"), j.get("due_minute"), j.get("delay_minutes"),
                 int(j["on_time"]) if j.get("on_time") is not None else None, j.get("reason")),
            )
    return run_id


def list_schedule_runs(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM schedule_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def create_planning_approval(product_id: str, recommended_quantity: float) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO planning_approvals (product_id, recommended_quantity, status, created_at) "
            "VALUES (?, ?, 'pending', ?)",
            (product_id, recommended_quantity, datetime.utcnow().isoformat() + "Z"),
        )
        return cur.lastrowid


def decide_planning_approval(approval_id: int, status: str, approved_quantity: Optional[float],
                              planner_note: str = "") -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE planning_approvals SET status = ?, approved_quantity = ?, decided_at = ?, "
            "planner_note = ? WHERE id = ?",
            (status, approved_quantity, datetime.utcnow().isoformat() + "Z", planner_note, approval_id),
        )
        return cur.rowcount > 0


def list_planning_approvals(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM planning_approvals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def log_disruption_event(disruption_type: str, params: dict, description: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO disruption_events (timestamp, disruption_type, params_json, description) "
            "VALUES (?, ?, ?, ?)",
            (datetime.utcnow().isoformat() + "Z", disruption_type, json.dumps(params, default=str), description),
        )
