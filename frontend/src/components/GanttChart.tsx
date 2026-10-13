import { useMemo } from "react";
import type { Machine, ScheduledJob } from "../api/types";
import { useTheme } from "../context/ThemeContext";
import { STATUS, categoricalColor } from "../theme/palette";

function fmtMinute(totalMinutes: number): string {
  const days = Math.floor(totalMinutes / 1440);
  const mins = totalMinutes % 1440;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `Day ${days + 1}, ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function GanttChart({ jobs, machines }: { jobs: ScheduledJob[]; machines: Machine[] }) {
  const { theme } = useTheme();
  const productIds = useMemo(() => Array.from(new Set(jobs.map((j) => j.product_id))).sort(), [jobs]);

  const maxMinute = useMemo(() => {
    const max = jobs.reduce((m, j) => Math.max(m, j.end_minute), 0);
    return Math.max(max, 1440);
  }, [jobs]);

  const dayLines = useMemo(() => {
    const days = Math.ceil(maxMinute / 1440);
    return Array.from({ length: days + 1 }, (_, i) => i * 1440);
  }, [maxMinute]);

  const jobsByMachine = useMemo(() => {
    const map: Record<string, ScheduledJob[]> = {};
    for (const m of machines) map[m.machine_id] = [];
    for (const j of jobs) {
      if (!map[j.machine_id]) map[j.machine_id] = [];
      map[j.machine_id].push(j);
    }
    return map;
  }, [jobs, machines]);

  if (jobs.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">No scheduled jobs to display.</p>;
  }

  return (
    <div>
      {/* Legend: status is never color-alone — icon + label pairing */}
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-slate-600 dark:text-slate-300">
        <LegendSwatch color={STATUS.good} label="On-time" />
        <LegendSwatch color={STATUS.critical} label="Late" />
        <span className="text-slate-400 dark:text-slate-500">
          Colors within a bar's border indicate product identity (see table below for exact mapping).
        </span>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[720px]">
          {/* Day gridline header */}
          <div className="relative mb-1 h-5 border-b border-slate-200 dark:border-slate-800">
            {dayLines.map((d) => (
              <div
                key={d}
                className="absolute top-0 text-[10px] text-slate-400 dark:text-slate-500"
                style={{ left: `${(d / maxMinute) * 100}%` }}
              >
                {fmtMinute(d).split(",")[0]}
              </div>
            ))}
          </div>

          {machines.map((machine) => (
            <div key={machine.machine_id} className="mb-2 flex items-center gap-2">
              <div className="w-32 shrink-0 truncate text-xs font-medium text-slate-600 dark:text-slate-300">
                {machine.machine_name}
              </div>
              <div className="relative h-8 flex-1 rounded-md bg-slate-100 dark:bg-slate-800/60">
                {dayLines.map((d) => (
                  <div
                    key={d}
                    className="absolute top-0 h-full w-px bg-slate-200 dark:bg-slate-700"
                    style={{ left: `${(d / maxMinute) * 100}%` }}
                  />
                ))}
                {(jobsByMachine[machine.machine_id] || []).map((job) => {
                  const left = (job.start_minute / maxMinute) * 100;
                  const width = Math.max(((job.end_minute - job.start_minute) / maxMinute) * 100, 0.6);
                  const productIdx = productIds.indexOf(job.product_id);
                  const borderColor = categoricalColor(productIdx, theme);
                  const fillColor = job.on_time ? STATUS.good : STATUS.critical;
                  return (
                    <div
                      key={job.order_id}
                      className="group absolute top-1 h-6 overflow-hidden rounded-[4px] border-2 px-1 text-[10px] leading-6 text-white shadow-sm"
                      style={{
                        left: `${left}%`,
                        width: `${width}%`,
                        backgroundColor: fillColor,
                        borderColor,
                        marginInline: "1px",
                      }}
                    >
                      <span className="truncate">{job.order_id}</span>
                      <div className="pointer-events-none absolute left-0 top-full z-10 mt-1 hidden w-56 rounded-md border border-slate-200 bg-white p-2 text-[11px] text-slate-700 shadow-lg group-hover:block dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                        <p className="font-semibold">{job.order_id} — {job.product_id}</p>
                        <p>Qty: {job.quantity}</p>
                        <p>Start: {fmtMinute(job.start_minute)}</p>
                        <p>End: {fmtMinute(job.end_minute)}</p>
                        <p>Due: {fmtMinute(job.due_minute)}</p>
                        <p className={job.on_time ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
                          {job.on_time ? "On time" : `Late by ${job.delay_minutes} min`}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
