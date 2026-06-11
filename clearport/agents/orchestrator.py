"""Orchestrator — plans and drives the closed recovery loop.

    inspect -> recall -> diagnose -> patch -> verify(eval-gate) -> decide(risk)
            -> act(auto buy | human queue) -> learn(write outcome to ②)

This is the plain-Python engine (runs offline, fully traced when Phoenix is
present). ``adk_app.py`` exposes the same capability as a Gemini ADK agent with
the Phoenix MCP toolset for the Agent Builder surface.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from enum import Enum

import structlog
from pydantic import BaseModel, Field

from clearport.agents.auditor import Auditor
from clearport.agents.executor import ExecutionResult, Executor
from clearport.agents.patch_engine import PatchEngine
from clearport.arize.tracing import get_tracer
from clearport.config import settings
from clearport.eval.baseline import get_baseline
from clearport.eval.judge import Judge
from clearport.eval.risk_tier import assess
from clearport.memory.episodic import EpisodicMemory, get_episodic
from clearport.memory.recall import recall
from clearport.schemas import (
    ActionType,
    CarrierResult,
    CustomsPayload,
    Decision,
    Diagnosis,
    EvalVerdict,
    Outcome,
    PatchProposal,
    RejectionEvent,
    RiskAssessment,
    TraceStep,
)

logger = structlog.get_logger(__name__)


@contextmanager
def _timed_step(tracer, name: str, steps: list[TraceStep]):  # noqa: ANN001
    """Open the step's OTel span and record its wall-clock duration.

    The same measurement that becomes a Phoenix span is also captured locally so
    the dashboard can render a faithful trace waterfall offline.
    """
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as span:
        try:
            yield span
        finally:
            steps.append(
                TraceStep(name=name, duration_ms=round((time.perf_counter() - start) * 1000, 3))
            )


class LoopStatus(str, Enum):
    AUTO_RESOLVED = "AUTO_RESOLVED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REJECTED = "REJECTED"


class LoopResult(BaseModel):
    rejection: RejectionEvent
    diagnosis: Diagnosis
    patch: PatchProposal
    verdict: EvalVerdict
    risk: RiskAssessment
    execution: ExecutionResult | None = None
    outcome: Outcome
    status: LoopStatus
    recovery_seconds: float = 0.0
    vetoed_lesson_ids: list[str] = Field(default_factory=list)
    trace_steps: list[TraceStep] = Field(default_factory=list)


class RecoveryLoop:
    def __init__(self, episodic: EpisodicMemory | None = None) -> None:
        self.episodic = episodic or get_episodic()
        self.auditor = Auditor()
        self.patcher = PatchEngine()
        self.judge = Judge()
        self.executor = Executor()

    def run(self, rejection: RejectionEvent) -> LoopResult:
        tracer = get_tracer("clearport.loop")
        steps: list[TraceStep] = []
        t0 = time.perf_counter()
        with tracer.start_as_current_span("recover") as span:
            span.set_attribute("clearport.rejection_id", rejection.id)
            span.set_attribute("clearport.error_type", rejection.normalized_error_type.value)
            span.set_attribute("clearport.customs_value", rejection.customs_value)
            span.set_attribute("clearport.memory_key", rejection.memory_key.as_str())
            span.set_attribute("clearport.source", rejection.source.value)
            if rejection.seed_id:
                span.set_attribute("clearport.seed_id", rejection.seed_id)

            with _timed_step(tracer, "recall", steps) as rspan:
                memory = recall(rejection, episodic=self.episodic)
                rspan.set_attribute("clearport.memory.lessons_distilled", len(memory.lessons))
                rspan.set_attribute(
                    "clearport.memory.lessons_vetoed", len(memory.vetoed_lesson_ids)
                )
                rspan.set_attribute(
                    "clearport.memory.law_citations", len(memory.law_citations)
                )
                rspan.set_attribute("clearport.memory.precedents", len(memory.precedents))

            with _timed_step(tracer, "diagnose", steps) as gspan:
                diagnosis = self.auditor.diagnose(rejection, memory)
                gspan.set_attribute("clearport.root_cause", diagnosis.root_cause)
                gspan.set_attribute(
                    "clearport.diagnose.law_citations", len(diagnosis.law_citations)
                )

            with _timed_step(tracer, "patch", steps) as pspan:
                patch = self.patcher.patch(rejection, diagnosis)
                pspan.set_attribute("clearport.patch.field_count", len(patch.field_diff))

            with _timed_step(tracer, "verify", steps) as vspan:
                baseline = get_baseline(rejection.normalized_error_type, episodic=self.episodic)
                verdict = self.judge.evaluate(rejection, patch, baseline, diagnosis=diagnosis)
                vspan.set_attribute("clearport.eval_passed", verdict.passed)
                vspan.set_attribute("clearport.eval_confidence", verdict.confidence)
                # Record the full evaluation as span attributes so the verdict is
                # a first-class, visible artifact in the Phoenix trace (the eval
                # conscience), not just a pass/fail bit.
                vspan.set_attribute("clearport.eval.confidence_basis", verdict.confidence_basis)
                vspan.set_attribute("clearport.eval.judge_model", verdict.judge_model)
                vspan.set_attribute("clearport.eval.structural_match", verdict.rubric.structural_match)
                vspan.set_attribute(
                    "clearport.eval.required_fields_ok", verdict.rubric.required_fields_ok
                )
                vspan.set_attribute("clearport.eval.value_sanity", verdict.rubric.value_sanity)
                vspan.set_attribute("clearport.eval.law_consistent", verdict.rubric.law_consistent)

            with _timed_step(tracer, "decide", steps) as dspan:
                risk = assess(rejection, patch, verdict)
                dspan.set_attribute("clearport.decision", risk.decision.value)
                dspan.set_attribute("clearport.hard_line", risk.hard_line_triggered)

            with _timed_step(tracer, "act", steps) as aspan:
                execution, status, action = self._act(rejection, patch, risk)
                aspan.set_attribute("clearport.status", status.value)

            recovery_seconds = round(time.perf_counter() - t0, 4)
            outcome = self._build_outcome(
                rejection, patch, execution, action, recovery_seconds
            )

            with _timed_step(tracer, "learn", steps) as lspan:
                self._learn(rejection, patch, verdict, risk, outcome)
                lspan.set_attribute("clearport.memory_key", outcome.memory_key)
                lspan.set_attribute("clearport.outcome.action", outcome.action.value)

            span.set_attribute("clearport.recovery_seconds", recovery_seconds)
            span.set_attribute("clearport.final_status", status.value)

        return LoopResult(
            rejection=rejection,
            diagnosis=diagnosis,
            patch=patch,
            verdict=verdict,
            risk=risk,
            execution=execution,
            outcome=outcome,
            status=status,
            recovery_seconds=recovery_seconds,
            vetoed_lesson_ids=memory.vetoed_lesson_ids,
            trace_steps=steps,
        )

    # ── act / outcome / learn ────────────────────────────────────────────
    def _act(
        self, rejection: RejectionEvent, patch: PatchProposal, risk: RiskAssessment
    ) -> tuple[ExecutionResult, LoopStatus, ActionType]:
        if risk.decision is Decision.AUTO:
            execution = self.executor.finalize(rejection, patch, buy=True)
            if execution.carrier_result is CarrierResult.ACCEPTED:
                return execution, LoopStatus.AUTO_RESOLVED, ActionType.AUTO_BOUGHT
            return execution, LoopStatus.REJECTED, ActionType.PENDING
        # HUMAN: validate (no purchase) and hold for approval.
        execution = self.executor.finalize(rejection, patch, buy=False)
        return execution, LoopStatus.AWAITING_APPROVAL, ActionType.PENDING

    def _build_outcome(
        self,
        rejection: RejectionEvent,
        patch: PatchProposal,
        execution: ExecutionResult,
        action: ActionType,
        recovery_seconds: float,
    ) -> Outcome:
        accepted = execution.carrier_result is CarrierResult.ACCEPTED
        demurrage = (
            settings.clearport_broker_days * settings.clearport_demurrage_per_day_usd
            if accepted and action is ActionType.AUTO_BOUGHT
            else 0.0
        )
        return Outcome(
            patch_id=patch.id,
            rejection_id=rejection.id,
            memory_key=rejection.memory_key.as_str(),
            action=action,
            carrier_result=execution.carrier_result,
            label_id=execution.label_id,
            recovery_seconds=recovery_seconds,
            demurrage_saved_usd=round(demurrage, 2),
        )

    def _learn(
        self,
        rejection: RejectionEvent,
        patch: PatchProposal,
        verdict: EvalVerdict,
        risk: RiskAssessment,
        outcome: Outcome,
    ) -> None:
        """Write the outcome to episodic memory ② (the self-healing record)."""
        accepted = (
            outcome.action is ActionType.AUTO_BOUGHT
            and outcome.carrier_result is CarrierResult.ACCEPTED
        )
        input_ = {
            "summary": (
                f"{rejection.normalized_error_type.value} value=${rejection.customs_value:.2f} "
                f"decision={risk.decision.value}"
            ),
            "error_type": rejection.normalized_error_type.value,
            "memory_key": outcome.memory_key,
            "patched_payload": patch.patched_payload.model_dump(mode="json"),
            "field_diff": [d.model_dump() for d in patch.field_diff],
        }
        output = {"accepted": accepted, "action": outcome.action.value, "passed": verdict.passed}
        metadata = {
            "memory_key": outcome.memory_key,
            "error_type": rejection.normalized_error_type.value,
            "kind": "outcome",
            "seed_id": rejection.seed_id or "",
            "accepted": str(accepted).lower(),
        }
        try:
            self.episodic.add_example(input_, output, metadata)
        except Exception as exc:  # noqa: BLE001 — telemetry write must not break the loop
            logger.warning("loop.learn_failed", error=str(exc))

    # ── human-in-the-loop continuation (used by the API in Phase 6) ──────
    def buy_after_approval(
        self, rejection: RejectionEvent, patch: PatchProposal
    ) -> ExecutionResult:
        return self.executor.finalize(rejection, patch, buy=True)

    def learn_human_correction(
        self, rejection: RejectionEvent, corrected: CustomsPayload, *, accepted: bool
    ) -> str:
        """Persist a human correction to episodic ② — the seed for promotion."""
        input_ = {
            "summary": f"human-corrected {rejection.normalized_error_type.value}",
            "error_type": rejection.normalized_error_type.value,
            "memory_key": rejection.memory_key.as_str(),
            "patched_payload": corrected.model_dump(mode="json"),
        }
        output = {"accepted": accepted, "action": ActionType.HUMAN_CORRECTED.value}
        metadata = {
            "memory_key": rejection.memory_key.as_str(),
            "error_type": rejection.normalized_error_type.value,
            "kind": "human_correction",
            "accepted": str(accepted).lower(),
        }
        return self.episodic.add_example(input_, output, metadata)
