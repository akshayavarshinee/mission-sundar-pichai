"""Evidence-derived confidence is calculated, not LLM self-reported.

These pin the contract the judge cares about: the confidence scalar is a pure
function of rubric outcome, law grounding, precedent, and error-type certainty —
deterministic and reproducible with no model in the loop.
"""

from __future__ import annotations

from clearport.eval.confidence import diagnosis_confidence, eval_confidence
from clearport.eval.judge import Judge
from clearport.schemas import (
    EvalRubric,
    LawCitation,
    NormalizedErrorType,
    PatchProposal,
    PrecedentExample,
)
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed


def _rubric(ok: bool) -> EvalRubric:
    return EvalRubric(
        structural_match=ok, required_fields_ok=ok, value_sanity=ok, law_consistent=ok
    )


def test_failed_gate_is_capped_low() -> None:
    result = eval_confidence(
        rubric=EvalRubric(structural_match=True, required_fields_ok=False,
                          value_sanity=True, law_consistent=False),
        error_type=NormalizedErrorType.HS_INVALID,
    )
    assert result.score <= 0.45
    assert "gate failed" in result.basis


def test_passing_gate_rises_with_grounding() -> None:
    weak = eval_confidence(rubric=_rubric(True), error_type=NormalizedErrorType.HS_INVALID)
    strong = eval_confidence(
        rubric=_rubric(True),
        error_type=NormalizedErrorType.HS_INVALID,
        law_citations=[LawCitation(source="HTS", ref="8302.49", text="...", score=0.95)],
        baseline=[{"input": {"summary": "x"}}] * 5,
    )
    assert strong.score > weak.score
    assert 0.0 <= strong.score <= 0.99


def test_low_certainty_error_gets_penalty() -> None:
    normal = eval_confidence(rubric=_rubric(True), error_type=NormalizedErrorType.SIGNER_MISSING)
    ambiguous = eval_confidence(rubric=_rubric(True), error_type=NormalizedErrorType.UNKNOWN)
    assert ambiguous.score < normal.score
    assert ambiguous.certainty_penalty > 0


def test_confidence_is_deterministic() -> None:
    args = dict(rubric=_rubric(True), error_type=NormalizedErrorType.HS_INVALID,
                law_citations=[LawCitation(source="HTS", ref="x", text="y", score=0.8)])
    assert eval_confidence(**args).score == eval_confidence(**args).score


def test_diagnosis_confidence_rises_with_precedent() -> None:
    bare = diagnosis_confidence(error_type=NormalizedErrorType.HS_INVALID, base=0.9)
    rich = diagnosis_confidence(
        error_type=NormalizedErrorType.HS_INVALID,
        base=0.9,
        precedents=[PrecedentExample(example_id="e", summary="s", accepted=True)] * 3,
        lessons=1,
    )
    assert rich.score >= bare.score


def test_judge_offline_confidence_matches_evidence_formula() -> None:
    # Offline (no Gemini), the judge's confidence must equal the pure evidence
    # computation — proving the displayed number is calculated, not model-claimed.
    rejection = run_seed(get_seed("S4"))
    assert rejection is not None
    from clearport.agents.auditor import Auditor
    from clearport.agents.patch_engine import PatchEngine
    from clearport.eval.baseline import get_baseline
    from clearport.memory.recall import recall

    memory = recall(rejection)
    diagnosis = Auditor().diagnose(rejection, memory)
    patch = PatchEngine().patch(rejection, diagnosis)
    baseline = get_baseline(rejection.normalized_error_type)

    verdict = Judge().evaluate(rejection, patch, baseline, diagnosis=diagnosis)
    expected = eval_confidence(
        rubric=verdict.rubric,
        error_type=rejection.normalized_error_type,
        law_citations=diagnosis.law_citations,
        baseline=baseline,
        has_changes=bool(patch.field_diff),
    )
    assert verdict.confidence == expected.score
    assert verdict.confidence_basis == expected.basis
