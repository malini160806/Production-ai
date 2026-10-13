"""
Module C: constraint-based production scheduling using OR-Tools CP-SAT.

Modelling notes (documented explicitly per project requirements):

- Units: all durations/timestamps are integer MINUTES since horizon start
  (see calendar_utils.py). No arbitrary scaling factors are used to make
  schedules "fit" — if a job cannot fit, it is reported unscheduled with a
  reason rather than forced onto an impossible slot.
- A job's duration on a given machine = setup_minutes + processing_minutes_per_unit
  * quantity for that (product, machine) pair. Setup time is charged in full
  for every job (no sequence-dependent setup-time reduction modelled).
- Each job may run on any machine listed in its `options`. Exactly one
  option is chosen, OR the job is left unscheduled (with a large objective
  penalty) if no option fits within the horizon/material/committed-job
  constraints — this is how infeasible orders are identified rather than
  forced onto an impossible schedule.
- Nights and lunch breaks are removed entirely from the timeline the solver
  sees: all start/end/due/ready values here are in compressed WORKING
  MINUTES (see calendar_utils.WorkTimeMapping), so a job may legitimately
  span multiple shifts/days (pausing overnight, resuming next shift) without
  ever "spending" non-working time. Per-machine maintenance/downtime is
  layered on top as additional fixed obstacle intervals passed in via
  `blocked_intervals_by_machine` (already converted to the same working-
  minute axis by the caller).
- Locked/committed jobs are pinned to their existing machine and start time
  and are included in NoOverlap sets so new jobs cannot be placed on top of
  them (already-committed work is never silently moved).
- Objective weights are supplied as floats and internally scaled to
  integers (x100, rounded) because CP-SAT requires integer objective
  coefficients.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from ..config import DEFAULT_OBJECTIVE_WEIGHTS, SOLVER_TIME_LIMIT_SECONDS

UNSCHEDULED_PENALTY = 1_000_000


@dataclass
class MachineOption:
    machine_id: str
    duration_minutes: int
    setup_minutes: int
    cost_per_hour: float


@dataclass
class JobSpec:
    order_id: str
    product_id: str
    quantity: float
    due_minute: int
    priority_weight: int
    ready_minute: int = 0
    locked: bool = False
    committed_machine_id: Optional[str] = None
    committed_start_minute: Optional[int] = None
    options: List[MachineOption] = field(default_factory=list)
    no_option_reason: Optional[str] = None  # set by caller if options is empty


@dataclass
class ScheduledJob:
    order_id: str
    product_id: str
    quantity: float
    machine_id: str
    start_minute: int
    end_minute: int
    due_minute: int
    delay_minutes: int
    on_time: bool


@dataclass
class UnscheduledJob:
    order_id: str
    product_id: str
    reason: str


@dataclass
class ScheduleResult:
    status: str  # OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN
    solve_time_seconds: float
    scheduled: List[ScheduledJob]
    unscheduled: List[UnscheduledJob]
    makespan_minutes: int
    total_tardiness_minutes: int
    num_late_orders: int
    objective_value: Optional[float]


def _scale(weight: float) -> int:
    return max(0, round(weight * 100))


def solve_schedule(
    jobs: List[JobSpec],
    blocked_intervals_by_machine: Dict[str, List[Tuple[int, int]]],
    horizon_minutes: int,
    objective_weights: Optional[dict] = None,
    time_limit_seconds: int = SOLVER_TIME_LIMIT_SECONDS,
    precedence_pairs: Optional[List[Tuple[str, str]]] = None,
) -> ScheduleResult:
    weights = {**DEFAULT_OBJECTIVE_WEIGHTS, **(objective_weights or {})}
    model = cp_model.CpModel()

    runnable_jobs = [j for j in jobs if j.options]
    unschedulable_upfront = [
        UnscheduledJob(j.order_id, j.product_id, j.no_option_reason or "No compatible/available machine option.")
        for j in jobs if not j.options
    ]

    machine_intervals: Dict[str, List[cp_model.IntervalVar]] = {}

    def add_fixed_blocks():
        for m_id, blocks in blocked_intervals_by_machine.items():
            machine_intervals.setdefault(m_id, [])
            for i, (s, e) in enumerate(blocks):
                if e <= s:
                    continue
                iv = model.NewIntervalVar(s, e - s, e, f"blocked_{m_id}_{i}")
                machine_intervals[m_id].append(iv)

    add_fixed_blocks()

    job_end_vars: Dict[str, cp_model.IntVar] = {}
    job_start_vars: Dict[str, cp_model.IntVar] = {}
    job_machine_choice: Dict[str, Dict[str, cp_model.IntVar]] = {}
    unscheduled_lits: List[cp_model.IntVar] = []
    tardy_vars: List[cp_model.IntVar] = []
    late_bools: List[cp_model.IntVar] = []
    setup_cost_terms: List[cp_model.LinearExpr] = []
    prod_cost_terms: List[cp_model.LinearExpr] = []
    duration_presence_terms: List[cp_model.LinearExpr] = []

    for job in runnable_jobs:
        presence_lits = []
        option_ends = []
        option_starts = []
        job_machine_choice[job.order_id] = {}

        for idx, opt in enumerate(job.options):
            duration = max(1, int(round(opt.duration_minutes)))
            latest_start = horizon_minutes - duration
            if job.locked and job.committed_machine_id == opt.machine_id and job.committed_start_minute is not None:
                start_lb = start_ub = int(job.committed_start_minute)
            else:
                start_lb = max(0, int(job.ready_minute))
                start_ub = latest_start
            if start_ub < start_lb:
                continue  # this option cannot fit in the horizon at all

            presence = model.NewBoolVar(f"presence_{job.order_id}_{opt.machine_id}")
            start = model.NewIntVar(start_lb, start_ub, f"start_{job.order_id}_{opt.machine_id}")
            end = model.NewIntVar(start_lb + duration, start_ub + duration, f"end_{job.order_id}_{opt.machine_id}")
            interval = model.NewOptionalIntervalVar(
                start, duration, end, presence, f"iv_{job.order_id}_{opt.machine_id}"
            )
            if job.locked and job.committed_machine_id == opt.machine_id:
                model.Add(presence == 1)
                model.Add(start == job.committed_start_minute)

            machine_intervals.setdefault(opt.machine_id, []).append(interval)
            presence_lits.append(presence)
            option_starts.append((presence, start))
            option_ends.append((presence, end))
            job_machine_choice[job.order_id][opt.machine_id] = presence

            setup_cost_terms.append(presence * round(opt.setup_minutes / 60.0 * opt.cost_per_hour * 100))
            prod_cost_terms.append(presence * round((duration - opt.setup_minutes) / 60.0 * opt.cost_per_hour * 100))
            duration_presence_terms.append(presence * duration)

        if not presence_lits:
            unschedulable_upfront.append(
                UnscheduledJob(job.order_id, job.product_id,
                               "No machine option fits within the planning horizon "
                               "given its ready time and processing duration.")
            )
            continue

        if job.locked:
            model.Add(sum(presence_lits) == 1)
        else:
            unscheduled_lit = model.NewBoolVar(f"unscheduled_{job.order_id}")
            model.Add(sum(presence_lits) + unscheduled_lit == 1)
            unscheduled_lits.append(unscheduled_lit)

        job_end = model.NewIntVar(0, horizon_minutes, f"jobend_{job.order_id}")
        job_start = model.NewIntVar(0, horizon_minutes, f"jobstart_{job.order_id}")
        for presence, end in option_ends:
            model.Add(job_end == end).OnlyEnforceIf(presence)
        for presence, start in option_starts:
            model.Add(job_start == start).OnlyEnforceIf(presence)
        job_end_vars[job.order_id] = job_end
        job_start_vars[job.order_id] = job_start

        tardy = model.NewIntVar(0, horizon_minutes, f"tardy_{job.order_id}")
        model.Add(tardy >= job_end - job.due_minute)
        model.Add(tardy >= 0)
        tardy_vars.append(tardy * max(1, job.priority_weight))

        late = model.NewBoolVar(f"late_{job.order_id}")
        model.Add(job_end > job.due_minute).OnlyEnforceIf(late)
        model.Add(job_end <= job.due_minute).OnlyEnforceIf(late.Not())
        late_bools.append(late)

    for m_id, intervals in machine_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    if precedence_pairs:
        for before_id, after_id in precedence_pairs:
            if before_id in job_end_vars and after_id in job_start_vars:
                model.Add(job_start_vars[after_id] >= job_end_vars[before_id])

    makespan = model.NewIntVar(0, horizon_minutes, "makespan")
    if job_end_vars:
        model.AddMaxEquality(makespan, list(job_end_vars.values()))
    else:
        model.Add(makespan == 0)

    num_machines = max(1, len(machine_intervals))
    total_duration_scheduled = sum(duration_presence_terms) if duration_presence_terms else 0
    idle_proxy = model.NewIntVar(0, horizon_minutes * num_machines, "idle_proxy")
    model.Add(idle_proxy == makespan * num_machines - total_duration_scheduled)

    objective_terms = []
    if tardy_vars:
        objective_terms.append(_scale(weights["weighted_tardiness"]) * sum(tardy_vars))
    if late_bools:
        objective_terms.append(_scale(weights["num_late_orders"]) * sum(late_bools))
    objective_terms.append(_scale(weights["makespan"]) * makespan)
    objective_terms.append(_scale(weights["idle_time"]) * idle_proxy)
    if setup_cost_terms:
        objective_terms.append(_scale(weights["setup_cost"]) * sum(setup_cost_terms))
    if prod_cost_terms:
        objective_terms.append(_scale(weights["production_cost"]) * sum(prod_cost_terms))
    if unscheduled_lits:
        objective_terms.append(UNSCHEDULED_PENALTY * sum(unscheduled_lits))

    model.Minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    # Single worker + fixed seed makes solves deterministic: identical input always
    # produces identical output. This matters for disruption simulation (Module D),
    # where we diff a "before" and "after" schedule and want every difference to be
    # attributable to the disruption itself, not to parallel-search race noise.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status_code = solver.Solve(model)
    status_name = solver.StatusName(status_code)

    scheduled: List[ScheduledJob] = []
    unscheduled: List[UnscheduledJob] = list(unschedulable_upfront)

    if status_name in ("OPTIMAL", "FEASIBLE"):
        for job in runnable_jobs:
            if job.order_id not in job_machine_choice:
                continue
            chosen_machine = None
            for m_id, presence in job_machine_choice[job.order_id].items():
                if solver.Value(presence) == 1:
                    chosen_machine = m_id
                    break
            if chosen_machine is None:
                unscheduled.append(UnscheduledJob(
                    job.order_id, job.product_id,
                    "Solver could not find a feasible machine/time slot within the horizon "
                    "given due dates, committed jobs, and material readiness."
                ))
                continue
            start_v = solver.Value(job_start_vars[job.order_id])
            end_v = solver.Value(job_end_vars[job.order_id])
            delay = max(0, end_v - job.due_minute)
            scheduled.append(ScheduledJob(
                order_id=job.order_id, product_id=job.product_id, quantity=job.quantity,
                machine_id=chosen_machine, start_minute=start_v, end_minute=end_v,
                due_minute=job.due_minute, delay_minutes=delay, on_time=delay == 0,
            ))
        makespan_v = solver.Value(makespan)
        total_tardiness_v = sum(max(0, s.delay_minutes) for s in scheduled)
        num_late_v = sum(1 for s in scheduled if not s.on_time)
        objective_v = solver.ObjectiveValue()
    else:
        for job in runnable_jobs:
            unscheduled.append(UnscheduledJob(
                job.order_id, job.product_id,
                f"Solver status '{status_name}': no feasible schedule found for this problem instance."
            ))
        makespan_v, total_tardiness_v, num_late_v, objective_v = 0, 0, 0, None

    return ScheduleResult(
        status=status_name,
        solve_time_seconds=solver.WallTime(),
        scheduled=scheduled,
        unscheduled=unscheduled,
        makespan_minutes=makespan_v,
        total_tardiness_minutes=total_tardiness_v,
        num_late_orders=num_late_v,
        objective_value=objective_v,
    )
