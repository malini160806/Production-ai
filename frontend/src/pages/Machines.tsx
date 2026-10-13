import { useState } from "react";
import { AlertTriangle, Wrench } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import { useTheme } from "../context/ThemeContext";
import { categoricalColor, chrome } from "../theme/palette";

export default function Machines() {
  const { theme } = useTheme();
  const machinesQ = useAsync(() => api.machines(), []);
  const ptQ = useAsync(() => api.processingTimes(), []);
  const statusQ = useAsync(() => api.machineStatus(), []);
  const metricsQ = useAsync(() => api.metrics(), []);

  const [breakdownMachine, setBreakdownMachine] = useState<string>("");
  const [duration, setDuration] = useState(4);
  const [simResult, setSimResult] = useState<string | null>(null);
  const [simBusy, setSimBusy] = useState(false);

  if (machinesQ.loading || ptQ.loading || statusQ.loading) return <LoadingState label="Loading machine data..." />;
  if (machinesQ.error) return <ErrorState message={machinesQ.error} onRetry={machinesQ.refetch} />;

  const machines = machinesQ.data || [];
  const processingTimes = ptQ.data || [];
  const statusRows = statusQ.data || [];

  async function simulateBreakdown() {
    const machineId = breakdownMachine || machines[0]?.machine_id;
    if (!machineId) return;
    setSimBusy(true);
    setSimResult(null);
    try {
      const res = await api.runSimulation({
        disruption_type: "machine_breakdown",
        params: {
          machine_id: machineId,
          start_datetime: new Date().toISOString().slice(0, 19),
          duration_hours: duration,
          reason: "Simulated from Machine Management page",
        },
        horizon_days: 14,
      });
      setSimResult(
        `${res.description} Before: ${res.before.num_unscheduled} unscheduled. After: ${res.after.num_unscheduled} unscheduled, ${res.diff.changed_orders.length} orders changed.`,
      );
    } catch (e) {
      setSimResult(`Error: ${(e as Error).message}`);
    } finally {
      setSimBusy(false);
    }
  }

  const utilData = metricsQ.data
    ? Object.entries(metricsQ.data.machine_utilization_pct).map(([machine_id, pct]) => ({ machine_id, pct }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Machine Management</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Availability, processing capabilities, maintenance windows, and utilization.
        </p>
      </div>

      <Card>
        <CardHeader title="Machines" subtitle="Shift windows and cost" />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                <th className="py-1.5">ID</th>
                <th className="py-1.5">Name</th>
                <th className="py-1.5">Type</th>
                <th className="py-1.5">Capacity/hr</th>
                <th className="py-1.5">Shift</th>
                <th className="py-1.5">Cost/hr</th>
                <th className="py-1.5">Products</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => {
                const products = processingTimes.filter((p) => p.machine_id === m.machine_id);
                return (
                  <tr key={m.machine_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1.5 font-medium">{m.machine_id}</td>
                    <td className="py-1.5">{m.machine_name}</td>
                    <td className="py-1.5">{m.machine_type}</td>
                    <td className="py-1.5">{m.capacity_units_per_hour}</td>
                    <td className="py-1.5">
                      {Math.floor(m.shift_start_min / 60)}:{String(m.shift_start_min % 60).padStart(2, "0")} –{" "}
                      {Math.floor(m.shift_end_min / 60)}:{String(m.shift_end_min % 60).padStart(2, "0")}
                    </td>
                    <td className="py-1.5">${m.cost_per_hour.toFixed(2)}</td>
                    <td className="py-1.5">
                      <div className="flex flex-wrap gap-1">
                        {products.map((p) => (
                          <Badge key={p.product_id}>{p.product_id}</Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Utilization" subtitle="% of available working time used, current horizon" />
          {metricsQ.loading ? (
            <LoadingState />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={utilData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chrome("gridline", theme)} vertical={false} />
                <XAxis dataKey="machine_id" tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} />
                <YAxis tick={{ fontSize: 12, fill: chrome("mutedInk", theme) }} unit="%" />
                <Tooltip contentStyle={{ background: chrome("surface", theme), border: `1px solid ${chrome("gridline", theme)}`, fontSize: 12 }} />
                <Bar dataKey="pct" radius={[4, 4, 0, 0]} fill={categoricalColor(0, theme)} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card>
          <CardHeader title="Maintenance / Downtime Windows" subtitle="From machine_status.csv" />
          {statusRows.length === 0 ? (
            <EmptyState label="No maintenance windows scheduled." />
          ) : (
            <ul className="space-y-2">
              {statusRows.map((s, i) => (
                <li key={i} className="flex items-center gap-2 rounded-lg bg-slate-50 p-2.5 text-sm dark:bg-slate-800/60">
                  <Wrench className="h-4 w-4 shrink-0 text-amber-500" />
                  <span className="font-medium">{s.machine_id}</span>
                  <Badge tone={s.status === "available" ? "good" : "warn"}>{s.status}</Badge>
                  {s.status_start && (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {new Date(s.status_start).toLocaleString()} → {new Date(s.status_end).toLocaleString()}
                    </span>
                  )}
                  {s.reason && <span className="text-xs text-slate-400">({s.reason})</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Simulate Breakdown" subtitle="Quick disruption test — full scenario tooling is on the Scenario Simulation page" />
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Machine</label>
            <Select
              value={breakdownMachine || machines[0]?.machine_id || ""}
              onChange={setBreakdownMachine}
              options={machines.map((m) => ({ value: m.machine_id, label: `${m.machine_id} — ${m.machine_name}` }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Duration (hours)</label>
            <Select value={String(duration)} onChange={(v) => setDuration(Number(v))} options={[2, 4, 8, 24].map((h) => ({ value: String(h), label: `${h}h` }))} />
          </div>
          <Button onClick={simulateBreakdown} disabled={simBusy} variant="danger">
            <AlertTriangle className="h-4 w-4" /> {simBusy ? "Simulating..." : "Simulate Breakdown Now"}
          </Button>
        </div>
        {simResult && <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{simResult}</p>}
      </Card>
    </div>
  );
}
