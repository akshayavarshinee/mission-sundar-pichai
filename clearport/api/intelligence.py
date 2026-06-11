"""Intelligence aggregation — a faithful, derived view of how ClearPort learns.

Everything here is computed from *real* in-process state so the dashboard's
"Intelligence" page can show the long-term memory (LTM) tiers and the Arize
Phoenix touchpoints honestly, plus a progression series that demonstrates the
system improving over the course of a session:

* **Memory (LTM)** — live counts/usage of tiers ① law · ② episodic · ③ lessons
  · ④ prompts, read straight from the stores.
* **Arize** — traces/spans emitted, eval-gate pass/veto, experiment-gated
  promotions, datasets written, the MCP tool surface, and the active backends.
* **Progression** — a per-run cumulative series (auto-resolve %, demurrage,
  lessons known, self-heal markers) ordered in time.
* **Self-heal** — per-memory-key first-vs-repeat latency, the real basis for the
  headline self-heal speed-up.

Nothing is fabricated: counts come from the stores, durations from the captured
trace steps, and self-heal markers from ``patch.tool_calls_used``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from clearport.api.store import RecoveryRun, RunStatus
from clearport.config import settings
from clearport.schemas import utcnow

_RESOLVED = {RunStatus.AUTO_RESOLVED, RunStatus.HUMAN_APPROVED, RunStatus.HUMAN_CORRECTED}
_MEMORY_LESSON_TOOL = "memory-lesson"
_CLASSIFIER_TOOL = "classify_hs"


# ── response models ──────────────────────────────────────────────────────────
class TierUsage(BaseModel):
    tier: str
    name: str
    backend: str
    count: int
    purpose: str
    detail: list[str] = Field(default_factory=list)


class MemoryIntel(BaseModel):
    law_count: int
    episodic_total: int
    episodic_outcomes: int
    episodic_corrections: int
    episodic_accepted: int
    lessons_count: int
    prompts_count: int
    prompt_names: list[str]
    tiers: list[TierUsage]


class EvalGateIntel(BaseModel):
    total: int
    passed: int
    failed: int
    pass_rate: float
    law_vetoes: int
    gemini_judged: int
    judge_model: str


class DatasetIntel(BaseModel):
    name: str
    role: str
    examples: int


class ArizeIntel(BaseModel):
    live: bool
    mode: str
    project: str
    tracing_endpoint: str
    traces_emitted: int
    spans_emitted: int
    eval_gate: EvalGateIntel
    experiments_won: int
    lessons_promoted: int
    datasets: list[DatasetIntel]
    mcp_tools: list[str]
    episodic_backend: str
    prompts_backend: str
    embeddings_backend: str
    vector_backend: str


class ProgressionPoint(BaseModel):
    index: int
    run_id: str
    created_at: str
    seed_id: str | None
    error_type: str
    recovery_seconds: float
    status: str
    decision: str
    eval_passed: bool
    self_healed: bool
    used_classifier: bool
    cum_runs: int
    cum_auto: int
    cum_resolved: int
    cum_auto_pct: float
    cum_demurrage: float
    cum_lessons: int


class SelfHealPair(BaseModel):
    memory_key: str
    error_type: str
    first_seconds: float
    repeat_seconds: float
    speedup: float
    occurrences: int
    healed_from_memory: bool


class LessonProgressPoint(BaseModel):
    promoted_at: str | None
    memory_key: str
    error_type: str
    recommended_fix: str
    baseline_score: float | None
    candidate_score: float | None
    pass_rate: float
    evidence_count: int
    cum_lessons: int


class IntelligenceReport(BaseModel):
    generated_at: str
    memory: MemoryIntel
    arize: ArizeIntel
    progression: list[ProgressionPoint]
    self_heal: list[SelfHealPair]
    lesson_timeline: list[LessonProgressPoint]


# ── helpers ──────────────────────────────────────────────────────────────────
def _episodic_split(rows: list[dict]) -> tuple[int, int, int]:
    """Return (outcomes, human_corrections, accepted) over episodic ② examples."""
    outcomes = corrections = accepted = 0
    for r in rows:
        kind = str(r.get("metadata", {}).get("kind", ""))
        if kind == "outcome":
            outcomes += 1
        elif kind == "human_correction":
            corrections += 1
        out = r.get("output", {})
        if str(out.get("accepted")).lower() == "true":
            accepted += 1
    return outcomes, corrections, accepted


def _phoenix_live() -> bool:
    # "Live" means a real Phoenix is in the loop. Mirror the backend factories'
    # own notion of live (see memory/episodic.py + memory/prompts.py): episodic
    # ② is live on the in-process arize-phoenix-client ("phoenix-client"/"client")
    # or the MCP backend ("phoenix"); prompts ④ are live on "phoenix". A set
    # Phoenix API key (Arize cloud) also counts.
    episodic = (settings.clearport_episodic_backend or "").lower()
    prompts = (settings.clearport_prompts_backend or "").lower()
    return (
        bool(settings.phoenix_api_key)
        or episodic in {"phoenix", "phoenix-client", "client"}
        or prompts == "phoenix"
    )


# ── main entry ─────────────────────────────────────────────────────────────--
def compute_intelligence(service) -> IntelligenceReport:  # noqa: ANN001 — ClearPortService
    from clearport.arize.mcp_client import REQUIRED_TOOLS
    from clearport.memory.law_store import LawStore
    from clearport.memory.lessons import LessonsStore
    from clearport.memory.prompts import DEFAULT_PROMPTS

    runs: list[RecoveryRun] = service.list_runs()  # chronological (store sorts)

    # ── memory tiers (LTM) ──────────────────────────────────────────────
    law_store = LawStore()
    law_store.bootstrap()
    law_count = law_store.store.count()

    episodic_rows = service.loop.episodic.get_examples()
    ep_outcomes, ep_corrections, ep_accepted = _episodic_split(episodic_rows)

    lessons = sorted(
        LessonsStore().all(),
        key=lambda lesson: lesson.promoted_at or utcnow(),
    )
    lessons_count = len(lessons)

    prompt_names = list(DEFAULT_PROMPTS.keys())

    memory = MemoryIntel(
        law_count=law_count,
        episodic_total=len(episodic_rows),
        episodic_outcomes=ep_outcomes,
        episodic_corrections=ep_corrections,
        episodic_accepted=ep_accepted,
        lessons_count=lessons_count,
        prompts_count=len(prompt_names),
        prompt_names=prompt_names,
        tiers=[
            TierUsage(
                tier="①",
                name="Static law",
                backend=f"pgvector ({settings.clearport_vector_backend})",
                count=law_count,
                purpose="Grounds every diagnosis and holds a hard veto over learned experience.",
                detail=["HTS headings", "CBP CROSS rulings", "FTR §30.37 EEI"],
            ),
            TierUsage(
                tier="②",
                name="Episodic outcomes",
                backend=settings.clearport_episodic_backend,
                count=len(episodic_rows),
                purpose="Every loop outcome and human correction — the self-healing record and eval baseline.",
                detail=[
                    f"{ep_outcomes} agent outcomes",
                    f"{ep_corrections} human corrections",
                    f"{ep_accepted} accepted",
                ],
            ),
            TierUsage(
                tier="③",
                name="Distilled lessons",
                backend=f"pgvector ({settings.clearport_vector_backend})",
                count=lessons_count,
                purpose="Reusable fixes — promoted only after an Arize experiment beats baseline.",
                detail=[f"{lessons_count} promoted lesson(s)"],
            ),
            TierUsage(
                tier="④",
                name="Procedural prompts",
                backend=settings.clearport_prompts_backend,
                count=len(prompt_names),
                purpose="Versioned reasoning templates for the Auditor, Patch Engine, and Judge.",
                detail=prompt_names,
            ),
        ],
    )

    # ── per-run progression + eval-gate aggregation ─────────────────────
    progression: list[ProgressionPoint] = []
    spans = 0
    eval_total = eval_passed = law_vetoes = gemini_judged = 0
    judge_model = "deterministic-policy"
    cum_auto = cum_resolved = 0
    cum_demurrage = 0.0
    by_key: dict[str, list[tuple[float, bool]]] = {}

    for i, run in enumerate(runs, start=1):
        res = run.result
        spans += len(res.trace_steps) + 1  # +1 for the root "recover" span

        eval_total += 1
        if res.verdict.passed:
            eval_passed += 1
        law_vetoes += len(res.vetoed_lesson_ids)
        if res.verdict.judge_model and res.verdict.judge_model != "deterministic-policy":
            gemini_judged += 1
            judge_model = res.verdict.judge_model

        tools = res.patch.tool_calls_used
        self_healed = _MEMORY_LESSON_TOOL in tools
        used_classifier = _CLASSIFIER_TOOL in tools

        if run.status is RunStatus.AUTO_RESOLVED:
            cum_auto += 1
        if run.status in _RESOLVED:
            cum_resolved += 1
        cum_demurrage += res.outcome.demurrage_saved_usd

        # lessons "known" by this run's time (aligned by promotion timestamp)
        cum_lessons = sum(
            1 for lesson in lessons if lesson.promoted_at and lesson.promoted_at <= run.created_at
        )

        by_key.setdefault(res.outcome.memory_key, []).append(
            (res.recovery_seconds, self_healed)
        )

        progression.append(
            ProgressionPoint(
                index=i,
                run_id=run.id,
                created_at=run.created_at.isoformat(),
                seed_id=run.seed_id,
                error_type=res.rejection.normalized_error_type.value,
                recovery_seconds=res.recovery_seconds,
                status=run.status.value,
                decision=res.risk.decision.value,
                eval_passed=res.verdict.passed,
                self_healed=self_healed,
                used_classifier=used_classifier,
                cum_runs=i,
                cum_auto=cum_auto,
                cum_resolved=cum_resolved,
                cum_auto_pct=round(cum_auto / i * 100.0, 1),
                cum_demurrage=round(cum_demurrage, 2),
                cum_lessons=cum_lessons,
            )
        )

    eval_gate = EvalGateIntel(
        total=eval_total,
        passed=eval_passed,
        failed=eval_total - eval_passed,
        pass_rate=round(eval_passed / eval_total * 100.0, 1) if eval_total else 0.0,
        law_vetoes=law_vetoes,
        gemini_judged=gemini_judged,
        judge_model=judge_model,
    )

    # ── self-heal pairs (first vs repeat) per memory key ────────────────
    self_heal: list[SelfHealPair] = []
    for key, observations in by_key.items():
        if len(observations) < 2:
            continue
        first = observations[0][0]
        repeats = [s for s, _ in observations[1:]]
        repeat_avg = (sum(repeats) / len(repeats)) or 1e-9
        healed = any(flag for _, flag in observations[1:])
        # memory_key is "lane|hsNN|ERROR_TYPE" — surface the error type cleanly.
        error_type = key.split("|")[-1] if "|" in key else key
        self_heal.append(
            SelfHealPair(
                memory_key=key,
                error_type=error_type,
                first_seconds=round(first, 4),
                repeat_seconds=round(repeat_avg, 4),
                speedup=round(first / repeat_avg, 2),
                occurrences=len(observations),
                healed_from_memory=healed,
            )
        )

    # ── lesson learning curve (by promotion time) ───────────────────────
    lesson_timeline: list[LessonProgressPoint] = []
    for n, lesson in enumerate(lessons, start=1):
        lesson_timeline.append(
            LessonProgressPoint(
                promoted_at=lesson.promoted_at.isoformat() if lesson.promoted_at else None,
                memory_key=lesson.key.as_str(),
                error_type=lesson.key.error_type.value,
                recommended_fix=lesson.recommended_fix,
                baseline_score=lesson.baseline_score,
                candidate_score=lesson.candidate_score,
                pass_rate=lesson.pass_rate,
                evidence_count=lesson.evidence_count,
                cum_lessons=n,
            )
        )

    arize = ArizeIntel(
        live=_phoenix_live(),
        mode="live" if _phoenix_live() else "offline (deterministic fallback)",
        project=settings.phoenix_project,
        tracing_endpoint=settings.collector_endpoint,
        traces_emitted=len(runs),
        spans_emitted=spans,
        eval_gate=eval_gate,
        experiments_won=lessons_count,
        lessons_promoted=lessons_count,
        datasets=[
            DatasetIntel(
                name=settings.phoenix_dataset,
                role="episodic outcomes ②",
                examples=len(episodic_rows),
            ),
            DatasetIntel(
                name=settings.phoenix_baseline_dataset,
                role="accepted baseline",
                examples=ep_accepted,
            ),
        ],
        mcp_tools=sorted(REQUIRED_TOOLS),
        episodic_backend=settings.clearport_episodic_backend,
        prompts_backend=settings.clearport_prompts_backend,
        embeddings_backend=settings.clearport_embeddings_backend,
        vector_backend=settings.clearport_vector_backend,
    )

    return IntelligenceReport(
        generated_at=utcnow().isoformat(),
        memory=memory,
        arize=arize,
        progression=progression,
        self_heal=self_heal,
        lesson_timeline=lesson_timeline,
    )
