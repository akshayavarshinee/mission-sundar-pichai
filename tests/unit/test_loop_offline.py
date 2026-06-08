"""Phase 3-5 integration tests: the full recovery loop, offline + deterministic.

These exercise recall -> diagnose -> patch -> eval-gate -> risk -> act -> learn
end to end with no network, and assert the locked demo beats.
"""

from __future__ import annotations

from clearport.agents import patch_engine
from clearport.agents.classifier import HSClassification
from clearport.agents.orchestrator import LoopStatus, RecoveryLoop
from clearport.schemas import Decision
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed


def _run(seed_id: str):
    rejection = run_seed(get_seed(seed_id))
    assert rejection is not None
    return RecoveryLoop().run(rejection)


def test_s4_signer_fast_auto_heal() -> None:
    result = _run("S4")
    assert result.patch.patched_payload.customs_signer
    assert result.verdict.passed is True
    assert result.risk.decision is Decision.AUTO
    assert result.status is LoopStatus.AUTO_RESOLVED
    assert result.outcome.demurrage_saved_usd > 0


def test_s1_hs_classified_then_auto() -> None:
    result = _run("S1")
    assert "classify_hs" in result.patch.tool_calls_used
    assert result.patch.patched_payload.items[0].hs_tariff_number == "830249"
    assert result.risk.decision is Decision.AUTO
    assert result.status is LoopStatus.AUTO_RESOLVED


def test_s2_eei_hard_line_escalates() -> None:
    result = _run("S2")
    assert result.risk.hard_line_triggered is True
    assert result.risk.decision is Decision.HUMAN
    assert result.status is LoopStatus.AWAITING_APPROVAL
    assert any("hard line" in r for r in result.risk.reasons)


def test_s3_restricted_danger_escalates() -> None:
    result = _run("S3")
    assert result.patch.patched_payload.restriction_comments
    assert result.risk.decision is Decision.HUMAN
    assert result.status is LoopStatus.AWAITING_APPROVAL


def test_w1_wildcard_contents_explanation_auto() -> None:
    result = _run("W1")
    assert result.patch.patched_payload.contents_explanation
    assert result.verdict.passed is True
    assert result.status is LoopStatus.AUTO_RESOLVED


def test_wrong_hs_patch_is_vetoed_by_eval_gate(monkeypatch) -> None:
    # Force the classifier to fail so the HS stays invalid -> eval must veto.
    monkeypatch.setattr(
        patch_engine,
        "classify_hs",
        lambda *a, **k: HSClassification(
            code=None, description="x", confidence=0.1, source="none"
        ),
    )
    result = _run("S1")
    assert result.verdict.passed is False
    assert result.risk.decision is Decision.HUMAN
    assert any("eval-gate FAILED" in r for r in result.risk.reasons)
    assert result.status is LoopStatus.AWAITING_APPROVAL
