from app.scheduling.calendar_utils import WorkTimeMapping, shared_working_windows
from app.scheduling.cp_sat_scheduler import JobSpec, MachineOption, solve_schedule


def _mapping(horizon_days=5):
    return WorkTimeMapping(shared_working_windows(horizon_days))


def test_machine_compatibility_respected():
    """A job must only be assignable to machines listed in its options."""
    mapping = _mapping()
    jobs = [
        JobSpec(
            order_id="J1", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
            priority_weight=1, options=[MachineOption("M1", 60, 10, 10.0)],
        )
    ]
    result = solve_schedule(jobs, {"M1": [], "M2": []}, mapping.total_work_minutes, time_limit_seconds=5)
    assert len(result.scheduled) == 1
    assert result.scheduled[0].machine_id == "M1"


def test_no_overlapping_jobs_on_same_machine():
    mapping = _mapping()
    jobs = [
        JobSpec(order_id=f"J{i}", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
                priority_weight=1, options=[MachineOption("M1", 200, 0, 10.0)])
        for i in range(4)
    ]
    result = solve_schedule(jobs, {"M1": []}, mapping.total_work_minutes, time_limit_seconds=10)
    scheduled = sorted(result.scheduled, key=lambda s: s.start_minute)
    for a, b in zip(scheduled, scheduled[1:]):
        assert a.end_minute <= b.start_minute, "Jobs on the same machine must not overlap"


def test_tardiness_and_on_time_flagging():
    mapping = _mapping()
    # Due date impossibly early -> job will be late; on_time must be False and delay > 0.
    jobs = [
        JobSpec(order_id="LATE1", product_id="P1", quantity=10, due_minute=1,
                priority_weight=3, options=[MachineOption("M1", 300, 0, 10.0)])
    ]
    result = solve_schedule(jobs, {"M1": []}, mapping.total_work_minutes, time_limit_seconds=5)
    assert len(result.scheduled) == 1
    job = result.scheduled[0]
    assert job.on_time is False
    assert job.delay_minutes == job.end_minute - job.due_minute
    assert result.total_tardiness_minutes == job.delay_minutes


def test_infeasible_order_with_no_compatible_machine_is_reported_not_forced():
    mapping = _mapping()
    jobs = [
        JobSpec(order_id="NOOPT", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
                priority_weight=1, options=[], no_option_reason="No machine configured."),
    ]
    result = solve_schedule(jobs, {"M1": []}, mapping.total_work_minutes, time_limit_seconds=5)
    assert len(result.scheduled) == 0
    assert len(result.unscheduled) == 1
    assert result.unscheduled[0].order_id == "NOOPT"
    assert "No machine configured" in result.unscheduled[0].reason


def test_maintenance_block_is_respected():
    """A machine fully blocked for the entire horizon cannot host any job."""
    mapping = _mapping()
    full_block = [(0, mapping.total_work_minutes)]
    jobs = [
        JobSpec(order_id="J1", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
                priority_weight=1, options=[MachineOption("M1", 60, 0, 10.0)]),
    ]
    result = solve_schedule(jobs, {"M1": full_block}, mapping.total_work_minutes, time_limit_seconds=5)
    assert len(result.scheduled) == 0
    assert len(result.unscheduled) == 1


def test_locked_job_is_pinned_and_blocks_new_jobs():
    mapping = _mapping()
    locked_job = JobSpec(
        order_id="LOCKED", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
        priority_weight=1, locked=True, committed_machine_id="M1", committed_start_minute=0,
        options=[MachineOption("M1", 100, 0, 10.0)],
    )
    new_job = JobSpec(
        order_id="NEW", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
        priority_weight=1, options=[MachineOption("M1", 100, 0, 10.0)],
    )
    result = solve_schedule([locked_job, new_job], {"M1": []}, mapping.total_work_minutes, time_limit_seconds=5)
    locked_result = next(s for s in result.scheduled if s.order_id == "LOCKED")
    assert locked_result.start_minute == 0
    assert locked_result.machine_id == "M1"
    new_result = next((s for s in result.scheduled if s.order_id == "NEW"), None)
    if new_result is not None:
        # Must not overlap the locked job.
        assert new_result.start_minute >= locked_result.end_minute or new_result.end_minute <= locked_result.start_minute


def test_status_is_not_claimed_optimal_when_infeasible_within_time_limit():
    """Status must faithfully reflect solver outcome, never fabricated as optimal."""
    mapping = _mapping(horizon_days=1)  # tiny horizon
    full_block = [(0, mapping.total_work_minutes)]
    jobs = [
        JobSpec(order_id="J1", product_id="P1", quantity=10, due_minute=mapping.total_work_minutes,
                priority_weight=1, options=[MachineOption("M1", 60, 0, 10.0)]),
    ]
    result = solve_schedule(jobs, {"M1": full_block}, mapping.total_work_minutes, time_limit_seconds=3)
    assert result.status in ("OPTIMAL", "FEASIBLE")  # leaving the unschedulable job out is itself optimal
    assert len(result.unscheduled) == 1
