import { useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, Select, StatCard } from "../components/ui";
import type { ScheduleResponse } from "../api/types";
import { GanttChart } from "../components/GanttChart";
import { downloadCsv } from "../utils/csv";

export default function Scheduling() {
  const { data: machines, loading: loadingMachines, error: machinesError } = useAsync(() => api.machines(), []);

  const [horizon, setHorizon] = useState(14);
  const [timeLimit, setTimeLimit] = useState(15);
  const [baselineRule, setBaselineRule] = useState<"EDD" | "FCFS">("EDD");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScheduleResponse | null>(null);

  async function run(persist: boolean) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.optimizeSchedule({
        horizon_days: horizon,
        time_limit_seconds: timeLimit,
        compare_baseline: true,
        baseline_rule: baselineRule,
        persist,
      });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (loadingMachines) return <LoadingState label="Loading machines..." />;
  if (machinesError) return <ErrorState message={machinesError} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Production Scheduling</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            OR-Tools CP-SAT constraint-based scheduling with a traditional baseline comparison.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Horizon (days)">
            <Select value={String(horizon)} onChange={(v) => setHorizon(Number(v))} options={[7, 14, 21, 30].map((h) => ({ value: String(h), label: `${h}d` }))} />
          </Field>
          <Field label="Solver time limit (s)">
            <Select value={String(timeLimit)} onChange={(v) => setTimeLimit(Number(v))} options={[5, 10, 15, 30, 60].map((h) => ({ value: String(h), label: `${h}s` }))} />
          </Field>
          <Field label="Baseline rule">
            <Select value={baselineRule} onChange={(v) => setBaselineRule(v as "EDD" | "FCFS")} options={[{ value: "EDD", label: "Earliest Due Date" }, { value: "FCFS", label: "First-Come-First-Served" }]} />
          </Field>
          <Button onClick={() => run(true)} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> {loading ? "Solving..." : "Optimize Schedule"}
          </Button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={() => run(true)} />}
      {loading && <LoadingState label={`Running CP-SAT solver (time limit ${timeLimit}s)...`} />}

      {!loading && result && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label="Solver Status"
              value={result.status}
              tone={result.status === "OPTIMAL" ? "good" : result.status === "FEASIBLE" ? "warn" : "bad"}
              sublabel={result.status === "FEASIBLE" ? "Feasible, not proven optimal within time limit" : undefined}
            />
            <StatCard label="On-Time Delivery" value={`${result.metrics.on_time_delivery_pct}%`} />
            <StatCard label="Scheduled / Unscheduled" value={`${result.metrics.num_scheduled} / ${result.metrics.num_unscheduled}`} />
            <StatCard label="Makespan (min)" value={result.makespan_minutes} />
          </div>

          {result.baseline_comparison && (
            <Card>
              <CardHeader title="Baseline vs. Optimized Comparison" subtitle={`Baseline rule: ${baselineRule}. Figures computed from real runs over the same orders/machines/constraints.`} />
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                      <th className="py-1.5">Metric</th>
                      <th className="py-1.5">Baseline ({baselineRule})</th>
                      <th className="py-1.5">Optimized (CP-SAT)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <Row label="On-time delivery %" a={result.baseline_comparison.baseline.on_time_delivery_pct} b={result.baseline_comparison.optimized.on_time_delivery_pct} />
                    <Row label="Total tardiness (min)" a={result.baseline_comparison.baseline.total_tardiness_minutes} b={result.baseline_comparison.optimized.total_tardiness_minutes} />
                    <Row label="Makespan (min)" a={result.baseline_comparison.baseline.makespan_minutes} b={result.baseline_comparison.optimized.makespan_minutes} />
                    <Row label="Unscheduled orders" a={result.baseline_comparison.baseline.num_unscheduled} b={result.baseline_comparison.optimized.num_unscheduled} />
                    <Row label="Solve time (s)" a={result.baseline_comparison.baseline.solve_time_seconds} b={result.baseline_comparison.optimized.solve_time_seconds} />
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">{result.baseline_comparison.note}</p>
            </Card>
          )}

          <Card>
            <CardHeader title="Machine Timeline" subtitle="Gantt-style view of all scheduled jobs, grouped by machine" />
            <GanttChart jobs={result.scheduled} machines={machines || []} />
          </Card>

          <Card>
            <CardHeader
              title="Scheduled Jobs"
              action={
                <Button variant="secondary" onClick={() => downloadCsv("schedule.csv", result.scheduled)}>
                  <Download className="h-3.5 w-3.5" /> Export CSV
                </Button>
              }
            />
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                    <th className="py-1.5">Order</th>
                    <th className="py-1.5">Product</th>
                    <th className="py-1.5">Qty</th>
                    <th className="py-1.5">Machine</th>
                    <th className="py-1.5">Start</th>
                    <th className="py-1.5">End</th>
                    <th className="py-1.5">Due</th>
                    <th className="py-1.5">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.scheduled.map((j) => (
                    <tr key={j.order_id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1.5 font-medium">{j.order_id}</td>
                      <td className="py-1.5">{j.product_id}</td>
                      <td className="py-1.5">{j.quantity}</td>
                      <td className="py-1.5">{j.machine_id}</td>
                      <td className="py-1.5">{new Date(j.start_datetime).toLocaleString()}</td>
                      <td className="py-1.5">{new Date(j.end_datetime).toLocaleString()}</td>
                      <td className="py-1.5">{new Date(j.due_datetime).toLocaleDateString()}</td>
                      <td className="py-1.5">
                        {j.on_time ? <Badge tone="good">On time</Badge> : <Badge tone="bad">Late {j.delay_minutes}m</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardHeader title="Unscheduled Orders" subtitle="Orders the solver could not fit, with the reason" />
            {result.unscheduled.length === 0 ? (
              <EmptyState label="All orders were successfully scheduled." />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                    <th className="py-1.5">Order</th>
                    <th className="py-1.5">Product</th>
                    <th className="py-1.5">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.unscheduled.map((u) => (
                    <tr key={u.order_id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1.5 font-medium">{u.order_id}</td>
                      <td className="py-1.5">{u.product_id}</td>
                      <td className="py-1.5 text-slate-500 dark:text-slate-400">{u.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}

      {!loading && !result && !error && <EmptyState label="Click 'Optimize Schedule' to run the solver." />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">{label}</label>
      {children}
    </div>
  );
}

function Row({ label, a, b }: { label: string; a: number; b: number }) {
  const better = b <= a;
  return (
    <tr className="border-t border-slate-100 dark:border-slate-800">
      <td className="py-1.5">{label}</td>
      <td className="py-1.5">{a}</td>
      <td className={`py-1.5 font-medium ${better ? "text-emerald-600 dark:text-emerald-400" : "text-slate-700 dark:text-slate-200"}`}>{b}</td>
    </tr>
  );
}
