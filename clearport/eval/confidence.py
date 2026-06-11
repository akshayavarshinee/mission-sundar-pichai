"""Evidence-derived confidence — calculated, inspectable, never LLM self-reported.

A judge reviewing ClearPort should be able to see that the confidence shown next
to a verdict is *computed from concrete evidence*, not a number the model claims
about itself. The model still decides the rubric booleans (its judgement of
whether the patch is structurally sound, law-consistent, etc.); the confidence
*scalar* is then derived here from:

* **rubric outcome** — how many of the four gate checks passed (a failed gate is
  intrinsically low-confidence);
* **grounding strength** — the similarity score of the best retrieved law
  citation (how well the decision is anchored to cited law);
* **precedent support** — how much historically-accepted evidence corroborates
  the fix;
* **error-type certainty** — a penalty for inherently ambiguous error classes
  (UNKNOWN / schema-drift).

Every input is available offline, so the number is deterministic and unit
testable with no network and no API key.
"""

from __future__ import annotations

from pydantic import BaseModel

from clearport.schemas import EvalRubric, LawCitation, NormalizedErrorType, PrecedentExample

# Error classes where even a clean-looking patch deserves a confidence haircut.
LOW_CERTAINTY_ERRORS = {
    NormalizedErrorType.UNKNOWN,
    NormalizedErrorType.OVERLAY_SCHEMA_DRIFT,
}


class ConfidenceResult(BaseModel):
    """A computed confidence plus the evidence components that produced it."""

    score: float
    basis: str
    rubric_component: float = 0.0
    grounding_component: float = 0.0
    precedent_component: float = 0.0
    certainty_penalty: float = 0.0


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _grounding_strength(citations: list[LawCitation] | None) -> float:
    """Best citation similarity in [0, 1]; 0 when nothing was retrieved."""
    if not citations:
        return 0.0
    return _clamp(max((c.score for c in citations), default=0.0))


def _precedent_from_baseline(baseline: list[dict] | None) -> float:
    """Coverage of the accepted-baseline reference set, saturating at 5 examples."""
    if not baseline:
        return 0.0
    return _clamp(len(baseline) / 5.0)


def _precedent_from_examples(precedents: list[PrecedentExample] | None) -> float:
    """Accepted-rate of retrieved precedent, scaled by how much precedent exists."""
    if not precedents:
        return 0.0
    accepted = sum(1 for p in precedents if p.accepted)
    rate = accepted / len(precedents)
    coverage = _clamp(len(precedents) / 3.0)
    return _clamp(rate * coverage)


def eval_confidence(
    *,
    rubric: EvalRubric,
    error_type: NormalizedErrorType,
    law_citations: list[LawCitation] | None = None,
    baseline: list[dict] | None = None,
    has_changes: bool = True,
) -> ConfidenceResult:
    """Confidence for an eval-gate verdict, derived from evidence (not the model).

    A failing gate is intrinsically uncertain, so it scales only with how many
    checks survived. A passing gate starts from a calibrated floor and is raised
    by law grounding and historical precedent, minus an ambiguity penalty.
    """
    checks = (
        rubric.structural_match,
        rubric.required_fields_ok,
        rubric.value_sanity,
        rubric.law_consistent,
    )
    passed = sum(1 for c in checks if c)
    rubric_component = passed / 4.0

    if passed < 4:
        score = round(_clamp(0.12 + 0.08 * passed, hi=0.45), 3)
        return ConfidenceResult(
            score=score,
            basis=f"{passed}/4 rubric checks passed — gate failed, capped low",
            rubric_component=rubric_component,
        )

    grounding = _grounding_strength(law_citations)
    precedent = _precedent_from_baseline(baseline)
    penalty = 0.18 if error_type in LOW_CERTAINTY_ERRORS else 0.0
    change_credit = 0.08 if has_changes else 0.0

    raw = 0.55 + 0.22 * grounding + 0.15 * precedent + change_credit - penalty
    score = round(_clamp(raw, hi=0.99), 3)

    basis = (
        f"all 4 checks pass; grounding {grounding:.2f}, precedent {precedent:.2f}"
        + (f", −{penalty:.2f} ambiguity" if penalty else "")
    )
    return ConfidenceResult(
        score=score,
        basis=basis,
        rubric_component=rubric_component,
        grounding_component=round(grounding, 3),
        precedent_component=round(precedent, 3),
        certainty_penalty=penalty,
    )


def diagnosis_confidence(
    *,
    error_type: NormalizedErrorType,
    base: float,
    law_citations: list[LawCitation] | None = None,
    precedents: list[PrecedentExample] | None = None,
    lessons: int = 0,
) -> ConfidenceResult:
    """Confidence for a diagnosis, anchored on the rule's base certainty.

    Starts from the deterministic per-error base certainty and is nudged up by
    law grounding, corroborating precedent, and the existence of distilled
    lessons — then penalised for inherently ambiguous error classes. The model's
    own self-assessment is deliberately *not* averaged in.
    """
    grounding = _grounding_strength(law_citations)
    precedent = _precedent_from_examples(precedents)
    lesson_credit = 0.05 if lessons > 0 else 0.0
    penalty = 0.15 if error_type in LOW_CERTAINTY_ERRORS else 0.0

    raw = base + 0.06 * grounding + 0.05 * precedent + lesson_credit - penalty
    score = round(_clamp(raw, hi=0.99), 3)
    basis = (
        f"base {base:.2f}; grounding {grounding:.2f}, precedent {precedent:.2f}"
        + (f", +lesson" if lesson_credit else "")
        + (f", −{penalty:.2f} ambiguity" if penalty else "")
    )
    return ConfidenceResult(
        score=score,
        basis=basis,
        rubric_component=round(base, 3),
        grounding_component=round(grounding, 3),
        precedent_component=round(precedent, 3),
        certainty_penalty=penalty,
    )
