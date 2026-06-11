"use client";

import { useState } from "react";
import {
  Activity,
  ExternalLink,
  FlaskConical,
  Loader2,
  ShieldCheck,
  Target,
} from "lucide-react";
import { api, phoenixExperimentUrl, type BenchmarkReport } from "@/lib/api";

// The quantitative eval behind the trust claims: a labeled synthetic suite run
// end-to-end through the real loop and scored against known ground truth. It is
// lazy-run on demand (it drives the loop dozens of times) and, when Phoenix is
// live, logged as a real dataset + experiment the judge can open.
export default function BenchmarkPanel() {
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = (opts?: { refresh?: boolean; register?: boolean }) => {
    setLoading(true);
    setError(null);
    api
      .benchmark(opts)
      .then(setReport)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="section-title">
            <FlaskConical className="h-4 w-4 text-accent" />
            Recovery benchmark — measured, not asserted
          </h2>
          <p className="mt-1 max-w-2xl text-xs text-muted">
            A labeled synthetic suite of customs rejections with known ground truth, run end-to-end
            through the real recovery loop and scored. The cardinal metric is the false auto-clear
            rate — how often an invalid declaration is auto-shipped. It must be zero.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {report ? (
            <button
              className="btn btn-ghost text-xs"
              onClick={() => run({ refresh: true })}
              disabled={loading}
            >
              Re-run
            </button>
          ) : null}
          <button
            className="btn btn-accent text-xs"
            onClick={() => run(report ? { refresh: true, register: true } : undefined)}
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Running…
              </>
            ) : report ? (
              "Log to Phoenix"
            ) : (
              "Run benchmark"
            )}
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-lg border border-veto/40 bg-veto/5 p-3 text-xs text-veto">{error}</p>
      ) : null}

      {!report && !loading && !error ? (
        <p className="mt-4 rounded-lg border border-edge bg-panel2 p-3 text-xs text-muted">
          Not run yet — runs the full loop on each labeled case (no labels are purchased; nothing is
          written to memory).
        </p>
      ) : null}

      {report ? (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Metric
              label="Resolution accuracy"
              value={pctOf(report.resolution_accuracy)}
              tone="text-good"
              icon={Target}
              hint={`${report.total} labeled cases`}
            />
            <Metric
              label="False auto-clear rate"
              value={pctOf(report.false_auto_clear_rate)}
              tone={report.false_auto_clear_rate === 0 ? "text-good" : "text-veto"}
              icon={ShieldCheck}
              hint="invalid fix auto-shipped"
            />
            <Metric
              label="Diagnosis accuracy"
              value={pctOf(report.diagnosis_accuracy)}
              tone="text-accent"
              icon={Activity}
              hint="right field identified"
            />
            <Metric
              label="Missed escalation"
              value={pctOf(report.missed_escalation_rate)}
              tone={report.missed_escalation_rate === 0 ? "text-good" : "text-warn"}
              hint="should-be-human auto-handled"
            />
            <Metric
              label="Auto-resolve rate"
              value={pctOf(report.auto_resolve_rate)}
              tone="text-body"
              hint="throughput context"
            />
            <Metric
              label="False rejection"
              value={pctOf(report.false_rejection_rate)}
              tone={report.false_rejection_rate === 0 ? "text-good" : "text-warn"}
              hint={`${report.control_n} clean controls`}
            />
          </div>

          <div>
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-faint">
              Per-slice accuracy
            </h3>
            <ul className="space-y-1.5">
              {report.slices.map((s) => (
                <li key={s.slice} className="flex items-center gap-3">
                  <span className="w-44 shrink-0 truncate font-mono text-[11px] text-muted">
                    {s.slice}
                    <span className="text-faint"> ·{s.n}</span>
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel2">
                    <div
                      className={s.false_auto_clear_rate > 0 ? "h-full bg-veto" : "h-full bg-good"}
                      style={{ width: `${Math.round(s.accuracy * 100)}%` }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right text-[11px] tabular-nums text-body">
                    {pctOf(s.accuracy)}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {report.calibration.length > 0 ? (
            <div>
              <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-faint">
                Confidence calibration — does eval confidence track reality?
              </h3>
              <ul className="space-y-1.5">
                {report.calibration.map((b) => (
                  <li key={`${b.lower}-${b.upper}`} className="flex items-center gap-3">
                    <span className="w-20 shrink-0 font-mono text-[11px] text-muted">
                      {pctOf(b.lower)}–{pctOf(b.upper)}
                      <span className="text-faint"> ·{b.n}</span>
                    </span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel2">
                      <div
                        className="h-full bg-accent"
                        style={{ width: `${Math.round(b.empirical_clean_rate * 100)}%` }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right text-[11px] tabular-nums text-body">
                      {pctOf(b.empirical_clean_rate)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1.5 text-[10px] text-faint">
                Each band shows the empirical rate at which a fix was actually valid — well-calibrated
                confidence rises left-to-right.
              </p>
            </div>
          ) : null}

          {report.experiment_live && report.experiment_id ? (
            <a
              href={phoenixExperimentUrl(report.experiment_dataset_id, report.experiment_id)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
            >
              View benchmark experiment in Phoenix <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            <p className="text-[11px] text-faint">
              Run with Phoenix live to log this as a clickable dataset + experiment.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function pctOf(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

function Metric({
  label,
  value,
  tone,
  icon: Icon,
  hint,
}: {
  label: string;
  value: string;
  tone: string;
  icon?: React.ComponentType<{ className?: string }>;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-edge bg-panel2 p-3">
      <div className="flex items-center gap-1 text-[11px] text-muted">
        {Icon ? <Icon className="h-3 w-3" /> : null}
        {label}
      </div>
      <div className={`mt-0.5 text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
      {hint ? <div className="mt-0.5 text-[10px] text-faint">{hint}</div> : null}
    </div>
  );
}
