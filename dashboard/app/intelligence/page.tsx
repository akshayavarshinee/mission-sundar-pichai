"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, GraduationCap, Scale } from "lucide-react";
import { api, type LawRecord, type LessonRecord } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { errorLabel } from "@/lib/shipment";
import TraceTimeline from "@/components/TraceTimeline";

export default function IntelligencePage() {
  const { events, connected } = useWorkspace();
  const [lessons, setLessons] = useState<LessonRecord[]>([]);
  const [law, setLaw] = useState<LawRecord[]>([]);

  const load = useCallback(() => {
    api.memoryLessons().then(setLessons).catch(() => setLessons([]));
    api.memoryLaw().then(setLaw).catch(() => setLaw([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Refresh memory when a lesson is promoted or the board resets.
  useEffect(() => {
    const latest = events[0];
    if (latest && ["lesson_promoted", "reset", "drift_alert"].includes(latest.type)) load();
  }, [events, load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Intelligence</h1>
        <p className="text-sm text-muted">
          The memory and law that ground every fix — and how ClearPort learns from each outcome.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Promoted lessons (tier ③) */}
          <div className="card p-5">
            <h2 className="section-title mb-1">
              <GraduationCap className="h-4 w-4 text-good" />
              Promoted lessons
            </h2>
            <p className="mb-3 text-xs text-muted">
              Fixes promoted to permanent memory only after a Phoenix experiment beat baseline.
            </p>
            {lessons.length === 0 ? (
              <p className="rounded-lg border border-edge bg-panel2 p-4 text-center text-sm text-muted">
                No lessons yet — after a human correction, run learning from the Demo drawer to
                promote one.
              </p>
            ) : (
              <ul className="space-y-2">
                {lessons.map((l) => (
                  <li key={l.id} className="rounded-lg border border-edge bg-panel2 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted">
                        {l.key.lane} · hs{l.key.hs_chapter} · {errorLabel(l.key.error_type)}
                      </span>
                      <span className="rounded-full border border-good/30 bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">
                        {(l.pass_rate * 100).toFixed(0)}% pass-rate
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm text-body">{l.recommended_fix}</p>
                    <div className="mt-1.5 flex flex-wrap gap-x-4 text-[11px] text-faint">
                      <span>{l.evidence_count} observation(s)</span>
                      {l.baseline_score != null && l.candidate_score != null ? (
                        <span>
                          baseline {l.baseline_score.toFixed(2)} → candidate{" "}
                          {l.candidate_score.toFixed(2)}
                        </span>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Customs law (tier ①) */}
          <div className="card p-5">
            <h2 className="section-title mb-1">
              <Scale className="h-4 w-4 text-veto" />
              Grounding customs law
            </h2>
            <p className="mb-3 text-xs text-muted">
              The HTS / CROSS / EEI corpus the Auditor cites — law has veto over experience.
            </p>
            <ul className="max-h-96 space-y-2 overflow-y-auto pr-1">
              {law.map((r) => (
                <li key={r.id} className="rounded-lg border border-edge bg-panel2 p-3">
                  <div className="flex items-center gap-2 text-xs">
                    <BookOpen className="h-3.5 w-3.5 text-veto" />
                    <span className="font-medium text-body">
                      {r.source} {r.ref}
                    </span>
                    {r.hs_chapter ? (
                      <span className="font-mono text-faint">hs{r.hs_chapter}</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted">{r.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div>
          <TraceTimeline events={events} connected={connected} />
        </div>
      </div>
    </div>
  );
}
