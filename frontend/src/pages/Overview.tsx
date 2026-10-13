import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Card, CardHeader, ErrorState, LoadingState, StatCard } from "../components/ui";
import { useTheme } from "../context/ThemeContext";
import { categoricalColor, chrome } from "../theme/palette";

export default function Overview() {
  const { theme } = useTheme();
  const { data, loading, error, refetch } = useAsync(() => api.metrics(), []);

  if (loading) return <LoadingState label="Loading dashboard metrics from the backend..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!data) return null;

  const utilData = Object.entries(data.machine_utilization_pct).map(([machine_id, pct]) => ({
    machine_id,
    pct,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Overview</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Live metrics computed by the backend scheduling and forecasting pipelines. Generated{" "}
          {new Date(data.generated_at).toLocaleString()}.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active Orders" value={data.total_active_orders} />
        <StatCard label="Planned Production Qty" value={data.planned_production_quantity.toLocaleString()} />
        <StatCard
          label="On-Time Delivery Rate"
          value={`${data.on_time_delivery_rate_pct}%`}
          tone={data.on_time_delivery_rate_pct >= 90 ? "good" : data.on_time_delivery_rate_pct >= 70 ? "warn" : "bad"}
        />
        <StatCard
          label="Delayed Orders"
          value={data.total_delayed_orders}
          tone={data.total_delayed_orders === 0 ? "good" : "warn"}
        />
        <StatCard label="Avg Machine Utilization" value={`${data.avg_machine_utilization_pct}%`} />
        <StatCard label="Production Backlog Qty" value={data.total_production_backlog_qty.toLocaleString()} />
        <StatCard
          label="Forecast Models Trained"
          value={`${data.demand_forecast_summary.trained_products}/${
            data.demand_forecast_summary.trained_products + data.demand_forecast_summary.untrained_products
          }`}
        />
        <StatCard label="Latest Schedule Status" value={data.schedule_status} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Machine Utilization" subtitle="% of available working time used, current planning horizon" />
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={utilData}>
              <CartesianGrid strokeDasharray="3 3" stroke={chrome("gridline", theme)} vertical={false} />
              <XAxis dataKey="machine_id" tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} />
              <YAxis tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} unit="%" />
              <Tooltip
                contentStyle={{ background: chrome("surface", theme), border: `1px solid ${chrome("gridline", theme)}`, fontSize: 12 }}
              />
              <Bar dataKey="pct" radius={[4, 4, 0, 0]} fill={categoricalColor(0, theme)} name="Utilization %" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <CardHeader title="Demand Forecast Summary" subtitle="Per-product model status (ACTUAL evaluation results)" />
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                  <th className="py-1.5">Product</th>
                  <th className="py-1.5">Trained</th>
                  <th className="py-1.5">Model MAE</th>
                  <th className="py-1.5">Baseline MAE</th>
                  <th className="py-1.5">Improvement</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.demand_forecast_summary.per_product).map(([pid, info]) => (
                  <tr key={pid} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1.5 font-medium">{pid}</td>
                    <td className="py-1.5">{info.trained ? "Yes" : "No"}</td>
                    <td className="py-1.5">{info.model_mae?.toFixed(2) ?? "—"}</td>
                    <td className="py-1.5">{info.baseline_mae?.toFixed(2) ?? "—"}</td>
                    <td className="py-1.5">
                      {info.improvement_over_baseline_mae_pct != null ? `${info.improvement_over_baseline_mae_pct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
