import { useState } from "react";
import { Check, ChevronDown, ChevronUp, X } from "lucide-react";
import { api } from "../api/client";
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import type { PlanningRecommendation } from "../api/types";

export default function Planning() {
  const [horizon, setHorizon] = useState(14);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recs, setRecs] = useState<PlanningRecommendation[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<number, "approved" | "rejected">>({});

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.generatePlan(horizon);
      setRecs(res.recommendations);
      setDecisions({});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function decide(approvalId: number, decision: "approved" | "rejected", qty: number) {
    try {
      await api.decideApproval(approvalId, decision, qty);
      setDecisions((d) => ({ ...d, [approvalId]: decision }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Production Planning</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Converts forecast demand, confirmed orders, inventory, and material availability into explainable
            production recommendations.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Horizon (days)</label>
            <Select value={String(horizon)} onChange={(v) => setHorizon(Number(v))} options={[7, 14, 21, 30].map((h) => ({ value: String(h), label: `${h} days` }))} />
          </div>
          <Button onClick={generate} disabled={loading}>
            {loading ? "Generating..." : "Generate Recommendations"}
          </Button>
        </div>
      </div>

      {error && <ErrorState message={error} onRetry={generate} />}
      {loading && <LoadingState label="Computing net requirements..." />}

      {!loading && recs && recs.length === 0 && <EmptyState label="No products found." />}

      {!loading && recs && recs.length > 0 && (
        <div className="space-y-3">
          {recs.map((r) => {
            const isOpen = expanded === r.product_id;
            const decision = r.approval_id ? decisions[r.approval_id] : undefined;
            const hasShortage = r.material_checks.some((m) => m.shortage_qty > 0);
            return (
              <Card key={r.product_id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-slate-900 dark:text-slate-50">
                        {r.product_id} — {r.product_name}
                      </h3>
                      {hasShortage && <Badge tone="bad">Material shortage</Badge>}
                      {r.material_constrained_quantity != null && (
                        <Badge tone="warn">Constrained by materials</Badge>
                      )}
                      {decision === "approved" && <Badge tone="good">Approved</Badge>}
                      {decision === "rejected" && <Badge tone="bad">Rejected</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Source: {r.forecast_source}</p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-xs text-slate-500 dark:text-slate-400">Recommended Qty</p>
                      <p className="text-lg font-semibold text-indigo-600 dark:text-indigo-400">{r.recommended_quantity}</p>
                    </div>
                    {r.approval_id && !decision && (
                      <div className="flex gap-1.5">
                        <Button variant="primary" onClick={() => decide(r.approval_id!, "approved", r.recommended_quantity)}>
                          <Check className="h-3.5 w-3.5" /> Approve
                        </Button>
                        <Button variant="danger" onClick={() => decide(r.approval_id!, "rejected", r.recommended_quantity)}>
                          <X className="h-3.5 w-3.5" /> Reject
                        </Button>
                      </div>
                    )}
                    <button
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                      onClick={() => setExpanded(isOpen ? null : r.product_id)}
                    >
                      {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                    </button>
                  </div>
                </div>

                {isOpen && (
                  <div className="mt-4 border-t border-slate-100 pt-4 dark:border-slate-800">
                    <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <Fact label="Forecast Demand" value={r.forecast_qty} />
                      <Fact label="Confirmed Orders" value={r.confirmed_order_qty} />
                      <Fact label="Expected Demand" value={r.expected_demand} />
                      <Fact label="Safety Stock" value={r.safety_stock_qty} />
                      <Fact label="On-Hand Inventory" value={r.on_hand_inventory} />
                      <Fact label="Planned Receipts" value={r.planned_receipts} />
                      <Fact label="Net Requirement" value={r.net_requirement} />
                      <Fact label="Capacity Minutes Req." value={r.capacity_minutes_required} />
                    </div>
                    <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">{r.explanation}</p>
                    {r.material_checks.length > 0 && (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                            <th className="py-1">Material</th>
                            <th className="py-1">Required</th>
                            <th className="py-1">Available</th>
                            <th className="py-1">Shortage</th>
                          </tr>
                        </thead>
                        <tbody>
                          {r.material_checks.map((m) => (
                            <tr key={m.material_id} className="border-t border-slate-100 dark:border-slate-800">
                              <td className="py-1">{m.material_id}</td>
                              <td className="py-1">{m.required_qty.toFixed(1)}</td>
                              <td className="py-1">{m.available_qty.toFixed(1)}</td>
                              <td className={`py-1 ${m.shortage_qty > 0 ? "text-rose-600 dark:text-rose-400" : ""}`}>
                                {m.shortage_qty.toFixed(1)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {!loading && !recs && !error && <EmptyState label="Click 'Generate Recommendations' to begin." />}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2.5 dark:bg-slate-800/60">
      <p className="text-[10px] uppercase text-slate-500 dark:text-slate-400">{label}</p>
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">{value}</p>
    </div>
  );
}
