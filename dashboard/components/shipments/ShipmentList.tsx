"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, Package } from "lucide-react";
import type { RunSummary } from "@/lib/api";
import { fmtUsd, fmtSeconds } from "@/lib/format";
import {
  errorLabel,
  prettyLane,
  statusMeta,
  toneDot,
  type StatusGroup,
} from "@/lib/shipment";
import StatusPill from "@/components/ui/StatusPill";

type Filter = "all" | StatusGroup;

const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "attention", label: "Needs you" },
  { key: "cleared", label: "Cleared" },
  { key: "rejected", label: "Rejected" },
];

function ShipmentRow({ run }: { run: RunSummary }) {
  const meta = statusMeta(run.status);
  return (
    <Link
      href={`/shipments/${run.run_id}`}
      className="flex items-center gap-4 px-4 py-3 transition hover:bg-panel2"
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${toneDot[meta.tone]}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink">{run.title}</span>
          {run.seed_id ? (
            <span className="shrink-0 rounded border border-edge bg-panel2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
              {run.seed_id}
            </span>
          ) : null}
        </div>
        <div className="truncate text-xs text-muted">
          {prettyLane(run.origin, run.dest)} · {errorLabel(run.error_type)}
        </div>
      </div>

      <div className="hidden w-28 shrink-0 text-right sm:block">
        <div className="text-sm tabular-nums text-body">{fmtUsd(run.customs_value)}</div>
        <div className="text-[11px] text-faint">customs value</div>
      </div>

      <div className="hidden w-28 shrink-0 text-right md:block">
        {run.demurrage_saved_usd > 0 ? (
          <>
            <div className="text-sm tabular-nums text-good">{fmtUsd(run.demurrage_saved_usd)}</div>
            <div className="text-[11px] text-faint">saved · {fmtSeconds(run.recovery_seconds)}</div>
          </>
        ) : (
          <div className="text-[11px] text-faint">{fmtSeconds(run.recovery_seconds)}</div>
        )}
      </div>

      <div className="hidden shrink-0 sm:block">
        <StatusPill status={run.status} size="sm" />
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-faint" />
    </Link>
  );
}

export default function ShipmentList({ runs }: { runs: RunSummary[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: runs.length, attention: 0, cleared: 0, rejected: 0 };
    for (const r of runs) c[statusMeta(r.status).group] += 1;
    return c;
  }, [runs]);

  const filtered = useMemo(
    () => (filter === "all" ? runs : runs.filter((r) => statusMeta(r.status).group === filter)),
    [runs, filter]
  );

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-1 border-b border-edge px-3 py-2">
        {TABS.map((t) => {
          const active = filter === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                active ? "bg-accent/10 text-accent" : "text-muted hover:text-ink"
              }`}
            >
              {t.label}
              <span className="ml-1.5 text-xs text-faint">{counts[t.key]}</span>
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-14 text-center">
          <Package className="h-7 w-7 text-faint" />
          <p className="text-sm text-muted">
            {runs.length === 0
              ? "No shipments yet — submit a declaration or open the Demo drawer."
              : "Nothing in this view."}
          </p>
        </div>
      ) : (
        <div className="divide-y divide-edge">
          {filtered.map((run) => (
            <ShipmentRow key={run.run_id} run={run} />
          ))}
        </div>
      )}
    </div>
  );
}
