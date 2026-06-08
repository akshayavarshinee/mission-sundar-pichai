"use client";

import type { RunSummary } from "@/lib/api";
import { fmtUsd } from "@/lib/format";

interface Props {
  approvals: RunSummary[];
  busy: string | null;
  onApprove: (runId: string) => void;
  onReject: (runId: string) => void;
}

// Human-in-the-loop queue: every escalation the agent safely refused to
// auto-execute lands here for a one-click decision.
export default function ApprovalQueue({
  approvals,
  busy,
  onApprove,
  onReject,
}: Props) {
  return (
    <div className="card flex h-full flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Approval queue</h2>
        <span className="rounded-full border border-edge px-2 py-0.5 text-xs text-warn">
          {approvals.length} awaiting
        </span>
      </div>

      {approvals.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">
          No escalations awaiting review.
        </p>
      ) : (
        <ul className="space-y-2 overflow-y-auto">
          {approvals.map((run) => (
            <li
              key={run.run_id}
              className="rounded-lg border border-warn/30 bg-warn/5 p-3"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="font-mono text-sm font-semibold text-white">
                  {run.seed_id ?? run.run_id.slice(0, 8)}
                </span>
                <span className="text-xs text-slate-400">
                  {fmtUsd(run.customs_value)} · {run.error_type}
                </span>
              </div>
              <p className="mb-2 text-xs text-slate-400">
                {run.risk.reasons[0] ?? run.root_cause}
              </p>
              <div className="flex gap-2">
                <button
                  className="btn btn-good flex-1"
                  disabled={busy !== null}
                  onClick={() => onApprove(run.run_id)}
                >
                  {busy === run.run_id ? "…" : "Approve & buy label"}
                </button>
                <button
                  className="btn btn-bad"
                  disabled={busy !== null}
                  onClick={() => onReject(run.run_id)}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
