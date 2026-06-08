"use client";

import type { Metrics } from "@/lib/api";
import { fmtUsd, fmtSeconds, fmtDays } from "@/lib/format";

function Counter({
  label,
  value,
  sub,
  tone = "text-white",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="card flex flex-col gap-1 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
      {sub ? <div className="text-xs text-slate-500">{sub}</div> : null}
    </div>
  );
}

export default function MetricsBar({ metrics }: { metrics: Metrics | null }) {
  if (!metrics) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="card h-24 animate-pulse p-4" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Counter
          label="Avg recovery time"
          value={fmtSeconds(metrics.avg_recovery_seconds)}
          sub={`vs broker baseline ${fmtDays(metrics.broker_baseline_seconds)}`}
          tone="text-accent"
        />
        <Counter
          label="Demurrage saved"
          value={fmtUsd(metrics.total_demurrage_saved_usd)}
          sub={`${metrics.resolved} shipments resolved`}
          tone="text-good"
        />
        <Counter
          label="Auto-resolved"
          value={`${metrics.pct_auto_resolved.toFixed(0)}%`}
          sub={`${metrics.auto_resolved}/${metrics.runs_total} · ${metrics.escalated} safe-escalations`}
          tone="text-white"
        />
        <Counter
          label="Self-heal speed-up"
          value={`${metrics.self_heal_speedup.toFixed(1)}×`}
          sub="repeat-error latency before/after learning"
          tone="text-veto"
        />
      </div>
      <p className="text-[11px] text-slate-500">{metrics.assumptions}</p>
    </div>
  );
}
