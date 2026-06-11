"use client";

import {
  Activity,
  Boxes,
  Database,
  ExternalLink,
  FlaskConical,
  GitBranch,
  GraduationCap,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { phoenixTraceUrl, type ArizeIntel } from "@/lib/api";

// The "trust & telemetry" panel: a compact, honest map of every way ClearPort
// touches Arize Phoenix — tracing, eval-gating, experiments, datasets, prompts,
// and the MCP tool surface — driven entirely by real in-process counts.
export default function ArizeStrip({ arize }: { arize: ArizeIntel }) {
  const g = arize.eval_gate;
  const backends: [string, string][] = [
    ["episodic ②", arize.episodic_backend],
    ["prompts ④", arize.prompts_backend],
    ["embeddings", arize.embeddings_backend],
    ["vector", arize.vector_backend],
  ];

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="section-title">
            <Activity className="h-4 w-4 text-accent" />
            Arize Phoenix — the trust &amp; telemetry layer
          </h2>
          <p className="mt-1 text-xs text-muted">
            Every recovery is traced, evaluated, experiment-gated, and replayed through Phoenix.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`pill ${
              arize.live
                ? "border-good/40 bg-good/10 text-good"
                : "border-warn/40 bg-warn/10 text-warn"
            }`}
            title={arize.mode}
          >
            <span className={`h-2 w-2 rounded-full ${arize.live ? "bg-good" : "bg-warn"}`} />
            {arize.live ? "live Phoenix" : "offline fallback"}
          </span>
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
      </div>

      {/* headline tiles */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Tile icon={Activity} label="Traces" value={arize.traces_emitted} hint="recovery runs" tone="text-accent" />
        <Tile icon={Layers} label="Spans" value={arize.spans_emitted} hint="instrumented steps" tone="text-accent" />
        <Tile
          icon={ShieldCheck}
          label="Eval-gate"
          value={`${g.pass_rate.toFixed(0)}%`}
          hint={`${g.passed}/${g.total} passed`}
          tone="text-good"
        />
        <Tile icon={FlaskConical} label="Experiments won" value={arize.experiments_won} hint="live in Phoenix" tone="text-veto" />
        <Tile icon={GraduationCap} label="Lessons promoted" value={arize.lessons_promoted} hint="to memory ③" tone="text-good" />
      </div>

      {/* Phoenix surfaces */}
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-lg border border-edge bg-panel2 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
            <FlaskConical className="h-3.5 w-3.5 text-accent" />
            Tracing project
          </div>
          <div className="mt-1.5 font-mono text-xs text-body">{arize.project}</div>
          <div className="break-all font-mono text-[11px] text-faint">{arize.tracing_endpoint}</div>
          <div className="mt-1.5 text-[11px] text-muted">
            {g.gemini_judged} eval(s) judged by{" "}
            <span className="font-mono text-body">{g.judge_model}</span> · {g.law_vetoes} law veto(es)
          </div>
        </div>

        <div className="rounded-lg border border-edge bg-panel2 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
            <Database className="h-3.5 w-3.5 text-accent" />
            Datasets
          </div>
          <ul className="mt-1.5 space-y-1.5">
            {arize.datasets.map((d) => (
              <li key={d.name} className="text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-body">{d.name}</span>
                  <span className="shrink-0 tabular-nums text-muted">{d.examples}</span>
                </div>
                <div className="text-[11px] text-faint">{d.role}</div>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-edge bg-panel2 p-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
            <Boxes className="h-3.5 w-3.5 text-accent" />
            Active backends
          </div>
          <dl className="mt-1.5 space-y-1 text-xs">
            {backends.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-2">
                <dt className="text-muted">{k}</dt>
                <dd className="truncate font-mono text-body">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* MCP tool surface */}
      <div className="mt-4">
        <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted">
          <GitBranch className="h-3.5 w-3.5" />
          Phoenix MCP tools ({arize.mcp_tools.length})
        </div>
        <div className="flex flex-wrap gap-1.5">
          {arize.mcp_tools.map((t) => (
            <span key={t} className="pill border-edge font-mono text-[11px] text-muted">
              {t}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function Tile({
  icon: Icon,
  label,
  value,
  hint,
  tone = "text-ink",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-edge bg-panel2 p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${tone}`}>{value}</div>
      {hint ? <div className="text-[11px] text-faint">{hint}</div> : null}
    </div>
  );
}
