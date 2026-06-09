"use client";

import { ArrowRight, Check, Gavel, Scale, ShieldCheck, X } from "lucide-react";
import type { RunSummary } from "@/lib/api";
import { fmtUsd, fmtSeconds, statusBadge, decisionTone } from "@/lib/format";

function RubricRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted">{label}</span>
      <span
        className={`inline-flex items-center gap-1 ${ok ? "text-good" : "text-bad"}`}
      >
        {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
        {ok ? "pass" : "fail"}
      </span>
    </div>
  );
}

// The hero card: shows the eval-gate verdict (the money shot when it vetoes a
// confident-but-wrong patch) alongside the risk tier and the applied diff.
export default function EvalVerdictCard({ run }: { run: RunSummary }) {
  const evalFailed = !run.eval.passed;
  const escalated = run.risk.decision.toUpperCase() === "ESCALATE";

  return (
    <div
      className={`card p-4 ${
        evalFailed ? "ring-1 ring-bad/50" : escalated ? "ring-1 ring-warn/40" : ""
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">
            {run.seed_id ?? run.run_id.slice(0, 8)}
          </span>
          <span className="text-xs text-muted">{run.error_type}</span>
        </div>
        <span className={statusBadge(run.status)}>{run.status}</span>
      </div>

      <p className="mb-3 text-xs text-muted">{run.root_cause}</p>

      <div className="grid grid-cols-2 gap-3">
        {/* Eval gate */}
        <div className="rounded-lg border border-edge bg-panel2 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-body">
              <ShieldCheck className="h-3.5 w-3.5" />
              Arize eval-gate
            </span>
            <span
              className={`text-xs font-semibold ${
                run.eval.passed ? "text-good" : "text-bad"
              }`}
            >
              {run.eval.passed ? "PASS" : "VETO"}
            </span>
          </div>
          <div className="space-y-1">
            {Object.entries(run.eval.rubric).map(([k, v]) => (
              <RubricRow key={k} label={k} ok={Boolean(v)} />
            ))}
          </div>
          <div className="mt-2 text-[11px] text-faint">
            confidence {(run.eval.confidence * 100).toFixed(0)}% · {run.eval.model}
          </div>
        </div>

        {/* Risk tier */}
        <div className="rounded-lg border border-edge bg-panel2 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-body">
              <Scale className="h-3.5 w-3.5" />
              Risk tier
            </span>
            <span className={`text-xs font-semibold ${decisionTone(run.risk.decision)}`}>
              {run.risk.decision}
            </span>
          </div>
          <div className="space-y-1 text-[11px] text-muted">
            <div className="flex justify-between">
              <span>score</span>
              <span className="tabular-nums">{run.risk.score.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span>customs value</span>
              <span className="tabular-nums">{fmtUsd(run.customs_value)}</span>
            </div>
            {run.risk.hard_line ? (
              <div className="text-bad">$2,500 hard-line triggered</div>
            ) : null}
            {run.risk.reasons.slice(0, 2).map((r, i) => (
              <div key={i} className="truncate">
                · {r}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Applied diff */}
      {run.field_diff.length > 0 ? (
        <div className="mt-3">
          <div className="mb-1 text-[11px] uppercase tracking-wide text-faint">
            Patch applied
          </div>
          <div className="space-y-1">
            {run.field_diff.map((d, i) => (
              <div
                key={i}
                className="flex items-center gap-2 font-mono text-[11px]"
              >
                <span className="text-muted">{d.field}</span>
                <span className="text-bad line-through">
                  {String(d.before ?? "empty")}
                </span>
                <ArrowRight className="h-3 w-3 text-faint" />
                <span className="text-good">{String(d.after ?? "empty")}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Law citations / veto provenance */}
      {run.vetoed_lesson_ids.length > 0 ? (
        <div className="mt-3 flex items-center gap-1.5 rounded-md border border-veto/40 bg-veto/5 p-2 text-[11px] text-veto">
          <Gavel className="h-3.5 w-3.5 shrink-0" />
          Law-veto blocked {run.vetoed_lesson_ids.length} unsafe precedent(s).
        </div>
      ) : null}

      <div className="mt-3 flex items-center justify-between text-[11px] text-faint">
        <span>recovery {fmtSeconds(run.recovery_seconds)}</span>
        {run.demurrage_saved_usd > 0 ? (
          <span className="text-good">saved {fmtUsd(run.demurrage_saved_usd)}</span>
        ) : null}
      </div>
    </div>
  );
}
