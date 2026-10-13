import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download } from "lucide-react";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Button, Card, CardHeader, ErrorState, LoadingState, StatCard } from "../components/ui";
import { downloadCsv } from "../utils/csv";
import { useTheme } from "../context/ThemeContext";
import { categoricalColor, chrome } from "../theme/palette";

export default function Reports() {
  const { theme } = useTheme();
  const { data, loading, error, refetch } = useAsync(() => api.reports(), []);

  if (loading) return <LoadingState label="Generating report from live data..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;

  const utilData = Object.entries(data.machine_utilization).map(([machine_id, pct]) => ({ machine_id, pct }));
  const forecastRows = Object.entries(data.forecast_summary.per_product).map(([product_id, info]) => ({
    product_id,
    trained: info.trained,
    model_mae: info.model_mae ?? "",
    baseline_mae: info.baseline_mae ?? "",
    improvement_pct: info.improvement_over_baseline_mae_pct ?? "",
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Reports</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Generated {new Date(data.generated_at).toLocaleString()}. All figures below are computed from live
            backend runs, not hypothetical.
          </p>
        </div>
        <Button variant="secondary" onClick={() => downloadCsv("forecast_report.csv", forecastRows)}>
          <Download className="h-3.5 w-3.5" /> Export Forecast CSV
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="On-Time Delivery" value={`${data.on_time_delivery_pct}%`} />
        <StatCard label="Total Tardiness (min)" value={data.total_tardiness_minutes} />
        <StatCard label="Scheduled / Unscheduled" value={`${data.schedule_summary.num_scheduled} / ${data.schedule_summary.num_unscheduled}`} />
        <StatCard label="Makespan (min)" value={data.schedule_summary.makespan_minutes} />
      </div>

      <Card>
        <CardHeader title="Machine Utilization" />
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={utilData}>
            <CartesianGrid strokeDasharray="3 3" stroke={chrome("gridline", theme)} vertical={false} />
            <XAxis dataKey="machine_id" tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} />
            <YAxis tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} unit="%" />
            <Tooltip contentStyle={{ background: chrome("surface", theme), border: `1px solid ${chrome("gridline", theme)}`, fontSize: 12 }} />
            <Bar dataKey="pct" radius={[4, 4, 0, 0]} fill={categoricalColor(0, theme)} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {data.baseline_vs_optimized && (
        <Card>
          <CardHeader title="Baseline vs. Optimized" subtitle={data.baseline_vs_optimized.note} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                  <th className="py-1.5">Metric</th>
                  <th className="py-1.5">Baseline</th>
                  <th className="py-1.5">Optimized</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1.5">On-time delivery %</td>
                  <td className="py-1.5">{data.baseline_vs_optimized.baseline.on_time_delivery_pct}</td>
                  <td className="py-1.5 font-medium">{data.baseline_vs_optimized.optimized.on_time_delivery_pct}</td>
                </tr>
                <tr className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1.5">Total tardiness (min)</td>
                  <td className="py-1.5">{data.baseline_vs_optimized.baseline.total_tardiness_minutes}</td>
                  <td className="py-1.5 font-medium">{data.baseline_vs_optimized.optimized.total_tardiness_minutes}</td>
                </tr>
                <tr className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-1.5">Makespan (min)</td>
                  <td className="py-1.5">{data.baseline_vs_optimized.baseline.makespan_minutes}</td>
                  <td className="py-1.5 font-medium">{data.baseline_vs_optimized.optimized.makespan_minutes}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Forecast Model Summary" />
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
              <th className="py-1.5">Product</th>
              <th className="py-1.5">Trained</th>
              <th className="py-1.5">Model MAE</th>
              <th className="py-1.5">Baseline MAE</th>
              <th className="py-1.5">Improvement %</th>
            </tr>
          </thead>
          <tbody>
            {forecastRows.map((r) => (
              <tr key={r.product_id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1.5 font-medium">{r.product_id}</td>
                <td className="py-1.5">{r.trained ? "Yes" : "No"}</td>
                <td className="py-1.5">{r.model_mae}</td>
                <td className="py-1.5">{r.baseline_mae}</td>
                <td className="py-1.5">{r.improvement_pct}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <CardHeader title="Notes & Assumptions" />
        <ul className="list-inside list-disc space-y-1 text-sm text-slate-600 dark:text-slate-300">
          {data.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
