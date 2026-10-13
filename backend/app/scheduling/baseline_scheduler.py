"""
Module F: traditional baseline scheduling heuristics (Earliest Due Date and
First-Come-First-Served) evaluated under the SAME constraints as the
OR-Tools CP-SAT optimizer (compatible machines, no-overlap, shift/break/
maintenance calendars, material readiness, locked jobs) so the comparison
in Module F is apples-to-apples.

Unlike the optimizer, this is a greedy, non-backtracking heuristic: once a
job is assigned to a slot it is never reconsidered. This is intentional —
it represents how a human planner or a simple dispatch rule would schedule,
and is the point of comparison for the optimizer's improvement.
"""
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from .calendar_utils import merge_intervals
from .cp_sat_scheduler import JobSpec, ScheduledJob, ScheduleResult, UnscheduledJob

RuleType = Literal["EDD", "FCFS"]


def _find_earliest_slot(
    duration: int, ready_minute: int, horizon_minutes: int, occupied: List[Tuple[int, int]]
) -> Optional[int]:
    merged = merge_intervals(occupied)
    candidate = max(0, ready_minute)
    for s, e in merged:
        if candidate + duration <= s:
            return candidate
        if e > candidate:
            candidate = e
    if candidate + duration <= horizon_minutes:
        return candidate
    return None


def solve_baseline(
    jobs: List[JobSpec],
    blocked_intervals_by_machine: Dict[str, List[Tuple[int, int]]],
    horizon_minutes: int,
    rule: RuleType = "EDD",
) -> ScheduleResult:
    import time
    t0 = time.time()

    if rule == "EDD":
        ordered = sorted(jobs, key=lambda j: (j.due_minute, -j.priority_weight))
    else:  # FCFS: approximate by ready_minute, then order_id for determinism
        ordered = sorted(jobs, key=lambda j: (j.ready_minute, j.order_id))

    occupied: Dict[str, List[Tuple[int, int]]] = {
        m_id: list(blocks) for m_id, blocks in blocked_intervals_by_machine.items()
    }

    scheduled: List[ScheduledJob] = []
    unscheduled: List[UnscheduledJob] = []

    for job in ordered:
        if not job.options:
            unscheduled.append(UnscheduledJob(
                job.order_id, job.product_id, job.no_option_reason or "No compatible/available machine option."
            ))
            continue

        if job.locked and job.committed_machine_id and job.committed_start_minute is not None:
            opt = next((o for o in job.options if o.machine_id == job.committed_machine_id), job.options[0])
            start = job.committed_start_minute
            end = start + opt.duration_minutes
            occupied.setdefault(opt.machine_id, []).append((start, end))
            delay = max(0, end - job.due_minute)
            scheduled.append(ScheduledJob(
                job.order_id, job.product_id, job.quantity, opt.machine_id, start, end,
                job.due_minute, delay, delay == 0,
            ))
            continue

        best_choice = None  # (start, end, machine_id)
        for opt in job.options:
            occ = occupied.get(opt.machine_id, [])
            start = _find_earliest_slot(int(round(opt.duration_minutes)), job.ready_minute, horizon_minutes, occ)
            if start is None:
                continue
            end = start + int(round(opt.duration_minutes))
            if best_choice is None or start < best_choice[0]:
                best_choice = (start, end, opt.machine_id)

        if best_choice is None:
            unscheduled.append(UnscheduledJob(
                job.order_id, job.product_id,
                "No compatible machine had a free slot of sufficient duration within the "
                "planning horizon after accounting for shifts, breaks, maintenance, and "
                "material readiness."
            ))
            continue

        start, end, machine_id = best_choice
        occupied.setdefault(machine_id, []).append((start, end))
        delay = max(0, end - job.due_minute)
        scheduled.append(ScheduledJob(
            job.order_id, job.product_id, job.quantity, machine_id, start, end,
            job.due_minute, delay, delay == 0,
        ))

    makespan = max((s.end_minute for s in scheduled), default=0)
    total_tardiness = sum(s.delay_minutes for s in scheduled)
    num_late = sum(1 for s in scheduled if not s.on_time)

    return ScheduleResult(
        status="HEURISTIC_" + rule,
        solve_time_seconds=time.time() - t0,
        scheduled=scheduled,
        unscheduled=unscheduled,
        makespan_minutes=makespan,
        total_tardiness_minutes=total_tardiness,
        num_late_orders=num_late,
        objective_value=None,
    )
