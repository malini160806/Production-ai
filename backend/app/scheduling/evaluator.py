"""
Module F: evaluation metrics shared by the baseline and optimized schedules,
so comparisons are computed from real outputs rather than asserted.
"""
from dataclasses import dataclass
from typing import Dict, List

from .cp_sat_scheduler import ScheduleResult


@dataclass
class EvaluationMetrics:
    status: str
    solve_time_seconds: float
    num_scheduled: int
    num_unscheduled: int
    on_time_delivery_pct: float
    total_tardiness_minutes: int
    avg_tardiness_minutes: float
    makespan_minutes: int
    machine_utilization_pct: Dict[str, float]
    total_estimated_cost: float


def evaluate_schedule(
    result: ScheduleResult,
    machine_ids: List[str],
    horizon_minutes: int,
    cost_lookup: Dict[str, float] = None,  # (order_id -> estimated cost), optional
) -> EvaluationMetrics:
    num_scheduled = len(result.scheduled)
    num_unscheduled = len(result.unscheduled)
    total = num_scheduled + num_unscheduled
    on_time = sum(1 for s in result.scheduled if s.on_time)
    on_time_pct = (100.0 * on_time / num_scheduled) if num_scheduled else 0.0

    busy_by_machine: Dict[str, int] = {m: 0 for m in machine_ids}
    for s in result.scheduled:
        busy_by_machine[s.machine_id] = busy_by_machine.get(s.machine_id, 0) + (s.end_minute - s.start_minute)

    utilization = {
        m: round(100.0 * busy / horizon_minutes, 2) if horizon_minutes else 0.0
        for m, busy in busy_by_machine.items()
    }

    total_cost = 0.0
    if cost_lookup:
        total_cost = sum(cost_lookup.get(s.order_id, 0.0) for s in result.scheduled)

    return EvaluationMetrics(
        status=result.status,
        solve_time_seconds=round(result.solve_time_seconds, 3),
        num_scheduled=num_scheduled,
        num_unscheduled=num_unscheduled,
        on_time_delivery_pct=round(on_time_pct, 2),
        total_tardiness_minutes=result.total_tardiness_minutes,
        avg_tardiness_minutes=round(result.total_tardiness_minutes / num_scheduled, 2) if num_scheduled else 0.0,
        makespan_minutes=result.makespan_minutes,
        machine_utilization_pct=utilization,
        total_estimated_cost=round(total_cost, 2),
    )


def compare_schedules(baseline: EvaluationMetrics, optimized: EvaluationMetrics) -> dict:
    def pct_change(old, new):
        if old == 0:
            return 0.0 if new == 0 else float("inf")
        return round(100.0 * (new - old) / old, 2)

    return {
        "baseline": baseline.__dict__,
        "optimized": optimized.__dict__,
        "delta": {
            "on_time_delivery_pct_change": round(optimized.on_time_delivery_pct - baseline.on_time_delivery_pct, 2),
            "total_tardiness_minutes_change_pct": pct_change(
                baseline.total_tardiness_minutes, optimized.total_tardiness_minutes
            ),
            "makespan_minutes_change_pct": pct_change(baseline.makespan_minutes, optimized.makespan_minutes),
            "num_unscheduled_change": optimized.num_unscheduled - baseline.num_unscheduled,
        },
        "note": "All figures are calculated directly from the two schedules produced for "
                "the identical set of orders, machines, processing times, and constraints.",
    }
