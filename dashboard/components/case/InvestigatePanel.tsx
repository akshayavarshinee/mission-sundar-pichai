"use client";

import { useState } from "react";
import { ExternalLink, Loader2, Search } from "lucide-react";
import { api, phoenixTraceUrl, type InvestigationResult } from "@/lib/api";

// On-demand: re-ground a run's eval verdict by reading its verify-span
// annotations back out of Phoenix over the Model Context Protocol. A genuine
// runtime MCP exercise (judge-triggered), with a deterministic fallback.
export default function InvestigatePanel({ runId }: { runId: string }) {
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const investigate = () => {
    setLoading(true);
    setError(null);
    api
      .investigate(runId)
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  return (
    <section className="card p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="section-title">
          <Search className="h-4 w-4 text-accent" />
          Investigate in Phoenix (MCP)
        </h2>
        <button className="btn btn-ghost text-xs" onClick={investigate} disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Reading…
            </>
          ) : (
            "Investigate"
          )}
        </button>
      </div>
      <p className="mt-1 text-xs text-muted">
        Reads this run&apos;s verify-span annotations back out of Phoenix over the Model Context
        Protocol to re-ground the eval verdict.
      </p>

      {error ? (
        <p className="mt-3 rounded-lg border border-veto/40 bg-veto/5 p-3 text-xs text-veto">{error}</p>
      ) : null}

      {result ? (
        <div className="mt-3 space-y-2">
          <p className="rounded-lg border border-edge bg-panel2 p-3 text-sm leading-relaxed text-body">
            {result.explanation}
          </p>
          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            <span className={result.mcp_used ? "text-good" : "text-faint"}>
              {result.mcp_used ? "● live Phoenix MCP read-back" : "○ deterministic (MCP offline)"}
            </span>
            {result.span_id ? (
              <span className="font-mono text-faint">span {result.span_id.slice(0, 12)}</span>
            ) : null}
            <a
              href={phoenixTraceUrl()}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-accent hover:underline"
            >
              Open Phoenix <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          {result.annotations.length > 0 ? (
            <ul className="space-y-1">
              {result.annotations.map((a, i) => (
                <li
                  key={a.id ?? i}
                  className="flex items-center justify-between rounded-lg border border-edge bg-panel2 px-2.5 py-1.5 text-[11px]"
                >
                  <span className="font-mono text-body">{a.name ?? "annotation"}</span>
                  <span className="text-muted">
                    {a.result?.label ?? "—"}
                    {typeof a.result?.score === "number" ? ` · ${a.result.score.toFixed(2)}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
