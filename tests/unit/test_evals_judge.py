"""The eval-gate's LLM judge runs through Arize phoenix-evals and can only
*tighten* the deterministic policy gate — never loosen it.

The phoenix-evals classifier is mocked at the judge module's import seam so these
tests run offline and deterministically; what they pin is the AND-combine
contract and the offline fallback, not the model itself.
"""

from __future__ import annotations

import pytest

from clearport.config import settings
from clearport.eval import judge as judge_mod
from clearport.eval.baseline import get_baseline
from clearport.eval.judge import Judge
from clearport.schemas import EvalRubric
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed


def _pipeline(seed_id: str):
    """Drive the offline recall → diagnose → patch pipeline for one seed."""
    from clearport.agents.auditor import Auditor
    from clearport.agents.patch_engine import PatchEngine
    from clearport.memory.recall import recall

    rejection = run_seed(get_seed(seed_id))
    assert rejection is not None
    memory = recall(rejection)
    diagnosis = Auditor().diagnose(rejection, memory)
    patch = PatchEngine().patch(rejection, diagnosis)
    baseline = get_baseline(rejection.normalized_error_type)
    return rejection, patch, baseline, diagnosis


def test_offline_falls_back_to_deterministic_policy() -> None:
    # No live Phoenix in tests → evals disabled → the deterministic gate stands
    # alone and the verdict is attributed to the deterministic policy.
    rejection, patch, baseline, diagnosis = _pipeline("S4")
    verdict = Judge().evaluate(rejection, patch, baseline, diagnosis=diagnosis)
    assert verdict.judge_model == "deterministic-policy"


def test_model_invalid_vetoes_a_passing_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    # S4 passes the deterministic gate; an `invalid` model verdict must flip it
    # to FAIL via law_consistent, and carry the model's explanation.
    rejection, patch, baseline, diagnosis = _pipeline("S4")
    monkeypatch.setattr(judge_mod, "evals_available", lambda: True)
    monkeypatch.setattr(
        judge_mod,
        "judge_declaration",
        lambda **_: (False, "HS code unsupported by precedent", 0.0),
    )
    verdict = Judge().evaluate(rejection, patch, baseline, diagnosis=diagnosis)
    assert verdict.passed is False
    assert verdict.rubric.law_consistent is False
    assert "precedent" in verdict.rationale
    assert verdict.judge_model == settings.evals_model


def test_model_valid_keeps_a_passing_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    rejection, patch, baseline, diagnosis = _pipeline("S4")
    monkeypatch.setattr(judge_mod, "evals_available", lambda: True)
    monkeypatch.setattr(
        judge_mod,
        "judge_declaration",
        lambda **_: (True, "Matches accepted precedent.", 1.0),
    )
    verdict = Judge().evaluate(rejection, patch, baseline, diagnosis=diagnosis)
    assert verdict.passed is True
    assert verdict.rationale == "Matches accepted precedent."
    assert verdict.judge_model == settings.evals_model


def test_model_cannot_loosen_a_failing_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the deterministic gate to fail, then have the model say "valid":
    # the gate must remain FAILED (the model can never approve a hard-rule break).
    rejection, patch, baseline, diagnosis = _pipeline("S4")
    monkeypatch.setattr(Judge, "_deterministic", lambda self, p: EvalRubric())
    monkeypatch.setattr(judge_mod, "evals_available", lambda: True)
    monkeypatch.setattr(
        judge_mod, "judge_declaration", lambda **_: (True, "looks fine", 1.0)
    )
    verdict = Judge().evaluate(rejection, patch, baseline, diagnosis=diagnosis)
    assert verdict.passed is False
