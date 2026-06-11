"use client";

import { Scale, ShieldCheck, Sparkles } from "lucide-react";
import type { EvalGateIntel } from "@/lib/api";
import Donut from "@/components/charts/Donut";

// The conscience: a Phoenix-traced verdict gates every recovery, and customs
// law holds a hard veto over anything experience has learned.
export default function EvalGatePanel({ gate }: { gate: EvalGateIntel }) {
  const ratio = gate.total ? gate.passed / gate.total : 0;

  return (
    <section className="card p-5">
      <h2 className="section-title">
        <ShieldCheck className="h-4 w-4 text-good" />
        Eval-gate — every fix is checked before it ships
      </h2>
      <p className="mt-1 text-xs text-muted">
        A Phoenix-traced verdict gates each recovery; law can veto a learned shortcut outright.
      </p>

      <div className="mt-3 flex items-center gap-5">
        <div className="shrink-0">
          <Donut
            ratio={ratio}
            centerValue={`${gate.pass_rate.toFixed(0)}%`}
            centerLabel="pass-rate"
            valueClass="text-good"
            trackClass="text-warn/25"
          />
        </div>
        <dl className="grid flex-1 grid-cols-2 gap-3">
          <Stat label="Passed" value={gate.passed} tone="text-good" />
          <Stat label="Held back" value={gate.failed} tone="text-warn" />
          <Stat label="Law vetoes" value={gate.law_vetoes} tone="text-veto" icon={Scale} />
          <Stat label="Gemini-judged" value={gate.gemini_judged} tone="text-accent" icon={Sparkles} />
        </dl>
      </div>

      <p className="mt-3 rounded-lg border border-edge bg-panel2 p-2.5 text-[11px] text-muted">
        Judge model: <span className="font-mono text-body">{gate.judge_model}</span>
      </p>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string;
  value: number;
  tone: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="rounded-lg border border-edge bg-panel2 p-2.5">
      <dt className="flex items-center gap-1 text-[11px] text-muted">
        {Icon ? <Icon className="h-3 w-3" /> : null}
        {label}
      </dt>
      <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${tone}`}>{value}</dd>
    </div>
  );
}
