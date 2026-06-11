"use client";

import { CheckCircle2 } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import InboxCard from "@/components/inbox/InboxCard";

export default function InboxPage() {
  const { approvals, busy, approve, reject, correct } = useWorkspace();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">Needs your sign-off</h1>
        <p className="text-sm text-muted">
          ClearPort routes high-value, restricted, or low-confidence fixes here instead of acting on
          its own.
        </p>
      </div>

      {approvals.length === 0 ? (
        <div className="card flex flex-col items-center gap-2 py-16 text-center">
          <CheckCircle2 className="h-8 w-8 text-good" />
          <p className="text-sm font-medium text-ink">You’re all caught up</p>
          <p className="text-sm text-muted">No shipments are waiting on a human decision.</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {approvals.map((run) => (
            <InboxCard
              key={run.run_id}
              run={run}
              busy={busy === run.run_id}
              onApprove={() => approve(run.run_id)}
              onReject={() => reject(run.run_id)}
              onCorrect={(payload, note) => correct(run.run_id, payload, note)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
