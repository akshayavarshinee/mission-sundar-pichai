"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ExternalLink,
  Gavel,
  PenLine,
  ShieldAlert,
  ShoppingCart,
  X,
} from "lucide-react";
import type { RunSummary, SubmitPayload } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import { errorLabel, prettyLane } from "@/lib/shipment";
import CorrectionForm from "@/components/case/CorrectionForm";

export default function InboxCard({
  run,
  busy,
  onApprove,
  onReject,
  onCorrect,
}: {
  run: RunSummary;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
  onCorrect: (payload: SubmitPayload, note: string) => void;
}) {
  const [correcting, setCorrecting] = useState(false);

  return (
    <div className="card border-warn/30 p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-ink">{run.title}</span>
            {run.seed_id ? (
              <span className="shrink-0 rounded border border-edge bg-panel2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
                {run.seed_id}
              </span>
            ) : null}
          </div>
          <div className="text-xs text-muted">
            {prettyLane(run.origin, run.dest)} · {fmtUsd(run.customs_value)} ·{" "}
            {errorLabel(run.error_type)}
          </div>
        </div>
        <Link
          href={`/shipments/${run.run_id}`}
          className="inline-flex shrink-0 items-center gap-1 text-xs text-accent hover:underline"
        >
          Open case
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      {/* Why it needs a human */}
      <div className="mb-3 space-y-1.5">
        {!run.eval.passed ? (
          <div className="flex items-center gap-1.5 rounded-md border border-veto/30 bg-veto/5 p-2 text-[11px] text-veto">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
            Eval-gate vetoed the proposed fix — review before any spend.
          </div>
        ) : null}
        {run.risk.hard_line ? (
          <div className="flex items-center gap-1.5 rounded-md border border-warn/30 bg-warn/5 p-2 text-[11px] text-warn">
            <Gavel className="h-3.5 w-3.5 shrink-0" />
            Crossed the $2,500 hard line — mandatory human oversight.
          </div>
        ) : null}
        <p className="text-xs text-muted">{run.risk.reasons[0] ?? run.root_cause}</p>
      </div>

      {/* Proposed fix */}
      {run.field_diff.length > 0 ? (
        <div className="mb-3 space-y-1">
          {run.field_diff.map((d, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className="font-mono text-muted">{d.field}</span>
              <span className="rounded bg-bad/10 px-1.5 py-0.5 font-mono text-bad line-through">
                {String(d.before ?? "empty")}
              </span>
              <ArrowRight className="h-3 w-3 text-faint" />
              <span className="rounded bg-good/10 px-1.5 py-0.5 font-mono text-good">
                {String(d.after ?? "empty")}
              </span>
            </div>
          ))}
        </div>
      ) : null}

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
          <button className="btn btn-good flex-1" disabled={busy} onClick={onApprove}>
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
  );
}
