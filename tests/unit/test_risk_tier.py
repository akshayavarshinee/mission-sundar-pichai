"""Phase 5 unit tests: the risk tier decision logic in isolation."""

from __future__ import annotations

from clearport.eval.risk_tier import W_CONFIDENCE, assess
from clearport.schemas import (
    Decision,
    EvalRubric,
    EvalVerdict,
    PatchProposal,
    RestrictionType,
)
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed


def _verdict(passed: bool, confidence: float) -> EvalVerdict:
    return EvalVerdict(
        patch_id="patch_x",
        judge_model="deterministic-policy",
        passed=passed,
        confidence=confidence,
        rubric=EvalRubric(
            structural_match=passed,
            required_fields_ok=passed,
            value_sanity=passed,
            law_consistent=passed,
        ),
    )


def _patch(seed_id: str) -> tuple:
    rejection = run_seed(get_seed(seed_id))
    assert rejection is not None
    patch = PatchProposal(rejection_id=rejection.id, patched_payload=rejection.payload)
    return rejection, patch


def test_low_value_pass_is_auto() -> None:
    rejection, patch = _patch("S4")  # $90
    result = assess(rejection, patch, _verdict(True, 0.95))
    assert result.decision is Decision.AUTO
    assert result.hard_line_triggered is False


def test_over_threshold_is_hard_line_human() -> None:
    rejection, patch = _patch("S2")  # $3,200
    result = assess(rejection, patch, _verdict(True, 0.95))
    assert result.hard_line_triggered is True
    assert result.decision is Decision.HUMAN


def test_restricted_is_hard_line_human() -> None:
    rejection, patch = _patch("S3")  # quarantine restriction
    patch.patched_payload.restriction_type = RestrictionType.QUARANTINE
    result = assess(rejection, patch, _verdict(True, 0.95))
    assert result.hard_line_triggered is True
    assert result.decision is Decision.HUMAN


def test_failed_eval_is_human() -> None:
    rejection, patch = _patch("S4")
    result = assess(rejection, patch, _verdict(False, 0.3))
    assert result.decision is Decision.HUMAN
    assert any("eval-gate FAILED" in r for r in result.reasons)


def test_low_confidence_raises_confidence_component() -> None:
    rejection, patch = _patch("S1")  # $80, low value
    result = assess(rejection, patch, _verdict(True, 0.0))
    # 1 - confidence; a zero-confidence verdict maxes the confidence component
    assert result.confidence_component == 1.0
    assert result.total_score >= W_CONFIDENCE * 1.0


def test_expected_error_cost_escalates_midvalue_lowconfidence() -> None:
    # Below the $2,500 hard line but the expected cost of being wrong —
    # (1 − confidence) × value — is high, so a passing fix still goes to a human.
    rejection, patch = _patch("S2")
    patch.patched_payload.items[0].value = 1500.0  # under hard line
    result = assess(rejection, patch, _verdict(True, 0.6))
    # expected cost = (1 - 0.6) * 1500 = 600 > $400 ceiling
    assert result.expected_error_cost == 600.0
    assert result.decision is Decision.HUMAN
    assert any("expected error cost" in r for r in result.reasons)


def test_expected_error_cost_allows_confident_midvalue() -> None:
    # Same parcel, high confidence -> expected cost low -> stays AUTO.
    rejection, patch = _patch("S2")
    patch.patched_payload.items[0].value = 1500.0
    result = assess(rejection, patch, _verdict(True, 0.97))
    # expected cost = (1 - 0.97) * 1500 = 45 < $400 ceiling
    assert result.expected_error_cost == 45.0
    assert result.decision is Decision.AUTO
