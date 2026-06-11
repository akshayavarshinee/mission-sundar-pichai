// Typed REST client for the ClearPort backend. All shapes mirror the FastAPI
// responses in clearport/api/main.py.

import { resolveApiBase } from "./config";

export const API_BASE = resolveApiBase();
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

export interface ShipmentItem {
  description: string;
  quantity: number;
  value: number;
  hs_tariff_number: string | null;
  origin_country: string;
}

export interface DeclarationItem {
  description: string;
  quantity: number;
  value: number;
  weight_oz: number;
  origin_country: string;
  hs_tariff_number: string | null;
  currency: string;
}

export interface Declaration {
  contents_type: string;
  customs_certify: boolean;
  customs_signer: string | null;
  contents_explanation: string | null;
  restriction_type: string;
  restriction_comments: string | null;
  eel_pfc: string | null;
  non_delivery_option: string;
  items: DeclarationItem[];
}

export interface RunSummary {
  run_id: string;
  seed_id: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
  title: string;
  persona: string;
  lane: string;
  origin: string;
  dest: string;
  contents_type: string;
  items: ShipmentItem[];
  error_type: string;
  raw_error: string;
  customs_value: number | null;
  rejection_source: string;
  caught_by: string;
  human_note: string | null;
  root_cause: string;
  diagnosis: {
    confidence: number;
    confidence_basis: string;
  };
  declaration: Declaration;
  field_diff: FieldDiff[];
  rationale: string;
  eval: {
    passed: boolean;
    confidence: number;
    confidence_basis: string;
    rubric: Record<string, boolean>;
    model: string;
  };
  risk: {
    decision: string;
    score: number;
    components: { value: number; danger: number; confidence: number };
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

export interface SeedHistoryResult {
  runs_made: number;
  lessons_promoted: number;
  drift_healed: string | null;
  metrics: Metrics;
}

export interface Health {
  status: string;
  env: string;
}

export interface TraceStep {
  name: string;
  duration_ms: number;
  detail: string;
}

export interface RunTrace {
  run_id: string;
  rejection_id: string;
  recovery_seconds: number;
  total_ms: number;
  steps: TraceStep[];
}

export interface LawRecord {
  id: string;
  source: string;
  ref: string;
  hs_chapter: string | null;
  text: string;
}

export interface LessonRecord {
  id: string;
  key: { lane: string; hs_chapter: string; error_type: string };
  pattern: string;
  recommended_fix: string;
  evidence_count: number;
  baseline_score: number | null;
  candidate_score: number | null;
  promoted_at: string | null;
  pass_rate: number;
}

// ── Intelligence: aggregated LTM + Arize usage and the over-time series ──
export interface TierUsage {
  tier: string;
  name: string;
  backend: string;
  count: number;
  purpose: string;
  detail: string[];
}

export interface MemoryIntel {
  law_count: number;
  episodic_total: number;
  episodic_outcomes: number;
  episodic_corrections: number;
  episodic_accepted: number;
  lessons_count: number;
  prompts_count: number;
  prompt_names: string[];
  tiers: TierUsage[];
}

export interface EvalGateIntel {
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  law_vetoes: number;
  gemini_judged: number;
  judge_model: string;
}

export interface DatasetIntel {
  name: string;
  role: string;
  examples: number;
}

export interface ArizeIntel {
  live: boolean;
  mode: string;
  project: string;
  tracing_endpoint: string;
  traces_emitted: number;
  spans_emitted: number;
  eval_gate: EvalGateIntel;
  experiments_won: number;
  lessons_promoted: number;
  datasets: DatasetIntel[];
  mcp_tools: string[];
  episodic_backend: string;
  prompts_backend: string;
  embeddings_backend: string;
  vector_backend: string;
}

export interface ProgressionPoint {
  index: number;
  run_id: string;
  created_at: string;
  seed_id: string | null;
  error_type: string;
  recovery_seconds: number;
  status: string;
  decision: string;
  eval_passed: boolean;
  self_healed: boolean;
  used_classifier: boolean;
  cum_runs: number;
  cum_auto: number;
  cum_resolved: number;
  cum_auto_pct: number;
  cum_demurrage: number;
  cum_lessons: number;
}

export interface SelfHealPair {
  memory_key: string;
  error_type: string;
  first_seconds: number;
  repeat_seconds: number;
  speedup: number;
  occurrences: number;
  healed_from_memory: boolean;
}

export interface LessonProgressPoint {
  promoted_at: string | null;
  memory_key: string;
  error_type: string;
  recommended_fix: string;
  baseline_score: number | null;
  candidate_score: number | null;
  pass_rate: number;
  evidence_count: number;
  cum_lessons: number;
}

export interface IntelligenceReport {
  generated_at: string;
  memory: MemoryIntel;
  arize: ArizeIntel;
  progression: ProgressionPoint[];
  self_heal: SelfHealPair[];
  lesson_timeline: LessonProgressPoint[];
}

// A declaration line as submitted by an operator.
export interface SubmitItem {
  description: string;
  quantity: number;
  value: number;
  weight_oz: number;
  origin_country: string;
  hs_tariff_number: string | null;
  currency?: string;
}

export interface SubmitPayload {
  contents_type: string;
  customs_certify: boolean;
  customs_signer: string | null;
  contents_explanation: string | null;
  restriction_type: string;
  restriction_comments: string | null;
  eel_pfc: string | null;
  items: SubmitItem[];
}

export interface SubmitRequest {
  payload: SubmitPayload;
  origin: string;
  dest: string;
  persona: string | null;
  shipper_name: string | null;
}

export type SubmitResult =
  | RunSummary
  | { status: string; note: string };

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
  run: (runId: string) => req<RunSummary>(`/api/runs/${runId}`),
  trace: (runId: string) => req<RunTrace>(`/api/runs/${runId}/trace`),
  approvals: () => req<RunSummary[]>("/api/approvals"),
  metrics: () => req<Metrics>("/api/metrics"),
  recover: (seedId: string) =>
    req<RunSummary | { seed_id: string; status: string; note: string }>(
      `/api/recover/${seedId}`,
      { method: "POST" }
    ),
  submit: (body: SubmitRequest) =>
    req<SubmitResult>("/api/shipments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
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
  correct: (runId: string, corrected: SubmitPayload, note?: string) =>
    req<RunSummary>(`/api/approvals/${runId}/correct`, {
      method: "POST",
      body: JSON.stringify({ corrected, note: note ?? null }),
    }),
  learn: () => req<PromotionResult[]>("/api/learn", { method: "POST" }),
  drift: (seedId: string) =>
    req<DriftResult>(`/api/drift/${seedId}`, { method: "POST" }),
  reset: () => req<{ status: string }>("/api/reset", { method: "POST" }),
  playDemo: () => req<DemoResult>("/api/demo/play", { method: "POST" }),
  seedHistory: () =>
    req<SeedHistoryResult>("/api/demo/seed-history", { method: "POST" }),
  memoryLaw: () => req<LawRecord[]>("/api/memory/law"),
  memoryLessons: () => req<LessonRecord[]>("/api/memory/lessons"),
  intelligence: () => req<IntelligenceReport>("/api/intelligence"),
  health: () => req<Health>("/health"),
};

export function phoenixTraceUrl(): string {
  // Deep link to the Phoenix project so judges can inspect real telemetry.
  return `${PHOENIX_BASE}/projects`;
}
