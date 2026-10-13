"""
Shared time/calendar utilities for the scheduling engines.

Time convention (see app/config.py docstring): all schedule timestamps are
integer MINUTES SINCE THE START OF THE PLANNING HORIZON (horizon day 0,
00:00, local factory time).

Working-minute compression
---------------------------
All machines in this system share the same shift pattern (shift start/end
and lunch break — see config.py), so we build ONE shared calendar of
working windows across the horizon (nights and the lunch break excluded).
Job durations, ready times, and due dates are expressed in CP-SAT using
WORKING MINUTES on this shared calendar rather than raw calendar minutes.
This lets a job legitimately span the lunch break or run over into the
next shift/day (pausing overnight, resuming the next working period) —
exactly how a real multi-day production run behaves — without ever
"spending" non-working time. Only the compressed working-minute axis is
given to the solver's NoOverlap constraint, so arithmetic stays simple and
no arbitrary scaling factors are introduced.

Per-machine maintenance/breakdown windows are layered on top as additional
blocked ranges WITHIN that same working-minute axis (mapped through the
shared calendar), so a specific machine's downtime reduces only its own
availability.

`WorkTimeMapping.work_to_calendar` converts a solved working-minute value
back to a real calendar minute offset for API responses.
"""
from datetime import datetime, timedelta, date as date_cls
from typing import List, Tuple

import pandas as pd

from ..config import BREAK_END_MIN, BREAK_START_MIN, PLANNING_HORIZON_DAYS, SHIFT_END_MIN, SHIFT_START_MIN


def horizon_start_date(today: date_cls = None) -> date_cls:
    return today or date_cls.today()


def minute_to_datetime(minute: int, horizon_start: date_cls) -> datetime:
    return datetime.combine(horizon_start, datetime.min.time()) + timedelta(minutes=minute)


def datetime_to_minute(dt: datetime, horizon_start: date_cls) -> int:
    delta = dt - datetime.combine(horizon_start, datetime.min.time())
    return int(delta.total_seconds() // 60)


def daily_working_windows(day_index: int, shift_start=SHIFT_START_MIN, shift_end=SHIFT_END_MIN) -> List[Tuple[int, int]]:
    """Working sub-windows for one day, split around the lunch break."""
    base = day_index * 1440
    windows = []
    if BREAK_START_MIN > shift_start and BREAK_START_MIN < shift_end:
        windows.append((base + shift_start, base + BREAK_START_MIN))
        windows.append((base + BREAK_END_MIN, base + shift_end))
    else:
        windows.append((base + shift_start, base + shift_end))
    return windows


def shared_working_windows(
    horizon_days: int = PLANNING_HORIZON_DAYS,
    shift_start: int = SHIFT_START_MIN,
    shift_end: int = SHIFT_END_MIN,
) -> List[Tuple[int, int]]:
    """The universal (machine-independent) shift-minus-break calendar for the horizon."""
    windows: List[Tuple[int, int]] = []
    for day in range(horizon_days):
        windows.extend(daily_working_windows(day, shift_start, shift_end))
    return merge_intervals(windows)


class WorkTimeMapping:
    """
    Converts between real calendar minutes (since horizon start) and
    compressed "working minutes" (counting only time inside `windows`).
    """

    def __init__(self, windows: List[Tuple[int, int]]):
        self.windows = windows
        self._cum = []  # (calendar_start, calendar_end, work_minutes_before_this_window)
        total = 0
        for s, e in windows:
            self._cum.append((s, e, total))
            total += (e - s)
        self.total_work_minutes = total

    def calendar_to_work(self, t: int) -> int:
        """Working minutes elapsed strictly before calendar minute `t`."""
        for s, e, before in self._cum:
            if t <= s:
                return before
            if t < e:
                return before + (t - s)
        return self.total_work_minutes

    def work_to_calendar(self, w: int) -> int:
        """Inverse of calendar_to_work; clamps to the last window if w is out of range."""
        if not self._cum:
            return w
        for s, e, before in self._cum:
            length = e - s
            if w <= before + length:
                return s + (w - before)
        last_s, last_e, _ = self._cum[-1]
        return last_e


def maintenance_work_blocks(
    machine_id: str,
    machine_status_df: pd.DataFrame,
    mapping: WorkTimeMapping,
    horizon_start: date_cls,
    horizon_days: int = PLANNING_HORIZON_DAYS,
) -> List[Tuple[int, int]]:
    """
    Maintenance/breakdown windows for `machine_id`, converted into the
    shared working-minute axis (see module docstring) and clipped to the
    horizon. Returned as obstacle intervals to add to that machine's
    NoOverlap set (on top of the shared calendar, which already excludes
    nights/breaks for everyone).
    """
    horizon_minutes_cal = horizon_days * 1440
    blocked_work: List[Tuple[int, int]] = []
    status_rows = machine_status_df[machine_status_df["machine_id"] == machine_id]
    for _, row in status_rows.iterrows():
        if row.get("status") not in ("maintenance", "down", "breakdown"):
            continue
        if not row.get("status_start") or not row.get("status_end"):
            continue
        try:
            start_dt = pd.to_datetime(row["status_start"])
            end_dt = pd.to_datetime(row["status_end"])
        except Exception:
            continue
        start_min = max(0, datetime_to_minute(start_dt.to_pydatetime(), horizon_start))
        end_min = min(horizon_minutes_cal, datetime_to_minute(end_dt.to_pydatetime(), horizon_start))
        if end_min <= start_min:
            continue
        work_start = mapping.calendar_to_work(start_min)
        work_end = mapping.calendar_to_work(end_min)
        if work_end > work_start:
            blocked_work.append((work_start, work_end))
    return merge_intervals(blocked_work)


def merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def is_within_any_window(start: int, end: int, blocked: List[Tuple[int, int]]) -> bool:
    """True if [start, end) does not overlap any blocked interval."""
    for b_start, b_end in blocked:
        if start < b_end and end > b_start:
            return False
    return True
