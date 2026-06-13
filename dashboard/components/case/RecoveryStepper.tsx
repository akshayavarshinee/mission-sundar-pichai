"use client";

import {
  ArrowRight,
  BadgeCheck,
  Brain,
  Check,
  FileWarning,
  Gavel,
  PenLine,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Truck,
  X,
} from "lucide-react";
import type { RunSummary } from "@/lib/api";
import { fmtSeconds, fmtUsd } from "@/lib/format";
import {
  contentsLabel,
  decisionLabel,
  errorBlurb,
  errorLabel,
  toneSoft,
} from "@/lib/shipment";

type StepTone = "good" | "warn" | "bad" | "veto" | "accent" | "muted";

function Step({
  icon: Icon,
  title,
  badge,
  tone,
  isLast,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  badge?: React.ReactNode;
  tone: StepTone;
  isLast?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="relative flex gap-4 pb-5 last:pb-0">
      {!isLast ? (
        <span className="absolute left-[19px] top-10 bottom-0 w-px bg-edge" aria-hidden />
      ) : null}
      <span
        className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${toneSoft[tone]}`}
      >
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1 pt-1">
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {badge}
        </div>
        {children}
      </div>
    </li>
  );
}

function RubricRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted">{label}</span>
      <span className={`inline-flex items-center gap-1 ${ok ? "text-good" : "text-bad"}`}>
        {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
        {ok ? "pass" : "fail"}
      </span>
    </div>
  );
}

const RUBRIC_LABELS: Record<string, string> = {
  structural_match: "Structure matches accepted filings",
  required_fields_ok: "Required fields present",
  value_sanity: "Declared value is sane",
  law_consistent: "Consistent with customs law",
};

export default function RecoveryStepper({ run }: { run: RunSummary }) {
  const evalPassed = run.eval.passed;
  const escalated = run.risk.decision.toUpperCase() === "HUMAN";
  const cleared = ["AUTO_RESOLVED", "HUMAN_APPROVED", "HUMAN_CORRECTED"].includes(run.status);

  return (
    <ol className="card p-5">
      {/* 1 — Rejected */}
      <Step
        icon={FileWarning}
        title="Rejected at customs"
        tone="bad"
        badge={
          <span className="rounded-full border border-edge bg-panel2 px-2 py-0.5 text-[11px] text-muted">
            {run.caught_by}
          </span>
        }
      >
        <p className="mb-2 text-xs text-muted">{errorBlurb(run.error_type)}</p>
        <div className="rounded-lg border border-bad/20 bg-bad/5 p-2.5 font-mono text-[11px] text-bad">
          {run.raw_error}
        </div>
      </Step>

      {/* 2 — Diagnosed */}
      <Step
        icon={Brain}
        title="Diagnosed the cause"
        tone="accent"
        badge={
          <span className="text-[11px] text-faint">
            {(run.diagnosis.confidence * 100).toFixed(0)}% confident
          </span>
        }
      >
        <p className="mb-2 text-sm text-body">{run.root_cause}</p>
        {run.diagnosis.confidence_basis ? (
          <p className="mb-2 text-[11px] text-faint">{run.diagnosis.confidence_basis}</p>
        ) : null}
        {run.law_citations.length > 0 ? (
          <div className="space-y-1">
            {run.law_citations.slice(0, 3).map((c, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-md border border-edge bg-panel2 p-2 text-[11px]"
              >
                <Gavel className="mt-0.5 h-3 w-3 shrink-0 text-veto" />
                <span className="text-muted">
                  <span className="font-medium text-body">
                    {c.source} {c.ref}
                  </span>{" "}
                  — {c.text}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </Step>

      {/* 3 — Patched */}
      <Step icon={PenLine} title="Patched the declaration" tone="accent">
        {run.field_diff.length > 0 ? (
          <div className="space-y-1.5">
            {run.field_diff.map((d, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="font-mono text-muted">{d.field}</span>
                <span className="rounded bg-bad/10 px-1.5 py-0.5 font-mono text-bad line-through">
                  {String(d.before ?? "empty")}
                </span>
                <ArrowRight className="h-3 w-3 text-faint" />
                <span className="rounded bg-good/10 px-1.5 py-0.5 font-mono text-good">
                  {String(d.after ?? "empty")}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted">No field changes were required.</p>
        )}
        {run.rationale ? (
          <p className="mt-2 text-[11px] text-faint">{run.rationale}</p>
        ) : null}
      </Step>

      {/* 4 — Eval-gate (hero) */}
      <Step
        icon={evalPassed ? ShieldCheck : ShieldAlert}
        title="Arize eval-gate"
        tone={evalPassed ? "good" : "veto"}
        badge={
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
              evalPassed
                ? "border-good/30 bg-good/10 text-good"
                : "border-veto/40 bg-veto/10 text-veto"
            }`}
          >
            {evalPassed ? "PASS" : "VETO"}
          </span>
        }
      >
        <div
          className={`rounded-lg border p-3 ${
            evalPassed ? "border-edge bg-panel2" : "border-veto/40 bg-veto/5"
          }`}
        >
          {!evalPassed ? (
            <p className="mb-2 text-xs font-medium text-veto">
              The judge blocked this fix against historically-accepted shipments — no money was
              spent.
            </p>
          ) : null}
          <div className="space-y-1">
            {Object.entries(run.eval.rubric).map(([k, v]) => (
              <RubricRow key={k} label={RUBRIC_LABELS[k] ?? k} ok={Boolean(v)} />
            ))}
          </div>
          <div className="mt-2 border-t border-edge pt-2 text-[11px] text-faint">
            {(run.eval.confidence * 100).toFixed(0)}% confidence · judged by {run.eval.model}
          </div>
        </div>
        {run.vetoed_lesson_ids.length > 0 ? (
          <div className="mt-2 flex items-center gap-1.5 rounded-md border border-veto/40 bg-veto/5 p-2 text-[11px] text-veto">
            <Gavel className="h-3.5 w-3.5 shrink-0" />
            Law-veto blocked {run.vetoed_lesson_ids.length} unsafe precedent(s) from memory.
          </div>
        ) : null}
      </Step>

      {/* 5 — Decision */}
      <Step
        icon={Scale}
        title="Risk decision"
        tone={escalated ? "warn" : "good"}
        badge={
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
              escalated
                ? "border-warn/30 bg-warn/10 text-warn"
                : "border-good/30 bg-good/10 text-good"
            }`}
          >
            {decisionLabel(run.risk.decision)}
          </span>
        }
      >
        <div className="grid grid-cols-3 gap-2 text-center">
          {(["value", "danger", "confidence"] as const).map((k) => (
            <div key={k} className="rounded-lg border border-edge bg-panel2 p-2">
              <div className="text-sm font-semibold tabular-nums text-body">
                {run.risk.components[k].toFixed(2)}
              </div>
              <div className="text-[10px] uppercase tracking-wide text-faint">{k}</div>
            </div>
          ))}
        </div>
        {run.risk.hard_line ? (
          <div className="mt-2 rounded-md border border-warn/30 bg-warn/5 p-2 text-[11px] text-warn">
            Crossed the $2,500 hard line — escalated regardless of confidence.
          </div>
        ) : null}
        {run.risk.reasons.length > 0 ? (
          <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
            {run.risk.reasons.slice(0, 3).map((r, i) => (
              <li key={i}>· {r}</li>
            ))}
          </ul>
        ) : null}
      </Step>

      {/* 6 — Outcome */}
      <Step
        icon={cleared ? BadgeCheck : escalated ? Sparkles : Truck}
        title="Outcome"
        tone={cleared ? "good" : escalated ? "warn" : "bad"}
        isLast
      >
        {cleared ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <span className="inline-flex items-center gap-1.5 font-medium text-good">
              <Check className="h-3.5 w-3.5" />
              {run.label_id ? "Label purchased" : "Customs cleared"} ({errorLabel(run.error_type)} resolved)
            </span>
            <span className="text-muted">recovered in {fmtSeconds(run.recovery_seconds)}</span>
            {run.demurrage_saved_usd > 0 ? (
              <span className="text-good">saved {fmtUsd(run.demurrage_saved_usd)} in demurrage</span>
            ) : null}
          </div>
        ) : run.status === "AWAITING_APPROVAL" ? (
          <p className="text-xs text-warn">
            Paused for your sign-off — review and approve, correct, or reject below.
          </p>
        ) : (
          <p className="text-xs text-bad">This shipment was not cleared.</p>
        )}
        {run.label_id ? (
          <p className="mt-1 font-mono text-[11px] text-faint">label {run.label_id}</p>
        ) : null}
        {cleared && !run.label_id && run.cleared_note ? (
          <p className="mt-1 text-[11px] text-muted">{run.cleared_note}</p>
        ) : null}
        <p className="mt-1 text-[11px] text-faint">
          {contentsLabel(run.contents_type)} · outcome written to episodic memory for next time.
        </p>
      </Step>
    </ol>
  );
}
