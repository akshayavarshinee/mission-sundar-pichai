"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Inbox, ShieldCheck } from "lucide-react";
import {
  api,
  API_BASE,
  type Health,
  type Metrics,
  type RunSummary,
  type Seed,
} from "@/lib/api";
import { useEvents, type ClearEvent } from "@/lib/useEvents";
import Topbar from "@/components/Topbar";
import MetricsBar from "@/components/MetricsBar";
import SeedControls from "@/components/SeedControls";
import TraceTimeline from "@/components/TraceTimeline";
import EvalVerdictCard from "@/components/EvalVerdictCard";
import ApprovalQueue from "@/components/ApprovalQueue";
import DriftBanner from "@/components/DriftBanner";

const AGENT_BUILDER_URL =
  process.env.NEXT_PUBLIC_AGENT_BUILDER_URL ?? "https://console.cloud.google.com/gen-app-builder";

const REFRESH_EVENTS = new Set([
  "run_created",
  "run_approved",
  "run_rejected",
  "shipment_accepted",
  "lesson_promoted",
  "drift_alert",
  "metrics",
]);

export default function Page() {
  const { events, connected } = useEvents();
  const [seeds, setSeeds] = useState<Seed[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [approvals, setApprovals] = useState<RunSummary[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [driftAlert, setDriftAlert] = useState<ClearEvent | null>(null);
  const [driftHealed, setDriftHealed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [r, a, m] = await Promise.all([
        api.runs(),
        api.approvals(),
        api.metrics(),
      ]);
      setRuns([...r].reverse());
      setApprovals(a);
      setMetrics(m);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  // Initial load + a periodic poll as a safety net alongside the event stream.
  useEffect(() => {
    api.seeds().then(setSeeds).catch((e) => setError((e as Error).message));
    api.health().then(setHealth).catch(() => setHealth(null));
    refresh();
    const id = setInterval(() => {
      refresh();
      api.health().then(setHealth).catch(() => setHealth(null));
    }, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  // React to the live event stream.
  useEffect(() => {
    const latest = events[0];
    if (!latest) return;
    if (latest.type === "drift_alert") {
      setDriftAlert(latest);
      setDriftHealed(false);
    }
    if (latest.type === "reset") {
      setDriftAlert(null);
      setDriftHealed(false);
    }
    if (REFRESH_EVENTS.has(latest.type)) refresh();
  }, [events, refresh]);

  const onRecover = useCallback(
    async (seedId: string) => {
      setBusy(seedId);
      try {
        await api.recover(seedId);
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const onApprove = useCallback(
    async (runId: string) => {
      setBusy(runId);
      try {
        await api.approve(runId);
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const onReject = useCallback(
    async (runId: string) => {
      setBusy(runId);
      try {
        await api.reject(runId);
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const onLearn = useCallback(async () => {
    setBusy("learn");
    try {
      await api.learn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const onDrift = useCallback(
    async (seedId: string) => {
      setBusy("drift");
      try {
        const res = await api.drift(seedId);
        if (res.healed_status === "AUTO_RESOLVED") setDriftHealed(true);
        await refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const onPlayDemo = useCallback(async () => {
    setBusy("play");
    setDriftAlert(null);
    setDriftHealed(false);
    try {
      const res = await api.playDemo();
      // The drift beat heals; reflect that in the banner if it fired.
      const driftBeat = res.beats.find((b) => b.beat === 7);
      if (driftBeat && driftBeat.healed_status === "AUTO_RESOLVED") {
        setDriftHealed(true);
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const onReset = useCallback(async () => {
    setBusy("reset");
    try {
      await api.reset();
      setDriftAlert(null);
      setDriftHealed(false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }, [refresh]);

  const recentRuns = useMemo(() => runs.slice(0, 6), [runs]);

  return (
    <div className="flex min-h-screen flex-col">
      <Topbar health={health} agentBuilderUrl={AGENT_BUILDER_URL} connected={connected} />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 md:p-6">
          {error ? (
            <div className="card flex items-start gap-2.5 border-bad/40 bg-bad/5 p-3 text-sm text-bad">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Backend error: {error}. Is the API running at{" "}
                <span className="font-mono">{API_BASE}</span>?
              </span>
            </div>
          ) : null}

          <DriftBanner
            alert={driftAlert}
            healed={driftHealed}
            onDismiss={() => setDriftAlert(null)}
          />

          <section id="overview" className="scroll-mt-20 space-y-3">
            <h2 className="section-title">
              <ShieldCheck className="h-4 w-4 text-accent" />
              Operational overview
            </h2>
            <MetricsBar metrics={metrics} />
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-6">
              <section id="controls" className="scroll-mt-20">
                <SeedControls
                  seeds={seeds}
                  busy={busy}
                  onRecover={onRecover}
                  onLearn={onLearn}
                  onDrift={onDrift}
                  onPlayDemo={onPlayDemo}
                  onReset={onReset}
                />
              </section>

              <section id="verdicts" className="scroll-mt-20 space-y-3">
                <h2 className="section-title">
                  <ShieldCheck className="h-4 w-4 text-accent" />
                  Recovery verdicts
                </h2>
                {recentRuns.length === 0 ? (
                  <div className="card flex flex-col items-center gap-2 p-8 text-center">
                    <Inbox className="h-6 w-6 text-faint" />
                    <p className="text-sm text-muted">
                      No runs yet — fire a seed to see the eval-gate in action.
                    </p>
                  </div>
                ) : (
                  recentRuns.map((run) => (
                    <EvalVerdictCard key={run.run_id} run={run} />
                  ))
                )}
              </section>
            </div>

            <div className="space-y-6">
              <section id="timeline" className="scroll-mt-20">
                <TraceTimeline events={events} connected={connected} />
              </section>
              <section id="approvals" className="scroll-mt-20">
                <ApprovalQueue
                  approvals={approvals}
                  busy={busy}
                  onApprove={onApprove}
                  onReject={onReject}
                />
              </section>
            </div>
          </div>

          <footer className="border-t border-edge pt-4 text-center text-xs text-faint">
            ClearPort · Gemini 3 + Google ADK + Arize Phoenix (MCP) · EasyPost
            test mode
          </footer>
        </main>
    </div>
  );
}
