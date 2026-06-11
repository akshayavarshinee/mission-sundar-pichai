"use client";

import Link from "next/link";
import { ArrowRight, FilePlus2, Inbox } from "lucide-react";
import { useWorkspace } from "@/lib/workspace";
import MetricsBar from "@/components/MetricsBar";
import ShipmentList from "@/components/shipments/ShipmentList";

export default function ShipmentsPage() {
  const { runs, approvals, metrics } = useWorkspace();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink">Shipments</h1>
          <p className="text-sm text-muted">
            Every cross-border declaration ClearPort has recovered, with its eval-gated verdict.
          </p>
        </div>
        <Link href="/submit" className="btn btn-accent h-9">
          <FilePlus2 className="h-4 w-4" />
          New shipment
        </Link>
      </div>

      {approvals.length > 0 ? (
        <Link
          href="/inbox"
          className="card flex items-center justify-between gap-3 border-warn/30 bg-warn/5 p-3 transition hover:border-warn/60"
        >
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-warn/15 text-warn">
              <Inbox className="h-5 w-5" />
            </span>
            <div>
              <div className="text-sm font-medium text-ink">
                {approvals.length} shipment{approvals.length > 1 ? "s" : ""} need your sign-off
              </div>
              <div className="text-xs text-muted">
                ClearPort safely paused these instead of spending money on an unsure fix.
              </div>
            </div>
          </div>
          <span className="flex items-center gap-1 text-sm font-medium text-warn">
            Review <ArrowRight className="h-4 w-4" />
          </span>
        </Link>
      ) : null}

      <MetricsBar metrics={metrics} />

      <ShipmentList runs={runs} />
    </div>
  );
}
