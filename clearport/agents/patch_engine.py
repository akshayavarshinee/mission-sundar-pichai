"""Document Patch Engine — rewrite the immutable declaration.

Produces a corrected :class:`CustomsPayload` (a deep copy, mirroring EasyPost's
immutable CustomsInfo) plus a field-level diff and a rationale. The corrections
are deterministic and rule-driven (so the loop works offline and is auditable);
Gemini, when live, only adds natural-language rationale and drafts free-text
fields. HS fixes call the complementary :mod:`classifier`.
"""

from __future__ import annotations

import re

import structlog

from clearport import llm
from clearport.agents.classifier import classify_hs
from clearport.schemas import (
    CustomsPayload,
    Diagnosis,
    FieldDiff,
    NormalizedErrorType,
    PatchProposal,
    RejectionEvent,
)
from clearport.validation.errors import EEI_THRESHOLD_USD, hs_is_valid

logger = structlog.get_logger(__name__)

_EEI_PENDING = "AES ITN PENDING (EEI filing required)"
_HS_RE = re.compile(r"\b(\d{6}(?:\d{4})?)\b")


class PatchEngine:
    def patch(self, rejection: RejectionEvent, diagnosis: Diagnosis) -> PatchProposal:
        payload: CustomsPayload = rejection.payload.model_copy_deep()
        diffs: list[FieldDiff] = []
        tools: list[str] = []
        rationale_bits: list[str] = []
        error_type = rejection.normalized_error_type

        if error_type is NormalizedErrorType.HS_INVALID:
            self._fix_hs(payload, diagnosis, diffs, tools, rationale_bits)
        elif error_type is NormalizedErrorType.EEI_THRESHOLD_MISMATCH:
            self._fix_eei(payload, diffs, rationale_bits)
        elif error_type is NormalizedErrorType.RESTRICTION_COMMENTS_MISSING:
            self._fix_restriction(payload, diffs, rationale_bits)
        elif error_type is NormalizedErrorType.SIGNER_MISSING:
            self._fix_signer(rejection, payload, diffs, rationale_bits)
        elif error_type is NormalizedErrorType.CONTENTS_EXPLANATION_MISSING:
            self._fix_contents_explanation(payload, diffs, rationale_bits)
        elif error_type is NormalizedErrorType.OVERLAY_SCHEMA_DRIFT:
            self._fix_overlay(payload, diffs, rationale_bits)
        elif error_type is NormalizedErrorType.ZERO_VALUE:
            self._fix_zero_value(payload, diffs, rationale_bits)
        else:
            rationale_bits.append("No deterministic fix available; routing for human review.")

        rationale = " ".join(rationale_bits) or "Corrected the diagnosed field(s)."
        rationale = self._maybe_enrich_rationale(rejection, diffs, rationale)

        proposal = PatchProposal(
            rejection_id=rejection.id,
            patched_payload=payload,
            field_diff=diffs,
            rationale=rationale,
            tool_calls_used=tools,
        )
        logger.info(
            "patch_engine.proposal",
            rejection=rejection.id,
            diffs=len(diffs),
            tools=tools,
        )
        return proposal

    # ── per-mode fixes ───────────────────────────────────────────────────
    def _fix_hs(self, payload, diagnosis, diffs, tools, rationale) -> None:
        citations = diagnosis.law_citations
        lesson_code = self._hs_from_lessons(diagnosis)
        for idx, item in enumerate(payload.items):
            if hs_is_valid(item.hs_tariff_number):
                continue
            before = item.hs_tariff_number

            # Self-heal first: a promoted lesson (memory ③) may already carry the
            # correct code for this error — the payoff of the learning loop.
            if lesson_code:
                item.hs_tariff_number = lesson_code
                tools.append("memory-lesson")
                diffs.append(
                    FieldDiff(field=f"items[{idx}].hs_tariff_number", before=before, after=lesson_code)
                )
                rationale.append(f"Self-healed from a promoted lesson: HTS {lesson_code}.")
                continue

            result = classify_hs(item.description, citations)
            tools.append("classify_hs")
            if result.code and hs_is_valid(result.code):
                item.hs_tariff_number = result.code
                diffs.append(
                    FieldDiff(field=f"items[{idx}].hs_tariff_number", before=before, after=result.code)
                )
                rationale.append(
                    f"Classified '{item.description}' to HTS {result.code} "
                    f"({result.source}, conf {result.confidence:.2f})."
                )
            else:
                rationale.append(
                    f"Could not confidently classify '{item.description}'; manual "
                    "classification required."
                )

    @staticmethod
    def _hs_from_lessons(diagnosis) -> str | None:
        """Extract a valid HTS code from any retrieved distilled lesson."""
        for lesson in diagnosis.retrieved_lessons:
            match = _HS_RE.search(lesson.recommended_fix or "")
            if match and hs_is_valid(match.group(1)):
                return match.group(1)
        return None


    def _fix_eei(self, payload, diffs, rationale) -> None:
        before = payload.eel_pfc
        payload.eel_pfc = _EEI_PENDING
        diffs.append(FieldDiff(field="eel_pfc", before=before, after=_EEI_PENDING))
        rationale.append(
            f"Value ${payload.total_value:.2f} is at/above the ${EEI_THRESHOLD_USD:.0f} "
            "threshold; switched from NOEEI to an EEI/AES filing (human files the ITN)."
        )

    def _fix_restriction(self, payload, diffs, rationale) -> None:
        before = payload.restriction_comments
        drafted = (
            f"{payload.restriction_type.value.replace('_', ' ').title()} controlled goods. "
            "Required permit/certificate attached; consignee authorized to receive."
        )
        payload.restriction_comments = drafted
        diffs.append(FieldDiff(field="restriction_comments", before=before, after=drafted))
        rationale.append("Drafted restriction_comments describing the restriction and permit.")

    def _fix_signer(self, rejection, payload, diffs, rationale) -> None:
        before = payload.customs_signer
        signer = (rejection.shipper_name or "Authorized Shipper").strip()
        payload.customs_signer = signer
        diffs.append(FieldDiff(field="customs_signer", before=before or "", after=signer))
        rationale.append(f"Filled customs_signer with the certifying shipper '{signer}'.")

    def _fix_contents_explanation(self, payload, diffs, rationale) -> None:
        before = payload.contents_explanation
        descriptions = ", ".join(i.description for i in payload.items)
        drafted = f"Assorted goods for retail sale: {descriptions}."
        payload.contents_explanation = drafted
        diffs.append(FieldDiff(field="contents_explanation", before=before, after=drafted))
        rationale.append("Drafted contents_explanation for the 'other' contents type.")

    def _fix_overlay(self, payload, diffs, rationale) -> None:
        # Heal the silent destination rule change by filling the newly-required
        # field (the overlay currently requires contents_explanation).
        from clearport.validation.regional_overlay import get_overlay

        required = get_overlay().rule.requires_field
        if required == "contents_explanation" and not (payload.contents_explanation or "").strip():
            self._fix_contents_explanation(payload, diffs, rationale)
        rationale.append("Healed a destination schema-drift rule change.")

    def _fix_zero_value(self, payload, diffs, rationale) -> None:
        for idx, item in enumerate(payload.items):
            if item.quantity <= 0:
                diffs.append(FieldDiff(field=f"items[{idx}].quantity", before="0", after="1"))
                item.quantity = 1
            if item.weight_oz <= 0:
                diffs.append(FieldDiff(field=f"items[{idx}].weight_oz", before="0", after="1.0"))
                item.weight_oz = 1.0
            # Value cannot be invented; flag for human confirmation.
            if item.value <= 0:
                rationale.append(
                    f"Line '{item.description}' has non-positive value; requires human "
                    "confirmation of the declared value."
                )

    # ── optional Gemini rationale ────────────────────────────────────────
    def _maybe_enrich_rationale(self, rejection, diffs, rationale) -> str:
        if not diffs:
            return rationale
        try:
            from clearport.memory.prompts import get_prompt

            changes = "; ".join(f"{d.field}: {d.before!r} -> {d.after!r}" for d in diffs)
            user = (
                f"Rejection: {rejection.normalized_error_type.value}. "
                f"Applied changes: {changes}. "
                "Write a one-sentence rationale for the customs officer. Return JSON "
                '{"rationale": "..."}.'
            )
            data = llm.generate_json(get_prompt("patch_engine"), user, temperature=0.1)
            if data.get("rationale"):
                return str(data["rationale"])
        except llm.LLMUnavailable:
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("patch_engine.enrich_failed", error=str(exc))
        return rationale
