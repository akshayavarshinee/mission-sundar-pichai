"use client";

import type { ClearEvent } from "@/lib/useEvents";
import { phoenixTraceUrl } from "@/lib/api";
import { eventLabel, fmtTime, decisionTone } from "@/lib/format";

function dotColor(type: string): string {
  if (type === "drift_alert") return "bg-bad";
  if (type === "law_veto") return "bg-veto";
  if (type === "lesson_promoted") return "bg-good";
  if (type === "run_rejected") return "bg-bad";
  if (type === "run_approved") return "bg-good";
  if (type === "demo_beat") return "bg-veto";
  if (type === "demo_complete") return "bg-good";
  if (type === "reset") return "bg-slate-500";
  return "bg-accent";
}

function detail(evt: ClearEvent): string {
  const d = evt.data as Record<string, unknown>;
  switch (evt.type) {
    case "run_created":
      return `${d.seed_id ?? "—"} · ${d.error_type ?? ""} → ${String(
        d.decision ?? ""
      )} (eval ${d.eval_passed ? "pass" : "FAIL"})`;
    case "shipment_accepted":
      return `${d.seed_id ?? "—"} cleared with no rejection`;
    case "law_veto":
      return `vetoed lessons: ${(d.lessons as string[] | undefined)?.length ?? 0}`;
    case "lesson_promoted":
      return `${d.memory_key ?? ""} — ${d.recommended_fix ?? ""}`;
    case "drift_alert":
      return `${d.memory_key ?? ""} · pass-rate ${d.pass_rate ?? "?"} < floor ${d.floor ?? "?"}`;
    case "run_approved":
    case "run_rejected":
      return `${d.run_id ?? ""}`;
    case "metrics":
      return `${d.pct_auto_resolved ?? 0}% auto · ${d.resolved ?? 0} resolved`;
    case "demo_beat":
      return `Beat ${d.index ?? ""} — ${d.title ?? ""}`;
    case "demo_complete":
      return `${d.beats ?? ""} beats played`;
    case "reset":
      return "board cleared";
    default:
      return "";
  }
}

export default function TraceTimeline({
  events,
  connected,
}: {
  events: ClearEvent[];
  connected: boolean;
}) {
  return (
    <div className="card flex h-full min-h-[24rem] flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Live trace timeline</h2>
        <div className="flex items-center gap-3">
          <a
            href={phoenixTraceUrl()}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-accent hover:underline"
          >
            Open in Phoenix ↗
          </a>
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <span
              className={`h-2 w-2 rounded-full ${
                connected ? "bg-good" : "bg-bad"
              }`}
            />
            {connected ? "live" : "reconnecting"}
          </span>
        </div>
      </div>

      <ol className="flex-1 space-y-0 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <li className="py-8 text-center text-sm text-slate-500">
            Trigger a shipment to watch the recovery loop stream live.
          </li>
        ) : (
          events.map((evt, i) => (
            <li
              key={`${evt.ts}-${i}`}
              className={`flex items-start gap-3 border-b border-edge/50 py-2 ${
                i === 0 ? "animate-pulseRow" : ""
              }`}
            >
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotColor(
                  evt.type
                )}`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-medium text-slate-200">
                    {eventLabel(evt.type)}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-slate-500">
                    {fmtTime(evt.ts)}
                  </span>
                </div>
                <p
                  className={`truncate text-xs ${
                    evt.type === "drift_alert"
                      ? "text-bad"
                      : evt.type === "law_veto"
                        ? "text-veto"
                        : decisionTone(
                            String(
                              (evt.data as Record<string, unknown>).decision ?? ""
                            )
                          )
                  }`}
                >
                  {detail(evt)}
                </p>
              </div>
            </li>
          ))
        )}
      </ol>
    </div>
  );
}
