"""Customs Auditor — diagnose the rejection, grounded by tiered memory.

Live mode reasons with Gemini over the recalled law citations, lessons, and
precedent; offline mode uses a deterministic map from the normalized error type.
Either way the Diagnosis carries its grounding (citations/lessons/precedent) so
the eval-gate and the dashboard can show *why*.
"""

from __future__ import annotations

import structlog

from clearport import llm
from clearport.eval.confidence import diagnosis_confidence
from clearport.memory.prompts import get_prompt
from clearport.memory.recall import RecalledMemory
from clearport.schemas import Diagnosis, NormalizedErrorType, RejectionEvent

logger = structlog.get_logger(__name__)

# error type -> (root cause, affected fields, base confidence)
_DIAGNOSIS_MAP: dict[NormalizedErrorType, tuple[str, list[str], float]] = {
    NormalizedErrorType.HS_INVALID: (
        "A line item carries an invalid or too-short HS tariff number; it must be "
        "a valid 6- or 10-digit HTS code.",
        ["items.hs_tariff_number"],
        0.9,
    ),
    NormalizedErrorType.EEI_THRESHOLD_MISMATCH: (
        "Declared value is at or above the $2,500 EEI threshold but the "
        "declaration claims NOEEI 30.37(a); a proper EEI/AES filing is required.",
        ["eel_pfc"],
        0.92,
    ),
    NormalizedErrorType.RESTRICTION_COMMENTS_MISSING: (
        "Goods are marked restricted but no restriction_comments explain the "
        "restriction and any permit.",
        ["restriction_comments"],
        0.9,
    ),
    NormalizedErrorType.SIGNER_MISSING: (
        "The declaration is certified (customs_certify=true) but customs_signer "
        "is empty.",
        ["customs_signer"],
        0.95,
    ),
    NormalizedErrorType.CONTENTS_EXPLANATION_MISSING: (
        "contents_type is 'other' but contents_explanation is missing.",
        ["contents_explanation"],
        0.93,
    ),
    NormalizedErrorType.ZERO_VALUE: (
        "A line item has a non-positive value, quantity, or weight.",
        ["items.value"],
        0.7,
    ),
    NormalizedErrorType.OVERLAY_SCHEMA_DRIFT: (
        "The destination registry changed a rule (schema drift); a previously "
        "accepted declaration no longer satisfies the new requirement.",
        ["overlay"],
        0.6,
    ),
    NormalizedErrorType.UNKNOWN: (
        "The rejection could not be confidently attributed to a known rule.",
        [],
        0.3,
    ),
}


class Auditor:
    def diagnose(self, rejection: RejectionEvent, memory: RecalledMemory) -> Diagnosis:
        root_cause, fields, base = _DIAGNOSIS_MAP.get(
            rejection.normalized_error_type, _DIAGNOSIS_MAP[NormalizedErrorType.UNKNOWN]
        )

        # Evidence-derived confidence: the per-rule base certainty, raised by law
        # grounding, corroborating precedent, and distilled lessons. The model's
        # self-assessment is deliberately not averaged in.
        conf = diagnosis_confidence(
            error_type=rejection.normalized_error_type,
            base=base,
            law_citations=memory.law_citations,
            precedents=memory.precedents,
            lessons=len(memory.lessons),
        )

        diagnosis = Diagnosis(
            rejection_id=rejection.id,
            root_cause=root_cause,
            affected_fields=list(fields),
            law_citations=memory.law_citations,
            retrieved_lessons=memory.lessons,
            precedent_examples=memory.precedents,
            confidence=conf.score,
            confidence_basis=conf.basis,
        )

        # Optionally enrich the narrative with Gemini, grounded by memory.
        try:
            diagnosis = self._enrich(rejection, memory, diagnosis)
        except llm.LLMUnavailable:
            pass
        except Exception as exc:  # noqa: BLE001 — keep the deterministic diagnosis
            logger.warning("auditor.enrich_failed", error=str(exc))

        logger.info(
            "auditor.diagnosis",
            rejection=rejection.id,
            error_type=rejection.normalized_error_type.value,
            confidence=diagnosis.confidence,
        )
        return diagnosis

    def _enrich(
        self, rejection: RejectionEvent, memory: RecalledMemory, base: Diagnosis
    ) -> Diagnosis:
        citations = "\n".join(f"- {c.source} {c.ref}: {c.text}" for c in memory.law_citations)
        lessons = "\n".join(f"- {lesson.recommended_fix}" for lesson in memory.lessons) or "(none)"
        user = (
            f"Rejection: {rejection.normalized_error_type.value}\n"
            f"Carrier message: {rejection.raw_error.message}\n"
            f"Declared value: ${rejection.customs_value}\n"
            f"Law citations:\n{citations or '(none)'}\n"
            f"Prior lessons:\n{lessons}\n"
            "Confirm the root_cause, affected_fields[], and confidence (0..1)."
        )
        data = llm.generate_json(get_prompt("auditor"), user, temperature=0.0)
        if data.get("root_cause"):
            base.root_cause = str(data["root_cause"])
        if isinstance(data.get("affected_fields"), list) and data["affected_fields"]:
            base.affected_fields = [str(f) for f in data["affected_fields"]]
        return base
