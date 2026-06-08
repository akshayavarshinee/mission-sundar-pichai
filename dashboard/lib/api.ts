// Typed REST client for the ClearPort backend. All shapes mirror the FastAPI
// responses in clearport/api/main.py.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";
export const PHOENIX_BASE =
  process.env.NEXT_PUBLIC_PHOENIX_BASE ?? "http://localhost:6006";

export interface Seed {
  id: string;
  persona: string;
  note: string | null;
  value: number;
  expected_error: string | null;
}

export interface FieldDiff {
  field: string;
  before: unknown;
  after: unknown;
}

export interface LawCitation {
  source: string;
  ref: string;
  text: string;
}

export interface RunSummary {
  run_id: string;
  seed_id: string | null;
  status: string;
  error_type: string;
  customs_value: number | null;
  root_cause: string;
  field_diff: FieldDiff[];
  rationale: string;
  eval: {
    passed: boolean;
    confidence: number;
    rubric: Record<string, boolean>;
    model: string;
  };
  risk: {
    decision: string;
    score: number;
    hard_line: boolean;
    reasons: string[];
  };
  law_citations: LawCitation[];
  vetoed_lesson_ids: string[];
  recovery_seconds: number;
  label_id: string | null;
  demurrage_saved_usd: number;
}

export interface Metrics {
  runs_total: number;
  auto_resolved: number;
  awaiting_approval: number;
  escalated: number;
  resolved: number;
  avg_recovery_seconds: number;
  broker_baseline_seconds: number;
  total_demurrage_saved_usd: number;
  pct_auto_resolved: number;
  self_heal_speedup: number;
  assumptions: string;
}

export interface DriftResult {
  drift?: {
    memory_key: string;
    observations: number;
    pass_rate: number;
    floor: number;
    window: number;
    drifted: boolean;
  };
  run_id?: string;
  healed_status?: string;
  field_diff?: FieldDiff[];
  drifted?: boolean;
  note?: string;
}

export interface PromotionResult {
  promoted: boolean;
  lesson_id: string | null;
  memory_key: string;
  recommended_fix: string | null;
  reason: string;
  experiment: {
    memory_key: string;
    baseline_score: number;
    candidate_score: number;
    margin: number;
    evidence_count: number;
    winner: string;
  };
}

export interface DemoResult {
  beats: Array<Record<string, unknown>>;
  metrics: Metrics;
}

export interface Health {
  status: string;
  env: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  seeds: () => req<Seed[]>("/api/seeds"),
  runs: () => req<RunSummary[]>("/api/runs"),
  approvals: () => req<RunSummary[]>("/api/approvals"),
  metrics: () => req<Metrics>("/api/metrics"),
  recover: (seedId: string) =>
    req<RunSummary | { seed_id: string; status: string; note: string }>(
      `/api/recover/${seedId}`,
      { method: "POST" }
    ),
  approve: (runId: string, note?: string) =>
    req<RunSummary>(`/api/approvals/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify({ note: note ?? null }),
    }),
  reject: (runId: string, note?: string) =>
    req<RunSummary>(`/api/approvals/${runId}/reject`, {
      method: "POST",
      body: JSON.stringify({ note: note ?? null }),
    }),
  learn: () => req<PromotionResult[]>("/api/learn", { method: "POST" }),
  drift: (seedId: string) =>
    req<DriftResult>(`/api/drift/${seedId}`, { method: "POST" }),
  reset: () => req<{ status: string }>("/api/reset", { method: "POST" }),
  playDemo: () => req<DemoResult>("/api/demo/play", { method: "POST" }),
  health: () => req<Health>("/health"),
};

export function phoenixTraceUrl(): string {
  // Deep link to the Phoenix project so judges can inspect real telemetry.
  return `${PHOENIX_BASE}/projects`;
}
