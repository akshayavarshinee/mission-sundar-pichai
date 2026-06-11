"use client";

import { useState } from "react";
import {
  Check,
  Package,
  PenLine,
  ShoppingCart,
  X,
} from "lucide-react";
import type { RunSummary, RunTrace, SubmitPayload } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import { contentsLabel, prettyLane } from "@/lib/shipment";
import StatusPill from "@/components/ui/StatusPill";
import RecoveryStepper from "@/components/case/RecoveryStepper";
import TraceWaterfall from "@/components/case/TraceWaterfall";
import CorrectionForm from "@/components/case/CorrectionForm";

export default function CaseFile({
  run,
  trace,
  busy,
  onApprove,
  onReject,
  onCorrect,
}: {
  run: RunSummary;
  trace: RunTrace | null;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onCorrect: (payload: SubmitPayload, note: string) => void;
}) {
  const [correcting, setCorrecting] = useState(false);
  const awaiting = run.status === "AWAITING_APPROVAL";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-lg font-semibold tracking-tight text-ink">
                {run.title}
              </h1>
              {run.seed_id ? (
                <span className="shrink-0 rounded border border-edge bg-panel2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
                  {run.seed_id}
                </span>
              ) : null}
            </div>
            <p className="mt-0.5 text-sm text-muted">{run.persona}</p>
          </div>
          <StatusPill status={run.status} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Route", value: prettyLane(run.origin, run.dest) },
            { label: "Customs value", value: fmtUsd(run.customs_value) },
            { label: "Contents", value: contentsLabel(run.contents_type) },
            {
              label: "Demurrage saved",
              value: run.demurrage_saved_usd > 0 ? fmtUsd(run.demurrage_saved_usd) : "—",
            },
          ].map((m) => (
            <div key={m.label} className="rounded-lg border border-edge bg-panel2 p-2.5">
              <div className="text-[10px] uppercase tracking-wide text-faint">{m.label}</div>
              <div className="text-sm font-medium text-body">{m.value}</div>
            </div>
          ))}
        </div>

        {/* Approval actions */}
        {awaiting ? (
          <div className="mt-4 rounded-lg border border-warn/30 bg-warn/5 p-3">
            <p className="mb-2.5 text-sm font-medium text-warn">
              This shipment needs your decision — ClearPort would not auto-spend on it.
            </p>
            {correcting ? (
              <CorrectionForm
                declaration={run.declaration}
                busy={busy}
                onSubmit={(payload, note) => {
                  onCorrect(payload, note);
                  setCorrecting(false);
                }}
                onCancel={() => setCorrecting(false)}
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                <button className="btn btn-good" disabled={busy} onClick={onApprove}>
                  <ShoppingCart className="h-4 w-4" />
                  {busy ? "Working…" : "Approve & buy label"}
                </button>
                <button className="btn" disabled={busy} onClick={() => setCorrecting(true)}>
                  <PenLine className="h-4 w-4" />
                  Correct…
                </button>
                <button className="btn btn-bad" disabled={busy} onClick={onReject}>
                  <X className="h-4 w-4" />
                  Reject
                </button>
              </div>
            )}
          </div>
        ) : null}

        {run.human_note ? (
          <div className="mt-3 flex items-center gap-1.5 text-xs text-muted">
            <Check className="h-3.5 w-3.5 text-good" />
            Your note: {run.human_note}
          </div>
        ) : null}
      </div>

      {/* Narrative + side panels */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecoveryStepper run={run} />
        </div>
        <div className="space-y-6">
          <div className="card p-5">
            <h2 className="section-title mb-3">
              <Package className="h-4 w-4 text-accent" />
              Goods declared
            </h2>
            <ul className="space-y-2">
              {run.items.map((it, i) => (
                <li key={i} className="rounded-lg border border-edge bg-panel2 p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm text-body">{it.description}</span>
                    <span className="shrink-0 text-sm tabular-nums text-muted">
                      {fmtUsd(it.value)}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-3 text-[11px] text-faint">
                    <span>qty {it.quantity}</span>
                    <span className="font-mono">HS {it.hs_tariff_number ?? "—"}</span>
                    <span>origin {it.origin_country}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <TraceWaterfall trace={trace} />
        </div>
      </div>
    </div>
  );
}
