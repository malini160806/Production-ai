from datetime import date

from fastapi import APIRouter, HTTPException

from .. import data_access as da
from .. import db
from ..data_access import DataValidationError
from ..scheduling.calendar_utils import WorkTimeMapping, minute_to_datetime
from ..scheduling.cp_sat_scheduler import ScheduleResult
from ..scheduling.evaluator import compare_schedules, evaluate_schedule
from ..scheduling.runner import run_baseline_schedule, run_optimized_schedule
from ..schemas import RescheduleRequest, ScheduleOptimizeRequest

router = APIRouter(prefix="/schedule", tags=["scheduling"])


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


def _serialize_result(result: ScheduleResult, horizon_start: date, mapping: WorkTimeMapping) -> dict:
    scheduled = []
    for s in result.scheduled:
        scheduled.append({
            **s.__dict__,
            "start_datetime": minute_to_datetime(mapping.work_to_calendar(s.start_minute), horizon_start).isoformat(),
            "end_datetime": minute_to_datetime(mapping.work_to_calendar(s.end_minute), horizon_start).isoformat(),
            "due_datetime": minute_to_datetime(mapping.work_to_calendar(s.due_minute), horizon_start).isoformat(),
        })
    return {
        "status": result.status,
        "solve_time_seconds": result.solve_time_seconds,
        "objective_value": result.objective_value,
        "makespan_minutes": result.makespan_minutes,
        "total_tardiness_minutes": result.total_tardiness_minutes,
        "num_late_orders": result.num_late_orders,
        "scheduled": scheduled,
        "unscheduled": [u.__dict__ for u in result.unscheduled],
    }


@router.post("/optimize")
def optimize(req: ScheduleOptimizeRequest):
    data = _load_all()
    horizon_start = date.today()
    weights = req.objective_weights.model_dump() if req.objective_weights else None

    result, material_info, mapping = run_optimized_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start,
        req.horizon_days, weights, req.time_limit_seconds,
    )
    payload = _serialize_result(result, horizon_start, mapping)
    metrics = evaluate_schedule(result, list(data["machines"]["machine_id"]), mapping.total_work_minutes)
    payload["metrics"] = metrics.__dict__

    if req.compare_baseline:
        baseline_result, _, base_mapping = run_baseline_schedule(
            data["orders"], data["machines"], data["processing_times"], data["machine_status"],
            data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start,
            req.horizon_days, req.baseline_rule,
        )
        baseline_metrics = evaluate_schedule(
            baseline_result, list(data["machines"]["machine_id"]), base_mapping.total_work_minutes
        )
        payload["baseline_comparison"] = compare_schedules(baseline_metrics, metrics)
        payload["baseline_comparison"]["baseline_rule"] = req.baseline_rule

    if req.persist:
        run_id = db.save_schedule_run(
            mode="optimized", status=result.status, horizon_start=horizon_start.isoformat(),
            horizon_days=req.horizon_days, objective_weights=weights or {}, metrics=metrics.__dict__,
            jobs=[{**s.__dict__} for s in result.scheduled] + [{**u.__dict__, "machine_id": None} for u in result.unscheduled],
        )
        payload["run_id"] = run_id
        db.log_audit("schedule_optimized", {"run_id": run_id, "status": result.status})

    payload["material_shortages"] = {k: v for k, v in material_info.items() if v["shortage"]}
    return payload


@router.post("/reschedule")
def reschedule(req: RescheduleRequest):
    """
    Recomputes the schedule from the current operational data, respecting
    any orders already marked locked/committed (their machine and start
    time are pinned and will not move). Intended to be called after a
    disruption has been applied via /api/simulation/run, or whenever
    underlying data has changed.
    """
    data = _load_all()
    horizon_start = date.today()
    weights = req.objective_weights.model_dump() if req.objective_weights else None

    result, material_info, mapping = run_optimized_schedule(
        data["orders"], data["machines"], data["processing_times"], data["machine_status"],
        data["bill_of_materials"], data["raw_materials"], data["products"], horizon_start,
        req.horizon_days, weights, req.time_limit_seconds,
    )
    payload = _serialize_result(result, horizon_start, mapping)
    metrics = evaluate_schedule(result, list(data["machines"]["machine_id"]), mapping.total_work_minutes)
    payload["metrics"] = metrics.__dict__

    run_id = db.save_schedule_run(
        mode="optimized_reschedule", status=result.status, horizon_start=horizon_start.isoformat(),
        horizon_days=req.horizon_days, objective_weights=weights or {}, metrics=metrics.__dict__,
        jobs=[{**s.__dict__} for s in result.scheduled] + [{**u.__dict__, "machine_id": None} for u in result.unscheduled],
    )
    payload["run_id"] = run_id
    db.log_audit("schedule_rescheduled", {"run_id": run_id, "status": result.status})
    payload["material_shortages"] = {k: v for k, v in material_info.items() if v["shortage"]}
    return payload


@router.get("/runs")
def get_runs(limit: int = 20):
    return db.list_schedule_runs(limit=limit)
