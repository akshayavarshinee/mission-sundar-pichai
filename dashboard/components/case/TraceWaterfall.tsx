"use client";

import { Activity, ExternalLink } from "lucide-react";
import type { RunTrace } from "@/lib/api";
import { phoenixTraceUrl } from "@/lib/api";

const STEP_LABELS: Record<string, string> = {
  recall: "Recall memory",
  diagnose: "Diagnose",
  patch: "Patch",
  verify: "Eval-gate",
  decide: "Risk decision",
  act: "Execute",
  learn: "Learn",
};

export default function TraceWaterfall({ trace }: { trace: RunTrace | null }) {
  return (
    <div className="card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="section-title">
          <Activity className="h-4 w-4 text-accent" />
          Execution trace
        </h2>
        <a
          href={phoenixTraceUrl()}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
        >
          Open in Phoenix
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {!trace || trace.steps.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted">No trace recorded.</p>
      ) : (
        <>
          <div className="space-y-2">
            {trace.steps.map((s, i) => {
              const pct = trace.total_ms > 0 ? (s.duration_ms / trace.total_ms) * 100 : 0;
              return (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <div className="w-24 shrink-0 truncate text-muted" title={s.detail || s.name}>
                    {STEP_LABELS[s.name] ?? s.name}
                  </div>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-panel2">
                    <div
                      className="h-full rounded-full bg-accent/70"
                      style={{ width: `${Math.max(pct, 2)}%` }}
                    />
                  </div>
                  <div className="w-14 shrink-0 text-right font-mono text-[11px] tabular-nums text-faint">
                    {s.duration_ms.toFixed(0)} ms
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 border-t border-edge pt-2 text-right text-[11px] text-faint">
            total {trace.total_ms.toFixed(0)} ms · {trace.steps.length} spans
          </div>
        </>
      )}
    </div>
  );
}
