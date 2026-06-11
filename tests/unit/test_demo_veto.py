"""The demo's eval-gate VETO is genuinely earned, not staged.

Seed S5 is a novel item (a hand-carved sitar bridge) the offline keyword
classifier cannot resolve, with an invalid declared HS. The recovery loop must
therefore fail the eval-gate and escalate — *without* any sabotaged classifier —
and then self-heal once a corrected lesson has been promoted.
"""

from __future__ import annotations

from clearport.agents.classifier import classify_hs
from clearport.api.store import RunStatus
from clearport.schemas import NormalizedErrorType
from clearport.seeds.shipments import get_seed
from clearport.service import ClearPortService
from clearport.validation.harness import run_seed


def test_novel_item_is_unclassifiable_offline() -> None:
    # The keyword table genuinely does not cover this item -> no code.
    result = classify_hs("Hand-carved rosewood sitar bridge (jawari)")
    assert result.code is None


def test_s5_trips_hs_invalid() -> None:
    rejection = run_seed(get_seed("S5"))
    assert rejection is not None
    assert rejection.normalized_error_type is NormalizedErrorType.HS_INVALID


def test_s5_earns_the_eval_gate_veto_without_sabotage() -> None:
    svc = ClearPortService()
    run = svc.submit_seed("S5")
    assert run is not None
    # The naive fix cannot resolve a novel code, so the eval-gate vetoes and the
    # run is held for a human rather than auto-resolved.
    assert run.result.verdict.passed is False
    assert run.status is not RunStatus.AUTO_RESOLVED


def test_s5_self_heals_after_promotion() -> None:
    svc = ClearPortService()
    from clearport.config import settings

    original = settings.clearport_promotion_min_evidence
    settings.clearport_promotion_min_evidence = 1
    try:
        run = svc.submit_seed("S5")
        corrected = get_seed("S5").payload.model_copy(deep=True)
        corrected.items[0].hs_tariff_number = "920992"
        svc.correct(run.id, corrected, note="broker classification")
        promotions = svc.run_learning()
        assert any(p.promoted for p in promotions)

        healed = svc.submit_seed("S5")
        assert "memory-lesson" in healed.result.patch.tool_calls_used
        assert healed.result.patch.patched_payload.items[0].hs_tariff_number == "920992"
        assert healed.result.verdict.passed is True
        assert healed.status is RunStatus.AUTO_RESOLVED
    finally:
        settings.clearport_promotion_min_evidence = original
