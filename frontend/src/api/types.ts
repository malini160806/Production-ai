export interface Product {
  product_id: string;
  product_name: string;
  category: string;
  unit: string;
  unit_cost: number;
  safety_stock_days: number;
  lead_time_days: number;
}

export interface Machine {
  machine_id: string;
  machine_name: string;
  machine_type: string;
  capacity_units_per_hour: number;
  shift_start_min: number;
  shift_end_min: number;
  cost_per_hour: number;
}

export interface Order {
  order_id: string;
  product_id: string;
  quantity: number;
  order_date: string;
  due_date: string;
  priority: string;
  status: string;
  locked: boolean;
  committed_machine_id: string | null;
}

export interface ProcessingTime {
  product_id: string;
  machine_id: string;
  processing_minutes_per_unit: number;
  setup_minutes: number;
}

export interface MachineStatusEntry {
  machine_id: string;
  status: string;
  status_start: string;
  status_end: string;
  reason: string;
}

export interface HealthResponse {
  status: string;
  data_sources: Record<string, { ok: boolean; rows?: number; error?: string }>;
}

export interface ForecastPoint {
  date: string;
  predicted_qty: number;
}

export interface ForecastResponse {
  product_id: string;
  status: string;
  message?: string;
  forecast: ForecastPoint[];
  model_metrics?: { mae: number; rmse: number };
  baseline_metrics?: { mae: number; rmse: number };
  improvement_over_baseline_mae_pct?: number;
  trained_at?: string;
  history_range?: { start: string; end: string };
}

export interface TestComparisonPoint {
  date: string;
  actual: number;
  model_pred: number;
  baseline_pred: number;
}

export interface TrainResult {
  product_id: string;
  skipped?: boolean;
  error?: string;
  model_metrics?: { mae: number; rmse: number };
  baseline_metrics?: { mae: number; rmse: number };
  improvement_over_baseline_mae_pct?: number;
  test_comparison?: TestComparisonPoint[];
  n_history_days?: number;
  history_start?: string;
  history_end?: string;
}

export interface TrainResponse {
  trained_count: number;
  skipped_count: number;
  results: TrainResult[];
}

export interface MaterialCheck {
  material_id: string;
  required_qty: number;
  available_qty: number;
  shortage_qty: number;
}

export interface PlanningRecommendation {
  product_id: string;
  product_name: string;
  horizon_days: number;
  forecast_qty: number;
  confirmed_order_qty: number;
  expected_demand: number;
  safety_stock_qty: number;
  on_hand_inventory: number;
  planned_receipts: number;
  net_requirement: number;
  recommended_quantity: number;
  material_checks: MaterialCheck[];
  material_constrained_quantity: number | null;
  capacity_minutes_required: number;
  explanation: string;
  forecast_source: string;
  approval_id: number | null;
}

export interface PlanningGenerateResponse {
  horizon_days: number;
  recommendations: PlanningRecommendation[];
}

export interface PlanningApproval {
  id: number;
  product_id: string;
  recommended_quantity: number;
  approved_quantity: number | null;
  status: string;
  created_at: string;
  decided_at: string | null;
  planner_note: string;
}

export interface ObjectiveWeights {
  weighted_tardiness: number;
  num_late_orders: number;
  makespan: number;
  idle_time: number;
  setup_cost: number;
  production_cost: number;
}

export interface ScheduledJob {
  order_id: string;
  product_id: string;
  quantity: number;
  machine_id: string;
  start_minute: number;
  end_minute: number;
  due_minute: number;
  delay_minutes: number;
  on_time: boolean;
  start_datetime: string;
  end_datetime: string;
  due_datetime: string;
}

export interface UnscheduledJob {
  order_id: string;
  product_id: string;
  reason: string;
}

export interface EvaluationMetrics {
  status: string;
  solve_time_seconds: number;
  num_scheduled: number;
  num_unscheduled: number;
  on_time_delivery_pct: number;
  total_tardiness_minutes: number;
  avg_tardiness_minutes: number;
  makespan_minutes: number;
  machine_utilization_pct: Record<string, number>;
  total_estimated_cost: number;
}

export interface BaselineComparison {
  baseline: EvaluationMetrics;
  optimized: EvaluationMetrics;
  delta: {
    on_time_delivery_pct_change: number;
    total_tardiness_minutes_change_pct: number;
    makespan_minutes_change_pct: number;
    num_unscheduled_change: number;
  };
  note: string;
  baseline_rule?: string;
}

export interface ScheduleResponse {
  status: string;
  solve_time_seconds: number;
  objective_value: number | null;
  makespan_minutes: number;
  total_tardiness_minutes: number;
  num_late_orders: number;
  scheduled: ScheduledJob[];
  unscheduled: UnscheduledJob[];
  metrics: EvaluationMetrics;
  baseline_comparison?: BaselineComparison;
  run_id?: number;
  material_shortages: Record<string, { ready_minute: number; shortage: boolean; detail: string }>;
}

export interface SimulationResult {
  disruption_type: string;
  description: string;
  before: {
    status: string;
    num_scheduled: number;
    num_unscheduled: number;
    total_tardiness_minutes: number;
    makespan_minutes: number;
  };
  after: {
    status: string;
    num_scheduled: number;
    num_unscheduled: number;
    total_tardiness_minutes: number;
    makespan_minutes: number;
    scheduled: ScheduledJob[];
    unscheduled: UnscheduledJob[];
  };
  diff: {
    unchanged_count: number;
    changed_orders: Array<Record<string, unknown>>;
    newly_unscheduled: Array<Record<string, unknown>>;
    deadlines_at_risk: Array<Record<string, unknown>>;
  };
}

export interface MetricsResponse {
  generated_at: string;
  total_active_orders: number;
  planned_production_quantity: number;
  on_time_delivery_rate_pct: number;
  total_delayed_orders: number;
  avg_machine_utilization_pct: number;
  machine_utilization_pct: Record<string, number>;
  total_production_backlog_qty: number;
  demand_forecast_summary: {
    trained_products: number;
    untrained_products: number;
    per_product: Record<string, { trained: boolean; model_mae?: number; baseline_mae?: number; improvement_over_baseline_mae_pct?: number }>;
  };
  schedule_status: string;
}

export interface ReportsResponse {
  generated_at: string;
  forecast_summary: MetricsResponse["demand_forecast_summary"];
  schedule_summary: { status: string; num_scheduled: number; num_unscheduled: number; makespan_minutes: number };
  machine_utilization: Record<string, number>;
  on_time_delivery_pct: number;
  total_tardiness_minutes: number;
  baseline_vs_optimized?: BaselineComparison;
  notes: string[];
}
