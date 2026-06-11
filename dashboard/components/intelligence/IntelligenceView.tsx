"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Brain, ExternalLink, Scale, Sparkles } from "lucide-react";
import { api, phoenixTraceUrl, type IntelligenceReport, type LawRecord } from "@/lib/api";
import { useWorkspace } from "@/lib/workspace";
import { fmtTime } from "@/lib/format";
import TraceTimeline from "@/components/TraceTimeline";
import ArizeStrip from "@/components/intelligence/ArizeStrip";
import MemoryTiers from "@/components/intelligence/MemoryTiers";
import ProgressionPanel from "@/components/intelligence/ProgressionPanel";
import EvalGatePanel from "@/components/intelligence/EvalGatePanel";
import SelfHealPanel from "@/components/intelligence/SelfHealPanel";
import LessonTimeline from "@/components/intelligence/LessonTimeline";

// Events that change what the Intelligence page should show.
const REFRESH = new Set([
  "run_created",
  "run_approved",
  "run_rejected",
  "run_corrected",
  "lesson_promoted",
  "drift_alert",
  "reset",
  "demo_complete",
  "seed_history_complete",
]);

// The Intelligence dashboard: one guided story from Arize telemetry → the
// over-time learning curve → eval-gate & self-heal → the memory tiers and the
// promoted lessons that prove the loop closed. All data is real (api.intelligence()).
export default function IntelligenceView() {
  const { events, connected, seedHistory, busy } = useWorkspace();
  const [report, setReport] = useState<IntelligenceReport | null>(null);
  const [law, setLaw] = useState<LawRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    api
      .intelligence()
      .then(setReport)
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
    api.memoryLaw().then(setLaw).catch(() => setLaw([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Re-pull the aggregate whenever the loop advances or the board resets.
  useEffect(() => {
    const latest = events[0];
    if (latest && REFRESH.has(latest.type)) load();
  }, [events, load]);

  const hasRuns = (report?.progression.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Intelligence</h1>
          <p className="text-sm text-muted">
            How ClearPort learns — Arize Phoenix telemetry, four-tier memory, and the self-improving loop.
          </p>
        </div>
        {report ? <span className="text-[11px] text-faint">updated {fmtTime(report.generated_at)}</span> : null}
      </div>

      {loading && !report ? (
        <div className="card p-10 text-center text-sm text-muted">Loading intelligence…</div>
      ) : !report ? (
        <div className="card p-10 text-center text-sm text-muted">
          Intelligence unavailable — is the backend running?
        </div>
      ) : (
        <>
          {!hasRuns ? (
            <div className="card flex flex-wrap items-center justify-between gap-3 border-accent/40 bg-accent/5 p-5">
              <div>
                <h2 className="section-title">
                  <Sparkles className="h-4 w-4 text-accent" />
                  Seed a learning history
                </h2>
                <p className="mt-1 max-w-2xl text-xs text-muted">
                  No recoveries yet. Seed ~24 real runs to watch auto-resolve climb from 0% as lessons are
                  learned — nothing is faked; the genuine loop runs end-to-end.
                </p>
              </div>
              <button className="btn btn-accent" onClick={() => seedHistory()} disabled={busy === "seed"}>
                {busy === "seed" ? "Seeding…" : "Seed rich history"}
              </button>
            </div>
          ) : null}

          <ArizeStrip arize={report.arize} />

          {hasRuns ? <ProgressionPanel points={report.progression} /> : null}

          {hasRuns ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <EvalGatePanel gate={report.arize.eval_gate} />
              {report.self_heal.length > 0 ? (
                <SelfHealPanel pairs={report.self_heal} />
              ) : (
                <section className="card p-5">
                  <h2 className="section-title">
                    <Brain className="h-4 w-4 text-warn" />
                    Self-healing
                  </h2>
                  <p className="mt-2 text-sm text-muted">
                    No repeat patterns yet — once a rejection recurs after a lesson is promoted, it heals from
                    memory here.
                  </p>
                </section>
              )}
            </div>
          ) : null}

          <MemoryTiers memory={report.memory} />

          {report.lesson_timeline.length > 0 ? <LessonTimeline lessons={report.lesson_timeline} /> : null}

          {/* grounding law + live traces */}
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="card p-5 lg:col-span-2">
              <div className="flex items-center justify-between">
                <h2 className="section-title">
                  <Scale className="h-4 w-4 text-veto" />
                  Grounding customs law
                </h2>
                <a
                  href={phoenixTraceUrl()}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                >
                  Phoenix <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              <p className="mb-3 mt-1 text-xs text-muted">
                The HTS / CROSS / EEI corpus the Auditor cites — law has veto over experience.
              </p>
              <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
                {law.map((r) => (
                  <li key={r.id} className="rounded-lg border border-edge bg-panel2 p-3">
                    <div className="flex items-center gap-2 text-xs">
                      <BookOpen className="h-3.5 w-3.5 text-veto" />
                      <span className="font-medium text-body">
                        {r.source} {r.ref}
                      </span>
                      {r.hs_chapter ? <span className="font-mono text-faint">hs{r.hs_chapter}</span> : null}
                    </div>
                    <p className="mt-1 text-[11px] leading-relaxed text-muted">{r.text}</p>
                  </li>
                ))}
              </ul>
            </section>
            <TraceTimeline events={events} connected={connected} />
          </div>
        </>
      )}
    </div>
  );
}
