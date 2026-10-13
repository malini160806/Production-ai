import type {
  BaselineComparison,
  ForecastResponse,
  HealthResponse,
  Machine,
  MachineStatusEntry,
  MetricsResponse,
  ObjectiveWeights,
  Order,
  PlanningApproval,
  PlanningGenerateResponse,
  ProcessingTime,
  Product,
  ReportsResponse,
  ScheduleResponse,
  SimulationResult,
  TrainResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    throw new ApiError(0, `Could not reach the backend API at ${BASE_URL}. Is it running? (${(err as Error).message})`);
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  products: () => request<Product[]>("/products"),
  machines: () => request<Machine[]>("/machines"),
  orders: () => request<Order[]>("/orders"),
  processingTimes: () => request<ProcessingTime[]>("/processing-times"),
  machineStatus: () => request<MachineStatusEntry[]>("/machine-status"),

  trainForecast: (product_ids?: string[]) =>
    request<TrainResponse>("/forecast/train", { method: "POST", body: JSON.stringify({ product_ids }) }),
  forecast: (product_id: string, horizon_days: number) =>
    request<ForecastResponse>("/forecast", { method: "POST", body: JSON.stringify({ product_id, horizon_days }) }),

  generatePlan: (horizon_days: number, product_ids?: string[]) =>
    request<PlanningGenerateResponse>("/planning/generate", {
      method: "POST",
      body: JSON.stringify({ horizon_days, product_ids }),
    }),
  decideApproval: (approval_id: number, decision: "approved" | "rejected", approved_quantity?: number, planner_note?: string) =>
    request<{ approval_id: number; decision: string }>("/planning/approve", {
      method: "POST",
      body: JSON.stringify({ approval_id, decision, approved_quantity, planner_note }),
    }),
  listApprovals: () => request<PlanningApproval[]>("/planning/approvals"),

  optimizeSchedule: (params: {
    horizon_days: number;
    objective_weights?: ObjectiveWeights;
    time_limit_seconds?: number;
    compare_baseline?: boolean;
    baseline_rule?: "EDD" | "FCFS";
    persist?: boolean;
  }) => request<ScheduleResponse>("/schedule/optimize", { method: "POST", body: JSON.stringify(params) }),
  reschedule: (params: { horizon_days: number; objective_weights?: ObjectiveWeights; time_limit_seconds?: number }) =>
    request<ScheduleResponse>("/schedule/reschedule", { method: "POST", body: JSON.stringify(params) }),
  scheduleRuns: () => request<Array<Record<string, unknown>>>("/schedule/runs"),

  runSimulation: (params: { disruption_type: string; params: Record<string, unknown>; horizon_days: number }) =>
    request<SimulationResult>("/simulation/run", { method: "POST", body: JSON.stringify(params) }),

  metrics: () => request<MetricsResponse>("/metrics"),
  reports: () => request<ReportsResponse>("/reports"),
};

export type { BaselineComparison };
