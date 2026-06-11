"use client";

import { ExternalLink, GraduationCap } from "lucide-react";
import { phoenixExperimentUrl, type LessonProgressPoint } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { errorLabel } from "@/lib/shipment";

// The proof behind every promotion: a candidate fix only enters memory after an
// Arize experiment scored it above the prior behaviour. We show that
// baseline → candidate jump alongside the pass-rate and evidence.
export default function LessonTimeline({ lessons }: { lessons: LessonProgressPoint[] }) {
  return (
    <section className="card p-5">
      <h2 className="section-title">
        <GraduationCap className="h-4 w-4 text-good" />
        Lessons promoted — only after an experiment beat baseline
      </h2>
      <p className="mt-1 text-xs text-muted">
        Each fix earned its place in memory by winning a Phoenix experiment against the prior behaviour.
      </p>

      <ol className="mt-3 space-y-3">
        {lessons.map((l, i) => (
          <li key={`${l.memory_key}-${i}`} className="rounded-lg border border-edge bg-panel2 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-good/40 bg-good/10 text-[11px] font-semibold text-good">
                  {l.cum_lessons}
                </span>
                <span className="text-sm font-medium text-body">{errorLabel(l.error_type)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-good/30 bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">
                  {(l.pass_rate * 100).toFixed(0)}% pass-rate
                </span>
                {l.promoted_at ? (
                  <span className="font-mono text-[11px] text-faint">{fmtTime(l.promoted_at)}</span>
                ) : null}
              </div>
            </div>

            <p className="mt-1.5 text-sm text-body">{l.recommended_fix}</p>

            <div className="mt-2 space-y-1">
              <ScoreBar label="baseline" score={l.baseline_score} tone="bg-faint" />
              <ScoreBar label="candidate" score={l.candidate_score} tone="bg-good" />
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-faint">
              <span>{l.evidence_count} observation(s)</span>
              <span className="font-mono">{l.memory_key}</span>
              {l.experiment_live && l.experiment_id ? (
                <a
                  href={phoenixExperimentUrl(l.experiment_dataset_id, l.experiment_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:underline"
                  title={`Phoenix experiment ${l.experiment_id}`}
                >
                  View experiment in Phoenix
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function ScoreBar({
  label,
  score,
  tone,
}: {
  label: string;
  score: number | null;
  tone: string;
}) {
  const value = score ?? 0;
  const width = `${Math.max(2, Math.min(100, value * 100)).toFixed(0)}%`;
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-[11px] text-muted">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel">
        <div className={`h-full rounded-full ${tone}`} style={{ width }} />
      </div>
      <span className="w-10 shrink-0 text-right font-mono text-[11px] text-body">
        {score == null ? "—" : value.toFixed(2)}
      </span>
    </div>
  );
}
