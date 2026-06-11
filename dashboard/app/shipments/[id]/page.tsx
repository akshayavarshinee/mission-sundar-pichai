"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { api, type RunSummary, type RunTrace } from "@/lib/api";
import { useWorkspace, useRun } from "@/lib/workspace";
import CaseFile from "@/components/case/CaseFile";

export default function ShipmentCasePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const ctxRun = useRun(id);
  const { busy, approve, reject, correct } = useWorkspace();

  const [fetchedRun, setFetchedRun] = useState<RunSummary | null>(null);
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [notFound, setNotFound] = useState(false);

  const run = ctxRun ?? fetchedRun ?? undefined;

  // Fallback fetch for direct deep-links before the workspace list has loaded.
  useEffect(() => {
    if (ctxRun) return;
    api
      .run(id)
      .then(setFetchedRun)
      .catch(() => setNotFound(true));
  }, [id, ctxRun]);

  // Per-step trace waterfall (durations don't change after the run completes).
  useEffect(() => {
    api.trace(id).then(setTrace).catch(() => setTrace(null));
  }, [id]);

  return (
    <div className="space-y-4">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" />
        Shipments
      </Link>

      {run ? (
        <CaseFile
          run={run}
          trace={trace}
          busy={busy === id}
          onApprove={() => approve(id)}
          onReject={() => reject(id)}
          onCorrect={(payload, note) => correct(id, payload, note)}
        />
      ) : notFound ? (
        <div className="card p-10 text-center text-sm text-muted">
          Shipment not found. It may have been cleared by a board reset.
        </div>
      ) : (
        <div className="card h-64 animate-pulse" />
      )}
    </div>
  );
}
