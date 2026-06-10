"""Risk tier — turn an eval verdict + shipment facts into AUTO or HUMAN.

    score = w_value·value_norm + w_danger·danger + w_confidence·(1 − eval_confidence)

Hard line (non-negotiable): customs value ≥ $2,500 **or** restricted/dangerous
goods ⇒ HUMAN. Otherwise a failed eval, or a score over threshold, ⇒ HUMAN. The
eval confidence is therefore load-bearing twice (gate + tier).
"""

from __future__ import annotations

import structlog

from clearport.config import settings
from clearport.schemas import (
    Decision,
    EvalVerdict,
    PatchProposal,
    RejectionEvent,
    RestrictionType,
    RiskAssessment,
)

logger = structlog.get_logger(__name__)

W_VALUE = 0.45
W_DANGER = 0.35
W_CONFIDENCE = 0.20


def assess(
    rejection: RejectionEvent, patch: PatchProposal, verdict: EvalVerdict
) -> RiskAssessment:
    value = patch.patched_payload.total_value
    hard_line = settings.clearport_hard_line_usd

    value_component = min(1.0, value / hard_line) if hard_line > 0 else 1.0
    is_restricted = patch.patched_payload.restriction_type is not RestrictionType.NONE
    danger_component = 1.0 if is_restricted else 0.0
    confidence_component = 1.0 - verdict.confidence

    total = round(
        W_VALUE * value_component
        + W_DANGER * danger_component
        + W_CONFIDENCE * confidence_component,
        4,
    )

    reasons: list[str] = []
    hard_line_triggered = False
    if value >= hard_line:
        hard_line_triggered = True
        reasons.append(f"customs value ${value:.2f} >= ${hard_line:.0f} hard line")
    if is_restricted:
        hard_line_triggered = True
        reasons.append(f"restricted goods ({patch.patched_payload.restriction_type.value})")

    if hard_line_triggered:
        decision = Decision.HUMAN
    elif not verdict.passed:
        decision = Decision.HUMAN
        reasons.append("eval-gate FAILED")
    elif total >= settings.clearport_risk_threshold:
        decision = Decision.HUMAN
        reasons.append(f"risk score {total:.2f} >= threshold {settings.clearport_risk_threshold:.2f}")
    else:
        decision = Decision.AUTO
        reasons.append(f"low risk (score {total:.2f}), eval passed")

    assessment = RiskAssessment(
        value_component=round(value_component, 4),
        danger_component=danger_component,
        confidence_component=round(confidence_component, 4),
        total_score=total,
        hard_line_triggered=hard_line_triggered,
        decision=decision,
        reasons=reasons,
    )
    logger.info(
        "risk.assessed",
        rejection=rejection.id,
        decision=decision.value,
        score=total,
        hard_line=hard_line_triggered,
    )
    return assessment
