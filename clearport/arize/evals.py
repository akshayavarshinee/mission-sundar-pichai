"""Arize Phoenix Evals — the eval-gate's LLM judge.

The judge is implemented as a ``phoenix-evals`` classifier so every verdict runs
through Arize's evaluation engine (and is auto-traced to Phoenix as an evaluator
run) instead of a raw model call. The classifier returns a ``valid`` / ``invalid``
label with an explanation; the :class:`~clearport.eval.judge.Judge` AND-combines
it with the deterministic policy gate, so the model can only ever make the gate
*stricter* — never approve a declaration that still breaks a hard rule.

The judge rubric itself is sourced from memory tier ④ (``get_prompt("judge")``),
so when prompts are Phoenix-managed the judge's instruction is versioned in
Phoenix too. ``phoenix-evals`` and the LLM adapter are imported lazily, so this
module imports cleanly offline (no keys, no network) for static checks and the
laptop demo.
"""

from __future__ import annotations

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)

# Appended to the tier-④ judge rubric to supply the case under evaluation. The
# ``{placeholders}`` are bound from the dict passed to ``evaluate`` below.
_JUDGE_DATA_TEMPLATE = (
    "\n\n"
    "Original rejection: {error_type}\n"
    "Carrier message: {carrier_message}\n"
    "Applied changes: {diffs}\n"
    "Patched line value (USD): {total_value}\n"
    "Historically accepted shipments:\n{precedent}\n"
)

# Lazily-built singleton classifier (building it imports phoenix-evals + the LLM).
_classifier = None


def evals_available() -> bool:
    """True when the phoenix-evals judge should run and can be imported."""
    if not settings.evals_enabled:
        return False
    try:
        import phoenix.evals  # noqa: F401
        import phoenix.evals.llm  # noqa: F401
    except Exception:  # noqa: BLE001 — package missing or import-time failure
        return False
    return True


def _build_llm():  # noqa: ANN202 — phoenix.evals.llm.LLM, imported lazily
    from phoenix.evals.llm import LLM

    return LLM(provider=settings.clearport_evals_provider, model=settings.evals_model)


def _declaration_classifier():  # noqa: ANN202 — phoenix.evals classifier, lazy
    global _classifier
    if _classifier is None:
        from phoenix.evals import create_classifier

        from clearport.memory.prompts import get_prompt

        template = get_prompt("judge") + _JUDGE_DATA_TEMPLATE
        _classifier = create_classifier(
            name="declaration_valid",
            prompt_template=template,
            llm=_build_llm(),
            choices={"valid": 1.0, "invalid": 0.0},
        )
    return _classifier


def reset_classifier() -> None:
    """Drop the cached classifier (used by tests / after a prompt change)."""
    global _classifier
    _classifier = None


def judge_declaration(
    *,
    error_type: str,
    carrier_message: str,
    diffs: str,
    total_value: float,
    precedent: str,
) -> tuple[bool, str, float]:
    """Run the phoenix-evals classifier on one patched declaration.

    Returns ``(valid, explanation, score)``. Raises on any failure so the caller
    can fall back to the deterministic gate.
    """
    classifier = _declaration_classifier()
    scores = classifier.evaluate(
        {
            "error_type": error_type,
            "carrier_message": carrier_message,
            "diffs": diffs,
            "total_value": f"{total_value:.2f}",
            "precedent": precedent,
        }
    )
    score = scores[0]
    label = (getattr(score, "label", None) or "").strip().lower()
    explanation = getattr(score, "explanation", "") or ""
    numeric = float(getattr(score, "score", 0.0) or 0.0)
    valid = label == "valid"
    logger.info("judge.evals", label=label or "(none)", score=numeric)
    return valid, explanation, numeric
