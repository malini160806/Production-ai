import json
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from .. import data_access as da
from .. import db
from ..config import MODELS_DIR, PLANNING_HORIZON_DAYS
from ..data_access import DataValidationError
from ..scheduling.evaluator import compare_schedules, evaluate_schedule
from ..scheduling.runner import run_baseline_schedule, run_optimized_schedule

router = APIRouter(tags=["reports"])

QUICK_TIME_LIMIT_SECONDS = 5


def _load_all():
    try:
        return {
            "orders": da.load_orders(),
            "machines": da.load_machines(),
            "processing_times": da.load_processing_times(),
            "machine_status": da.load_machine_status(),
            "bill_of_materials": da.load_bom(),
            "raw_materials": da.load_raw_materials(),
            "products": da.load_products(),
        }
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))


def _forecast_summary() -> dict:
    products = da.load_products()
    summary = {"trained_products": 0, "untrained_products": 0, "per_product": {}}
    for pid in products["product_id"]:
        meta_path = MODELS_DIR / f"{pid}_metadata.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            summary["trained_products"] += 1
            summary["per_product"][pid] = {
                "trained": True,
                "model_mae": meta["model_metrics"]["mae"],
                "baseline_mae": meta["baseline_metrics"]["mae"],
                "improvement_over_baseline_mae_pct": meta["improvement_over_baseline_mae_pct"],
            }
        else:
            summary["untrained_products"] += 1
            summary["per_product"][pid] = {"trained": False}
    return summary


@router.get("/metrics")
def metrics():
    data = _load_all()
    orders = data["orders"]
    active_orders = orders[orders["status"].isin(["confirmed", "pending"])]

    result, _, mapping = run_optimized_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], date.today(),
        PLANNING_HORIZON_DAYS, None, QUICK_TIME_LIMIT_SECONDS,
    )
    eval_metrics = evaluate_schedule(result, list(data["machines"]["machine_id"]), mapping.total_work_minutes)

    delayed = sum(1 for s in result.scheduled if not s.on_time)
    backlog_qty = float(
        orders[orders["order_id"].isin([u.order_id for u in result.unscheduled])]["quantity"].sum()
    )
    avg_utilization = (
        sum(eval_metrics.machine_utilization_pct.values()) / len(eval_metrics.machine_utilization_pct)
        if eval_metrics.machine_utilization_pct else 0.0
    )

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_active_orders": int(len(active_orders)),
        "planned_production_quantity": float(active_orders["quantity"].sum()),
        "on_time_delivery_rate_pct": eval_metrics.on_time_delivery_pct,
        "total_delayed_orders": int(delayed),
        "avg_machine_utilization_pct": round(avg_utilization, 2),
        "machine_utilization_pct": eval_metrics.machine_utilization_pct,
        "total_production_backlog_qty": backlog_qty,
        "demand_forecast_summary": _forecast_summary(),
        "schedule_status": result.status,
    }


@router.get("/reports")
def reports():
    data = _load_all()
    horizon_start = date.today()

    optimized, _, opt_mapping = run_optimized_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start,
        PLANNING_HORIZON_DAYS, None, QUICK_TIME_LIMIT_SECONDS,
    )
    baseline, _, base_mapping = run_baseline_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start,
        PLANNING_HORIZON_DAYS, "EDD",
    )

    opt_metrics = evaluate_schedule(optimized, list(data["machines"]["machine_id"]), opt_mapping.total_work_minutes)
    base_metrics = evaluate_schedule(baseline, list(data["machines"]["machine_id"]), base_mapping.total_work_minutes)
    comparison = compare_schedules(base_metrics, opt_metrics)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "forecast_summary": _forecast_summary(),
        "schedule_summary": {
            "status": optimized.status,
            "num_scheduled": len(optimized.scheduled),
            "num_unscheduled": len(optimized.unscheduled),
            "makespan_minutes": optimized.makespan_minutes,
        },
        "machine_utilization": opt_metrics.machine_utilization_pct,
        "on_time_delivery_pct": opt_metrics.on_time_delivery_pct,
        "total_tardiness_minutes": opt_metrics.total_tardiness_minutes,
        "baseline_vs_optimized": comparison,
        "notes": [
            "Forecast metrics (MAE/RMSE) are computed on a chronological test split and are "
            "ACTUAL evaluation results, not hypothetical.",
            "Schedule and baseline-comparison figures are computed from real solver/heuristic "
            "runs over the same orders, machines, and constraints in this request.",
            f"Planning horizon for this report: {PLANNING_HORIZON_DAYS} days starting {horizon_start.isoformat()}.",
        ],
    }
