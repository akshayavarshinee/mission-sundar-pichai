"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  api,
  type Health,
  type Metrics,
  type RunSummary,
  type Seed,
  type SubmitPayload,
  type SubmitRequest,
  type SubmitResult,
} from "@/lib/api";
import { useEvents, type ClearEvent } from "@/lib/useEvents";

const REFRESH_EVENTS = new Set([
  "run_created",
  "run_approved",
  "run_rejected",
  "run_corrected",
  "shipment_accepted",
  "lesson_promoted",
  "drift_alert",
  "metrics",
]);

interface WorkspaceValue {
  // live data
  events: ClearEvent[];
  connected: boolean;
  seeds: Seed[];
  runs: RunSummary[];
  approvals: RunSummary[];
  metrics: Metrics | null;
  health: Health | null;
  busy: string | null;
  error: string | null;
  driftAlert: ClearEvent | null;
  driftHealed: boolean;
  // actions
  refresh: () => Promise<void>;
  recover: (seedId: string) => Promise<RunSummary | null>;
  submit: (body: SubmitRequest) => Promise<SubmitResult>;
  approve: (runId: string, note?: string) => Promise<void>;
  reject: (runId: string, note?: string) => Promise<void>;
  correct: (runId: string, corrected: SubmitPayload, note?: string) => Promise<void>;
  learn: () => Promise<void>;
  drift: (seedId: string) => Promise<void>;
  playDemo: () => Promise<void>;
  seedHistory: () => Promise<void>;
  reset: () => Promise<void>;
  dismissDrift: () => void;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const { events, connected } = useEvents();
  const [seeds, setSeeds] = useState<Seed[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [approvals, setApprovals] = useState<RunSummary[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [driftAlert, setDriftAlert] = useState<ClearEvent | null>(null);
  const [driftHealed, setDriftHealed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [r, a, m] = await Promise.all([api.runs(), api.approvals(), api.metrics()]);
      setRuns([...r].reverse());
      setApprovals(a);
      setMetrics(m);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  // Initial load + periodic poll as a safety net alongside the event stream.
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

  const withBusy = useCallback(
    async <T,>(key: string, fn: () => Promise<T>): Promise<T | undefined> => {
      setBusy(key);
      try {
        const out = await fn();
        await refresh();
        return out;
      } catch (e) {
        setError((e as Error).message);
        return undefined;
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const recover = useCallback(
    async (seedId: string): Promise<RunSummary | null> => {
      const out = await withBusy(seedId, () => api.recover(seedId));
      return out && "run_id" in out ? (out as RunSummary) : null;
    },
    [withBusy]
  );

  const submit = useCallback(
    async (body: SubmitRequest): Promise<SubmitResult> => {
      setBusy("submit");
      try {
        const out = await api.submit(body);
        await refresh();
        return out;
      } finally {
        setBusy(null);
      }
    },
    [refresh]
  );

  const approve = useCallback(
    async (runId: string, note?: string) => {
      await withBusy(runId, () => api.approve(runId, note));
    },
    [withBusy]
  );

  const reject = useCallback(
    async (runId: string, note?: string) => {
      await withBusy(runId, () => api.reject(runId, note));
    },
    [withBusy]
  );

  const correct = useCallback(
    async (runId: string, corrected: SubmitPayload, note?: string) => {
      await withBusy(runId, () => api.correct(runId, corrected, note));
    },
    [withBusy]
  );

  const learn = useCallback(async () => {
    await withBusy("learn", () => api.learn());
  }, [withBusy]);

  const drift = useCallback(
    async (seedId: string) => {
      const res = await withBusy("drift", () => api.drift(seedId));
      if (res && "healed_status" in res && res.healed_status === "AUTO_RESOLVED") {
        setDriftHealed(true);
      }
    },
    [withBusy]
  );

  const playDemo = useCallback(async () => {
    setDriftAlert(null);
    setDriftHealed(false);
    const res = await withBusy("play", () => api.playDemo());
    const driftBeat = res?.beats.find((b) => b.beat === 7);
    if (driftBeat && driftBeat.healed_status === "AUTO_RESOLVED") setDriftHealed(true);
  }, [withBusy]);

  const seedHistory = useCallback(async () => {
    setDriftAlert(null);
    setDriftHealed(false);
    await withBusy("seed", () => api.seedHistory());
  }, [withBusy]);

  const reset = useCallback(async () => {
    await withBusy("reset", () => api.reset());
    setDriftAlert(null);
    setDriftHealed(false);
  }, [withBusy]);

  const dismissDrift = useCallback(() => setDriftAlert(null), []);

  const value = useMemo<WorkspaceValue>(
    () => ({
      events,
      connected,
      seeds,
      runs,
      approvals,
      metrics,
      health,
      busy,
      error,
      driftAlert,
      driftHealed,
      refresh,
      recover,
      submit,
      approve,
      reject,
      correct,
      learn,
      drift,
      playDemo,
      seedHistory,
      reset,
      dismissDrift,
    }),
    [
      events,
      connected,
      seeds,
      runs,
      approvals,
      metrics,
      health,
      busy,
      error,
      driftAlert,
      driftHealed,
      refresh,
      recover,
      submit,
      approve,
      reject,
      correct,
      learn,
      drift,
      playDemo,
      seedHistory,
      reset,
      dismissDrift,
    ]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return ctx;
}

export function useRun(runId: string): RunSummary | undefined {
  const { runs, approvals } = useWorkspace();
  return useMemo(
    () => [...runs, ...approvals].find((r) => r.run_id === runId),
    [runs, approvals, runId]
  );
}
