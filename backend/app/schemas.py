"""Pydantic request/response schemas for the REST API."""
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    data_sources: Dict[str, dict]


class ProductOut(BaseModel):
    product_id: str
    product_name: str
    category: str
    unit: str
    unit_cost: float
    safety_stock_days: float
    lead_time_days: float


class MachineOut(BaseModel):
    machine_id: str
    machine_name: str
    machine_type: str
    capacity_units_per_hour: float
    shift_start_min: int
    shift_end_min: int
    cost_per_hour: float


class OrderOut(BaseModel):
    order_id: str
    product_id: str
    quantity: float
    order_date: date
    due_date: date
    priority: str
    status: str
    locked: bool = False
    committed_machine_id: Optional[str] = None


# ---------- Forecasting ----------
class ForecastTrainRequest(BaseModel):
    product_ids: Optional[List[str]] = Field(None, description="Train only these products; omit to train all.")


class ForecastRequest(BaseModel):
    product_id: str
    horizon_days: int = Field(14, ge=1, le=90)


class ForecastPoint(BaseModel):
    date: str
    predicted_qty: float


class ForecastResponse(BaseModel):
    product_id: str
    status: str
    message: Optional[str] = None
    forecast: List[ForecastPoint]
    model_metrics: Optional[Dict[str, float]] = None
    baseline_metrics: Optional[Dict[str, float]] = None
    improvement_over_baseline_mae_pct: Optional[float] = None
    trained_at: Optional[str] = None
    history_range: Optional[Dict[str, str]] = None


# ---------- Planning ----------
class PlanningGenerateRequest(BaseModel):
    horizon_days: int = Field(14, ge=1, le=90)
    product_ids: Optional[List[str]] = None


class PlanningApprovalRequest(BaseModel):
    approval_id: int
    decision: str = Field(..., pattern="^(approved|rejected)$")
    approved_quantity: Optional[float] = None
    planner_note: str = ""


# ---------- Scheduling ----------
class ObjectiveWeights(BaseModel):
    weighted_tardiness: float = 10.0
    num_late_orders: float = 50.0
    makespan: float = 1.0
    idle_time: float = 0.5
    setup_cost: float = 0.0
    production_cost: float = 0.0


class ScheduleOptimizeRequest(BaseModel):
    horizon_days: int = Field(14, ge=1, le=60)
    objective_weights: Optional[ObjectiveWeights] = None
    time_limit_seconds: int = Field(20, ge=1, le=120)
    compare_baseline: bool = True
    baseline_rule: str = Field("EDD", pattern="^(EDD|FCFS)$")
    persist: bool = True


class RescheduleRequest(BaseModel):
    horizon_days: int = Field(14, ge=1, le=60)
    objective_weights: Optional[ObjectiveWeights] = None
    time_limit_seconds: int = Field(20, ge=1, le=120)


# ---------- Simulation ----------
class SimulationRequest(BaseModel):
    disruption_type: str = Field(
        ..., description="machine_breakdown | machine_restored | material_shortage | "
                          "new_urgent_order | order_change | processing_time_change"
    )
    params: Dict = Field(default_factory=dict)
    horizon_days: int = Field(14, ge=1, le=60)
    objective_weights: Optional[ObjectiveWeights] = None
    time_limit_seconds: int = Field(8, ge=1, le=60)


# ---------- Reports ----------
class ReportsResponse(BaseModel):
    generated_at: str
    forecast_summary: Dict
    schedule_summary: Dict
    machine_utilization: Dict
    on_time_delivery_pct: float
    total_tardiness_minutes: int
    baseline_vs_optimized: Optional[Dict] = None
    notes: List[str]
