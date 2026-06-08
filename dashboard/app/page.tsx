"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  API_BASE,
  phoenixTraceUrl,
  type Health,
  type Metrics,
  type RunSummary,
  type Seed,
} from "@/lib/api";
import { useEvents, type ClearEvent } from "@/lib/useEvents";
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
    <main className="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            ClearPort{" "}
            <span className="text-sm font-normal text-slate-400">
              customs-recovery agent
            </span>
          </h1>
          <p className="text-sm text-slate-400">
            Autonomous rejection recovery · Arize eval-gate · human approvals ·
            experiment-gated learning · drift detection
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
              health
                ? "border-good/40 text-good"
                : "border-bad/40 text-bad"
            }`}
            title={health ? `backend env: ${health.env}` : "backend unreachable"}
          >
            <span
              className={`h-2 w-2 rounded-full ${health ? "bg-good" : "bg-bad"}`}
            />
            {health ? `backend: ${health.env}` : "backend down"}
          </span>
          <a className="btn" href={phoenixTraceUrl()} target="_blank" rel="noreferrer">
            Phoenix traces ↗
          </a>
          <a className="btn" href={AGENT_BUILDER_URL} target="_blank" rel="noreferrer">
            Agent Builder app ↗
          </a>
        </div>
      </header>

      {error ? (
        <div className="card border-bad/40 bg-bad/5 p-3 text-sm text-bad">
          Backend error: {error}. Is the API running at{" "}
          <span className="font-mono">{API_BASE}</span>?
        </div>
      ) : null}

      <DriftBanner
        alert={driftAlert}
        healed={driftHealed}
        onDismiss={() => setDriftAlert(null)}
      />

      <MetricsBar metrics={metrics} />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <SeedControls
            seeds={seeds}
            busy={busy}
            onRecover={onRecover}
            onLearn={onLearn}
            onDrift={onDrift}
            onPlayDemo={onPlayDemo}
            onReset={onReset}
          />
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-200">
              Recovery verdicts
            </h2>
            {recentRuns.length === 0 ? (
              <div className="card p-6 text-center text-sm text-slate-500">
                No runs yet — fire a seed to see the eval-gate in action.
              </div>
            ) : (
              recentRuns.map((run) => (
                <EvalVerdictCard key={run.run_id} run={run} />
              ))
            )}
          </div>
        </div>

        <div className="space-y-4">
          <TraceTimeline events={events} connected={connected} />
          <ApprovalQueue
            approvals={approvals}
            busy={busy}
            onApprove={onApprove}
            onReject={onReject}
          />
        </div>
      </div>

      <footer className="pt-2 text-center text-xs text-slate-600">
        ClearPort · Gemini 3 + Google ADK + Arize Phoenix (MCP) · EasyPost test mode
      </footer>
    </main>
  );
}
