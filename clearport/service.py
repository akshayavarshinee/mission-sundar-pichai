"""ClearPortService — the application layer the API and tests both use.

It runs the recovery loop, stores runs, manages the approval queue, applies human
decisions (approve / reject / correct), publishes live events, and computes
metrics. It depends on nothing web-specific so it is fully unit-testable offline.
"""

from __future__ import annotations

import structlog

from clearport.agents.orchestrator import RecoveryLoop
from clearport.api.events import EventBus
from clearport.api.metrics import Metrics, compute_metrics
from clearport.api.store import RecoveryRun, RunStatus, RunStore
from clearport.arize.drift import DriftMonitor
from clearport.config import settings
from clearport.memory.lessons import LessonsStore
from clearport.memory.promotion import PromotionResult, run_promotion
from clearport.schemas import (
    ActionType,
    CarrierResult,
    CustomsPayload,
    PatchProposal,
    RejectionEvent,
    utcnow,
)
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed

logger = structlog.get_logger(__name__)


class ApprovalError(RuntimeError):
    """Raised when an approval action targets a missing or non-open run."""


class ClearPortService:
    def __init__(self) -> None:
        self.loop = RecoveryLoop()
        self.store = RunStore()
        self.bus = EventBus()
        self.drift = DriftMonitor()

    # ── intake ───────────────────────────────────────────────────────────
    def submit_seed(self, seed_id: str) -> RecoveryRun | None:
        rejection = run_seed(get_seed(seed_id))
        if rejection is None:
            self.bus.publish("shipment_accepted", {"seed_id": seed_id})
            return None
        return self.submit_rejection(rejection)

    def submit_rejection(self, rejection: RejectionEvent) -> RecoveryRun:
        result = self.loop.run(rejection)
        run = self.store.add(RecoveryRun.from_result(result))
        self._publish_run("run_created", run)
        self._publish_metrics()
        if run.result.vetoed_lesson_ids:
            self.bus.publish("law_veto", {"run_id": run.id, "lessons": run.result.vetoed_lesson_ids})
        return run

    # ── queries ──────────────────────────────────────────────────────────
    def list_runs(self) -> list[RecoveryRun]:
        return self.store.list()

    def get_run(self, run_id: str) -> RecoveryRun | None:
        return self.store.get(run_id)

    # ── demo hygiene ─────────────────────────────────────────────────────
    def clear(self) -> None:
        """Reset all demo state in place, keeping the SSE bus (and its
        subscribers) alive so a connected dashboard keeps streaming."""
        from clearport.memory.episodic import reset_episodic
        from clearport.memory.vector_store import reset_memory_stores
        from clearport.validation.regional_overlay import reset_overlay

        reset_memory_stores()
        reset_episodic()
        reset_overlay()
        self.store = RunStore()
        self.drift = DriftMonitor()
        self.loop = RecoveryLoop()
        self.bus.publish("reset", {})
        self._publish_metrics()

    def list_approvals(self) -> list[RecoveryRun]:
        return self.store.open_approvals()

    def metrics(self) -> Metrics:
        return compute_metrics(self.store)

    # ── learning (experiment-gated promotion ② -> ③) ─────────────────────
    def run_learning(self) -> list[PromotionResult]:
        results = run_promotion(episodic=self.loop.episodic, lessons_store=LessonsStore())
        for r in results:
            if r.promoted:
                self.bus.publish(
                    "lesson_promoted",
                    {
                        "lesson_id": r.lesson_id,
                        "memory_key": r.experiment.memory_key,
                        "baseline_score": r.experiment.baseline_score,
                        "candidate_score": r.experiment.candidate_score,
                        "recommended_fix": r.recommended_fix,
                    },
                )
        return results

    # ── drift (silent destination rule change) ───────────────────────────
    def trigger_drift(self, seed_id: str = "C0") -> dict:
        """Flip the registry rule, raise a drift alert, then auto-heal the schema."""
        from clearport.validation.regional_overlay import get_overlay

        overlay = get_overlay()
        overlay.flip(True)
        rejection = overlay.make_rejection(get_seed(seed_id))
        if rejection is None:
            return {"drifted": False, "note": "seed already satisfies the new rule"}

        key = rejection.memory_key.as_str()
        # The silent change makes recent shipments on this lane miss the new rule.
        for _ in range(settings.clearport_drift_window):
            self.drift.observe(key, passed=False)
        status = self.drift.status(key)
        self.bus.publish(
            "drift_alert",
            {
                "memory_key": key,
                "pass_rate": status.pass_rate,
                "floor": status.floor,
                "rule": overlay.rule.description,
            },
        )

        # Heal the new schema autonomously and record the recovery.
        run = self.submit_rejection(rejection)
        self.drift.observe(key, passed=run.result.verdict.passed)
        # Restore the registry to baseline so the board stays usable for the
        # rest of the session (the silent change has been demonstrated + healed).
        overlay.flip(False)
        return {
            "drift": status.model_dump(),
            "run_id": run.id,
            "healed_status": run.status.value,
            "field_diff": [d.model_dump() for d in run.result.patch.field_diff],
        }

    # ── human decisions ──────────────────────────────────────────────────
    def approve(self, run_id: str, note: str | None = None) -> RecoveryRun:
        run = self._require_open(run_id)
        execution = self.loop.buy_after_approval(run.result.rejection, run.result.patch)
        accepted = execution.carrier_result is CarrierResult.ACCEPTED
        if accepted:
            self._mark_resolved(run, RunStatus.HUMAN_APPROVED, ActionType.HUMAN_APPROVED,
                                 execution.label_id, note)
        else:
            run.status = RunStatus.REJECTED
            run.resolved_at = utcnow()
            run.human_note = note
        self._record_human(run, accepted=accepted, kind="approval")
        self._publish_run("run_approved" if accepted else "run_rejected", run)
        self._publish_metrics()
        return run

    def reject(self, run_id: str, note: str | None = None) -> RecoveryRun:
        run = self._require_open(run_id)
        run.status = RunStatus.HUMAN_REJECTED
        run.resolved_at = utcnow()
        run.human_note = note
        run.result.outcome.action = ActionType.HUMAN_REJECTED
        self._record_human(run, accepted=False, kind="rejection")
        self._publish_run("run_rejected", run)
        self._publish_metrics()
        return run

    def correct(
        self, run_id: str, corrected: CustomsPayload, note: str | None = None
    ) -> RecoveryRun:
        run = self._require_open(run_id)
        rejection = run.result.rejection
        # The human correction is the seed for experiment-gated promotion (Phase 7).
        self.loop.learn_human_correction(rejection, corrected, accepted=True)
        patch = PatchProposal(
            rejection_id=rejection.id,
            patched_payload=corrected,
            rationale=f"Human correction. {note or ''}".strip(),
        )
        run.result.patch = patch
        execution = self.loop.buy_after_approval(rejection, patch)
        accepted = execution.carrier_result is CarrierResult.ACCEPTED
        if accepted:
            self._mark_resolved(run, RunStatus.HUMAN_CORRECTED, ActionType.HUMAN_CORRECTED,
                                 execution.label_id, note)
        else:
            run.status = RunStatus.REJECTED
            run.resolved_at = utcnow()
            run.human_note = note
        self._publish_run("run_corrected", run)
        self._publish_metrics()
        return run

    # ── helpers ──────────────────────────────────────────────────────────
    def _require_open(self, run_id: str) -> RecoveryRun:
        run = self.store.get(run_id)
        if run is None:
            raise ApprovalError(f"run {run_id} not found")
        if not run.is_open:
            raise ApprovalError(f"run {run_id} is not awaiting approval (status={run.status.value})")
        return run

    def _mark_resolved(
        self,
        run: RecoveryRun,
        status: RunStatus,
        action: ActionType,
        label_id: str | None,
        note: str | None,
    ) -> None:
        run.status = status
        run.resolved_at = utcnow()
        run.label_id = label_id
        run.human_note = note
        run.result.outcome.action = action
        run.result.outcome.carrier_result = CarrierResult.ACCEPTED
        run.result.outcome.label_id = label_id
        run.result.outcome.demurrage_saved_usd = round(
            settings.clearport_broker_days * settings.clearport_demurrage_per_day_usd, 2
        )

    def _record_human(self, run: RecoveryRun, *, accepted: bool, kind: str) -> None:
        try:
            self.loop.episodic.add_example(
                {"summary": f"human {kind} for {run.id}", "memory_key": run.result.outcome.memory_key},
                {"accepted": accepted, "action": run.result.outcome.action.value},
                {
                    "memory_key": run.result.outcome.memory_key,
                    "error_type": run.result.rejection.normalized_error_type.value,
                    "kind": f"human_{kind}",
                    "accepted": str(accepted).lower(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("service.record_human_failed", error=str(exc))

    def _publish_run(self, event_type: str, run: RecoveryRun) -> None:
        self.bus.publish(
            event_type,
            {
                "run_id": run.id,
                "seed_id": run.seed_id,
                "status": run.status.value,
                "error_type": run.result.rejection.normalized_error_type.value,
                "decision": run.result.risk.decision.value,
                "eval_passed": run.result.verdict.passed,
                "eval_confidence": run.result.verdict.confidence,
                "reasons": run.result.risk.reasons,
                "field_diff": [d.model_dump() for d in run.result.patch.field_diff],
                "recovery_seconds": run.result.recovery_seconds,
            },
        )

    def _publish_metrics(self) -> None:
        self.bus.publish("metrics", self.metrics().model_dump())


_SERVICE: ClearPortService | None = None


def get_service() -> ClearPortService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ClearPortService()
    return _SERVICE


def reset_service() -> None:
    """Test helper."""
    global _SERVICE
    _SERVICE = None
