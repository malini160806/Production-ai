import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Download, PlayCircle } from "lucide-react";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, Select } from "../components/ui";
import type { ForecastResponse, TrainResult } from "../api/types";
import { downloadCsv } from "../utils/csv";
import { useTheme } from "../context/ThemeContext";
import { categoricalColor, chrome } from "../theme/palette";

export default function Forecasting() {
  const { theme } = useTheme();
  const { data: products, loading: loadingProducts, error: productsError } = useAsync(() => api.products(), []);

  const [selectedProduct, setSelectedProduct] = useState<string>("");
  const [horizon, setHorizon] = useState(14);
  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [forecastResult, setForecastResult] = useState<ForecastResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effectiveProduct = selectedProduct || products?.[0]?.product_id || "";

  async function handleTrain() {
    if (!effectiveProduct) return;
    setTraining(true);
    setError(null);
    try {
      const res = await api.trainForecast([effectiveProduct]);
      setTrainResult(res.results[0] ?? null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setTraining(false);
    }
  }

  async function handleForecast() {
    if (!effectiveProduct) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.forecast(effectiveProduct, horizon);
      setForecastResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loadingProducts) return <LoadingState label="Loading products..." />;
  if (productsError) return <ErrorState message={productsError} />;

  const chartData = trainResult?.test_comparison?.map((p) => ({
    date: p.date,
    Actual: p.actual,
    "Model Prediction": p.model_pred,
    "Baseline (last week)": p.baseline_pred,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Demand Forecasting</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          XGBoost demand forecasts with chronological train/validation/test evaluation against a naive baseline.
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Product</label>
            <Select
              value={effectiveProduct}
              onChange={setSelectedProduct}
              options={(products || []).map((p) => ({ value: p.product_id, label: `${p.product_id} — ${p.product_name}` }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Forecast horizon (days)</label>
            <Select
              value={String(horizon)}
              onChange={(v) => setHorizon(Number(v))}
              options={[7, 14, 21, 30].map((h) => ({ value: String(h), label: `${h} days` }))}
            />
          </div>
          <Button onClick={handleTrain} disabled={training} variant="secondary">
            <PlayCircle className="h-4 w-4" /> {training ? "Training..." : "Train / Evaluate Model"}
          </Button>
          <Button onClick={handleForecast} disabled={busy}>
            {busy ? "Forecasting..." : "Get Forecast"}
          </Button>
        </div>
        {error && <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      </Card>

      {trainResult && !trainResult.skipped && trainResult.model_metrics && (
        <Card>
          <CardHeader
            title="Actual vs. Predicted Demand (chronological test split)"
            subtitle="Computed from a real holdout evaluation — not a hypothetical scenario"
          />
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Model MAE" value={trainResult.model_metrics.mae.toFixed(2)} />
            <Metric label="Model RMSE" value={trainResult.model_metrics.rmse?.toFixed(2) ?? "—"} />
            <Metric label="Baseline MAE" value={trainResult.baseline_metrics?.mae.toFixed(2) ?? "—"} />
            <Metric
              label="Improvement vs Baseline"
              value={`${trainResult.improvement_over_baseline_mae_pct ?? 0}%`}
              good={(trainResult.improvement_over_baseline_mae_pct ?? 0) > 0}
            />
          </div>
          {chartData && chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chrome("gridline", theme)} vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: chrome("mutedInk", theme) }} />
                <YAxis tick={{ fontSize: 11, fill: chrome("mutedInk", theme) }} />
                <Tooltip contentStyle={{ background: chrome("surface", theme), border: `1px solid ${chrome("gridline", theme)}`, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="Actual" stroke={categoricalColor(0, theme)} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Model Prediction" stroke={categoricalColor(2, theme)} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Baseline (last week)" stroke={categoricalColor(1, theme)} strokeWidth={2} strokeDasharray="4 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState label="No test-split comparison available." />
          )}
        </Card>
      )}
      {trainResult?.skipped && (
        <Card>
          <p className="text-sm text-amber-600 dark:text-amber-400">Model not trained: {trainResult.error}</p>
        </Card>
      )}

      <Card>
        <CardHeader
          title={`Forecast — next ${horizon} days`}
          subtitle="Recursive multi-step forecast using the trained model (or a clearly-labelled fallback if untrained)"
          action={
            forecastResult?.forecast?.length ? (
              <Button
                variant="secondary"
                onClick={() => downloadCsv(`forecast_${effectiveProduct}.csv`, forecastResult.forecast)}
              >
                <Download className="h-3.5 w-3.5" /> Export CSV
              </Button>
            ) : undefined
          }
        />
        {!forecastResult && <EmptyState label="Click 'Get Forecast' to generate a forecast for the selected product." />}
        {forecastResult && forecastResult.status !== "ok" && (
          <p className="text-sm text-amber-600 dark:text-amber-400">{forecastResult.message}</p>
        )}
        {forecastResult?.status === "ok" && (
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 dark:text-slate-400">
                  <th className="py-1.5">Date</th>
                  <th className="py-1.5">Predicted Quantity</th>
                </tr>
              </thead>
              <tbody>
                {forecastResult.forecast.map((p) => (
                  <tr key={p.date} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1.5">{p.date}</td>
                    <td className="py-1.5 font-medium">{p.predicted_qty}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
      <p className="text-[11px] uppercase text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${good ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-slate-50"}`}>
        {value}
      </p>
    </div>
  );
}
