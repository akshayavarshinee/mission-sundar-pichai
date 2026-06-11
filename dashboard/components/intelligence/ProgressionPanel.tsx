"use client";

import { LineChart } from "lucide-react";
import type { ProgressionPoint } from "@/lib/api";
import ProgressionChart from "@/components/charts/ProgressionChart";

// Wraps the progression chart with a headline read-out and a plain-language
// legend so the "gets smarter over time" story is legible at a glance.
export default function ProgressionPanel({ points }: { points: ProgressionPoint[] }) {
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="section-title">
            <LineChart className="h-4 w-4 text-accent" />
            How ClearPort gets smarter over time
          </h2>
          <p className="mt-1 text-xs text-muted">
            Auto-resolve rate climbs as lessons accumulate — the self-improving loop, run by run.
          </p>
        </div>
        <div className="flex items-center gap-5 text-right">
          <Metric label="Auto-resolve">
            <span className="tabular-nums text-muted">{first ? first.cum_auto_pct.toFixed(0) : 0}%</span>
            <span className="text-faint"> → </span>
            <span className="tabular-nums text-accent">{last ? last.cum_auto_pct.toFixed(0) : 0}%</span>
          </Metric>
          <Metric label="Lessons">
            <span className="tabular-nums text-good">{last?.cum_lessons ?? 0}</span>
          </Metric>
          <Metric label="Runs">
            <span className="tabular-nums text-ink">{points.length}</span>
          </Metric>
        </div>
      </div>

      <div className="mt-3">
        <ProgressionChart points={points} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-sm bg-accent" /> auto-resolve %
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0 w-4 border-t-2 border-dashed border-veto" /> lessons learned
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-good" /> auto-cleared
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-accent" /> approved
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-warn" /> corrected
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border-2 border-veto" /> self-healed
        </span>
      </div>
    </section>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="text-sm font-semibold">{children}</div>
    </div>
  );
}
