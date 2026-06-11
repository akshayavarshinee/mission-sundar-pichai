"use client";

import { CheckCircle2, Zap } from "lucide-react";
import type { SelfHealPair } from "@/lib/api";
import { fmtSeconds } from "@/lib/format";
import { errorLabel } from "@/lib/shipment";

// Self-healing: once a lesson is promoted, the same rejection is fixed straight
// from memory with no human touch. We lead with that autonomy (the robust
// signal) and show first-vs-repeat latency as supporting context.
export default function SelfHealPanel({ pairs }: { pairs: SelfHealPair[] }) {
  const max = Math.max(1e-9, ...pairs.flatMap((p) => [p.first_seconds, p.repeat_seconds]));
  const healed = pairs.filter((p) => p.healed_from_memory).length;

  return (
    <section className="card p-5">
      <h2 className="section-title">
        <Zap className="h-4 w-4 text-warn" />
        Self-healing — the second time is autonomous
      </h2>
      <p className="mt-1 text-xs text-muted">
        After a lesson is promoted, recurring rejections fix themselves from memory.{" "}
        <span className="font-medium text-good">
          {healed}/{pairs.length}
        </span>{" "}
        repeat patterns healed with no human touch.
      </p>

      <ul className="mt-3 space-y-3">
        {pairs.map((p) => (
          <li key={p.memory_key} className="rounded-lg border border-edge bg-panel2 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium text-body">{errorLabel(p.error_type)}</span>
              {p.healed_from_memory ? (
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-good/30 bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">
                  <CheckCircle2 className="h-3 w-3" /> self-healed
                </span>
              ) : (
                <span className="pill shrink-0 border-edge text-[11px] text-muted">
                  {p.occurrences}× seen
                </span>
              )}
            </div>
            <div className="mt-2 space-y-1.5">
              <Bar label="first encounter" seconds={p.first_seconds} frac={p.first_seconds / max} tone="bg-faint" />
              <Bar
                label={`repeat ×${Math.max(1, p.occurrences - 1)}`}
                seconds={p.repeat_seconds}
                frac={p.repeat_seconds / max}
                tone="bg-good"
              />
            </div>
            <div className="mt-1.5 font-mono text-[10px] text-faint">{p.memory_key}</div>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-[11px] text-faint">
        Repeats reuse a tier-③ lesson; the latency speed-up grows with live model calls.
      </p>
    </section>
  );
}

function Bar({
  label,
  seconds,
  frac,
  tone,
}: {
  label: string;
  seconds: number;
  frac: number;
  tone: string;
}) {
  const width = `${Math.max(4, Math.min(100, frac * 100)).toFixed(1)}%`;
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 text-[11px] text-muted">{label}</span>
      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-panel">
        <div className={`h-full rounded-full ${tone}`} style={{ width }} />
      </div>
      <span className="w-16 shrink-0 text-right font-mono text-[11px] text-body">{fmtSeconds(seconds)}</span>
    </div>
  );
}
