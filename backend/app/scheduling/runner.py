"""
End-to-end helpers that wire DataFrames -> JobSpecs -> a schedule result,
shared by the scheduling API routes and the disruption-simulation module so
both run the exact same pipeline.
"""
from datetime import date as date_cls
from typing import Dict, Optional, Tuple

import pandas as pd

from ..config import PLANNING_HORIZON_DAYS, SOLVER_TIME_LIMIT_SECONDS
from .baseline_scheduler import RuleType, solve_baseline
from .calendar_utils import WorkTimeMapping, maintenance_work_blocks, shared_working_windows
from .cp_sat_scheduler import ScheduleResult, solve_schedule
from .job_builder import build_jobs


def build_mapping(horizon_days: int) -> WorkTimeMapping:
    return WorkTimeMapping(shared_working_windows(horizon_days))


def _blocked_work_intervals(
    machines_df: pd.DataFrame, machine_status_df: pd.DataFrame, mapping: WorkTimeMapping,
    horizon_start: date_cls, horizon_days: int,
) -> Dict[str, list]:
    return {
        m_id: maintenance_work_blocks(m_id, machine_status_df, mapping, horizon_start, horizon_days)
        for m_id in machines_df["machine_id"]
    }


def run_optimized_schedule(
    orders_df: pd.DataFrame, machines_df: pd.DataFrame, processing_times_df: pd.DataFrame,
    machine_status_df: pd.DataFrame, bom_df: pd.DataFrame, raw_materials_df: pd.DataFrame,
    products_df: pd.DataFrame, horizon_start: date_cls, horizon_days: int = PLANNING_HORIZON_DAYS,
    objective_weights: Optional[dict] = None, time_limit_seconds: int = SOLVER_TIME_LIMIT_SECONDS,
) -> Tuple[ScheduleResult, dict, WorkTimeMapping]:
    mapping = build_mapping(horizon_days)
    jobs, material_info = build_jobs(
        orders_df, processing_times_df, machines_df, bom_df, raw_materials_df, products_df,
        horizon_start, horizon_days, mapping,
    )
    blocked = _blocked_work_intervals(machines_df, machine_status_df, mapping, horizon_start, horizon_days)
    result = solve_schedule(
        jobs, blocked, mapping.total_work_minutes, objective_weights=objective_weights,
        time_limit_seconds=time_limit_seconds,
    )
    return result, material_info, mapping


def run_baseline_schedule(
    orders_df: pd.DataFrame, machines_df: pd.DataFrame, processing_times_df: pd.DataFrame,
    machine_status_df: pd.DataFrame, bom_df: pd.DataFrame, raw_materials_df: pd.DataFrame,
    products_df: pd.DataFrame, horizon_start: date_cls, horizon_days: int = PLANNING_HORIZON_DAYS,
    rule: RuleType = "EDD",
) -> Tuple[ScheduleResult, dict, WorkTimeMapping]:
    mapping = build_mapping(horizon_days)
    jobs, material_info = build_jobs(
        orders_df, processing_times_df, machines_df, bom_df, raw_materials_df, products_df,
        horizon_start, horizon_days, mapping,
    )
    blocked = _blocked_work_intervals(machines_df, machine_status_df, mapping, horizon_start, horizon_days)
    result = solve_baseline(jobs, blocked, mapping.total_work_minutes, rule=rule)
    return result, material_info, mapping
