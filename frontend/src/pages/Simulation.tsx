import { useState } from "react";
import { Zap } from "lucide-react";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, Select, StatCard } from "../components/ui";
import type { SimulationResult } from "../api/types";

const DISRUPTION_TYPES = [
  { value: "machine_breakdown", label: "Machine Breakdown" },
  { value: "machine_restored", label: "Machine Restored to Service" },
  { value: "material_shortage", label: "Raw Material Shortage" },
  { value: "new_urgent_order", label: "New Urgent Order" },
  { value: "order_change", label: "Order Quantity/Deadline Change" },
  { value: "processing_time_change", label: "Processing Time Change" },
];

export default function Simulation() {
  const machinesQ = useAsync(() => api.machines(), []);
  const productsQ = useAsync(() => api.products(), []);
  const ordersQ = useAsync(() => api.orders(), []);

  const [disruptionType, setDisruptionType] = useState(DISRUPTION_TYPES[0].value);
  const [machineId, setMachineId] = useState("");
  const [durationHours, setDurationHours] = useState(6);
  const [materialId, setMaterialId] = useState("RM01");
  const [reduceQty, setReduceQty] = useState(1000);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState(50);
  const [dueDate, setDueDate] = useState("");
  const [orderId, setOrderId] = useState("");
  const [newQty, setNewQty] = useState(100);
  const [newDue, setNewDue] = useState("");
  const [newMinutesPerUnit, setNewMinutesPerUnit] = useState(5);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);

  const machines = machinesQ.data || [];
  const products = productsQ.data || [];
  const orders = ordersQ.data || [];

  function buildParams(): Record<string, unknown> {
    switch (disruptionType) {
      case "machine_breakdown":
        return {
          machine_id: machineId || machines[0]?.machine_id,
          start_datetime: new Date().toISOString().slice(0, 19),
          duration_hours: durationHours,
          reason: "Simulated scenario",
        };
      case "machine_restored":
        return { machine_id: machineId || machines[0]?.machine_id, as_of_datetime: new Date().toISOString().slice(0, 19) };
      case "material_shortage":
        return { material_id: materialId, reduce_by_qty: reduceQty };
      case "new_urgent_order":
        return {
          product_id: productId || products[0]?.product_id,
          quantity,
          due_date: dueDate || new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10),
          priority: "high",
        };
      case "order_change":
        return { order_id: orderId || orders[0]?.order_id, new_quantity: newQty, new_due_date: newDue || undefined };
      case "processing_time_change":
        return {
          product_id: productId || products[0]?.product_id,
          machine_id: machineId || machines[0]?.machine_id,
          new_minutes_per_unit: newMinutesPerUnit,
        };
      default:
        return {};
    }
  }

  async function runSimulation() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.runSimulation({ disruption_type: disruptionType, params: buildParams(), horizon_days: 14 });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (machinesQ.loading || productsQ.loading || ordersQ.loading) return <LoadingState label="Loading scenario data..." />;
  if (machinesQ.error) return <ErrorState message={machinesQ.error} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Scenario Simulation</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Simulate a disruption, recompute the schedule, and compare it against the schedule just before the event.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Disruption type">
            <Select value={disruptionType} onChange={setDisruptionType} options={DISRUPTION_TYPES} />
          </Field>

          {disruptionType === "machine_breakdown" && (
            <>
              <Field label="Machine">
                <Select value={machineId || machines[0]?.machine_id || ""} onChange={setMachineId} options={machines.map((m) => ({ value: m.machine_id, label: m.machine_id }))} />
              </Field>
              <Field label="Duration (hours)">
                <Select value={String(durationHours)} onChange={(v) => setDurationHours(Number(v))} options={[2, 4, 8, 24, 48].map((h) => ({ value: String(h), label: `${h}h` }))} />
              </Field>
            </>
          )}

          {disruptionType === "machine_restored" && (
            <Field label="Machine">
              <Select value={machineId || machines[0]?.machine_id || ""} onChange={setMachineId} options={machines.map((m) => ({ value: m.machine_id, label: m.machine_id }))} />
            </Field>
          )}

          {disruptionType === "material_shortage" && (
            <>
              <Field label="Material ID">
                <input className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={materialId} onChange={(e) => setMaterialId(e.target.value)} />
              </Field>
              <Field label="Reduce stock by">
                <input type="number" className="w-28 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={reduceQty} onChange={(e) => setReduceQty(Number(e.target.value))} />
              </Field>
            </>
          )}

          {(disruptionType === "new_urgent_order" || disruptionType === "processing_time_change") && (
            <Field label="Product">
              <Select value={productId || products[0]?.product_id || ""} onChange={setProductId} options={products.map((p) => ({ value: p.product_id, label: p.product_id }))} />
            </Field>
          )}
          {disruptionType === "new_urgent_order" && (
            <>
              <Field label="Quantity">
                <input type="number" className="w-24 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} />
              </Field>
              <Field label="Due date">
                <input type="date" className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </Field>
            </>
          )}

          {disruptionType === "order_change" && (
            <>
              <Field label="Order">
                <Select value={orderId || orders[0]?.order_id || ""} onChange={setOrderId} options={orders.map((o) => ({ value: o.order_id, label: `${o.order_id} (${o.product_id})` }))} />
              </Field>
              <Field label="New quantity">
                <input type="number" className="w-24 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={newQty} onChange={(e) => setNewQty(Number(e.target.value))} />
              </Field>
              <Field label="New due date">
                <input type="date" className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={newDue} onChange={(e) => setNewDue(e.target.value)} />
              </Field>
            </>
          )}

          {disruptionType === "processing_time_change" && (
            <>
              <Field label="Machine">
                <Select value={machineId || machines[0]?.machine_id || ""} onChange={setMachineId} options={machines.map((m) => ({ value: m.machine_id, label: m.machine_id }))} />
              </Field>
              <Field label="New minutes/unit">
                <input type="number" className="w-24 rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800" value={newMinutesPerUnit} onChange={(e) => setNewMinutesPerUnit(Number(e.target.value))} />
              </Field>
            </>
          )}

          <Button onClick={runSimulation} disabled={busy}>
            <Zap className="h-4 w-4" /> {busy ? "Running..." : "Run Simulation"}
          </Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={runSimulation} />}
      {busy && <LoadingState label="Recomputing schedule before and after the disruption..." />}

      {!busy && result && (
        <>
          <Card>
            <p className="text-sm text-slate-700 dark:text-slate-200">{result.description}</p>
          </Card>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Unscheduled Before" value={result.before.num_unscheduled} />
            <StatCard label="Unscheduled After" value={result.after.num_unscheduled} tone={result.after.num_unscheduled > result.before.num_unscheduled ? "bad" : "default"} />
            <StatCard label="Orders Changed" value={result.diff.changed_orders.length} />
            <StatCard label="Deadlines Newly At Risk" value={result.diff.deadlines_at_risk.length} tone={result.diff.deadlines_at_risk.length > 0 ? "bad" : "good"} />
          </div>

          <Card>
            <CardHeader title="What Changed" subtitle="Comparing the schedule immediately before vs. after the disruption" />
            {result.diff.changed_orders.length === 0 ? (
              <EmptyState label="No existing orders needed to move." />
            ) : (
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                      <th className="py-1.5">Order</th>
                      <th className="py-1.5">Change</th>
                      <th className="py-1.5">Old Machine</th>
                      <th className="py-1.5">New Machine</th>
                      <th className="py-1.5">New On-Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.diff.changed_orders.map((c, i) => (
                      <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="py-1.5 font-medium">{String(c.order_id)}</td>
                        <td className="py-1.5">{String(c.change)}</td>
                        <td className="py-1.5">{String(c.old_machine ?? "—")}</td>
                        <td className="py-1.5">{String(c.new_machine ?? "—")}</td>
                        <td className="py-1.5">
                          {"new_on_time" in c ? (
                            c.new_on_time ? <Badge tone="good">On time</Badge> : <Badge tone="bad">Late</Badge>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {result.diff.newly_unscheduled.length > 0 && (
            <Card>
              <CardHeader title="Newly Unscheduled" subtitle="Orders that could be scheduled before, but not after the disruption" />
              <ul className="space-y-1 text-sm">
                {result.diff.newly_unscheduled.map((u, i) => (
                  <li key={i} className="text-rose-600 dark:text-rose-400">
                    {String(u.order_id)} — {String(u.reason)}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      {!busy && !result && !error && <EmptyState label="Configure a disruption above and click 'Run Simulation'." />}
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
