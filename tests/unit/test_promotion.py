"""Phase 7 tests: experiment-gated promotion and self-healing (the money shot).

Scenario (fully offline, deterministic):
  1. Break the HS classifier so the agent FAILS on S1 -> eval veto -> escalate.
  2. A human corrects the HS code -> recorded to episodic ②.
  3. An experiment shows the correction beats the agent's baseline -> PROMOTE to ③.
  4. Re-running S1 self-heals autonomously from the promoted lesson.
"""

from __future__ import annotations

import pytest

from clearport.agents import patch_engine
from clearport.agents.classifier import HSClassification
from clearport.api.store import RunStatus
from clearport.config import settings
from clearport.eval.experiments import run_experiment
from clearport.memory.lessons import LessonsStore
from clearport.memory.promotion import run_promotion
from clearport.schemas import Decision, NormalizedErrorType
from clearport.seeds.shipments import get_seed
from clearport.service import ClearPortService


@pytest.fixture
def broken_classifier(monkeypatch):
    monkeypatch.setattr(
        patch_engine,
        "classify_hs",
        lambda *a, **k: HSClassification(code=None, description="x", confidence=0.1, source="none"),
    )
    monkeypatch.setattr(settings, "clearport_promotion_min_evidence", 1, raising=False)


def test_failed_fix_promotes_then_self_heals(broken_classifier) -> None:
    svc = ClearPortService()

    # 1. agent fails -> eval veto -> human queue
    run = svc.submit_seed("S1")
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert run.result.verdict.passed is False
    assert run.result.risk.decision is Decision.HUMAN

    # 2. human correction with the right HS
    corrected = get_seed("S1").payload.model_copy(deep=True)
    corrected.items[0].hs_tariff_number = "830249"
    svc.correct(run.id, corrected, note="classified by broker")

    # 3. experiment-gated promotion
    lessons = LessonsStore()
    results = run_promotion(episodic=svc.loop.episodic, lessons_store=lessons)
    promoted = [r for r in results if r.promoted]
    assert promoted, "expected a promotion after a winning experiment"
    assert "830249" in (promoted[0].recommended_fix or "")

    # 4. re-run self-heals from ③ even though the classifier is still broken
    run2 = svc.submit_seed("S1")
    assert "memory-lesson" in run2.result.patch.tool_calls_used
    assert run2.result.patch.patched_payload.items[0].hs_tariff_number == "830249"
    assert run2.result.verdict.passed is True
    assert run2.status is RunStatus.AUTO_RESOLVED


def test_experiment_blocks_promotion_without_evidence(monkeypatch) -> None:
    # Require more evidence than exists -> experiment must NOT pass.
    monkeypatch.setattr(settings, "clearport_promotion_min_evidence", 5, raising=False)
    svc = ClearPortService()
    run = svc.submit_seed("S2")  # escalated (EEI)
    corrected = get_seed("S2").payload.model_copy(deep=True)
    corrected.eel_pfc = "AES X20250101123456"
    svc.correct(run.id, corrected)

    exp = run_experiment(
        run.result.rejection.memory_key.as_str(),
        NormalizedErrorType.EEI_THRESHOLD_MISMATCH,
        episodic=svc.loop.episodic,
    )
    assert exp.passed is False
