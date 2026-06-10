"""LLM-as-judge eval-gate — the hero capability.

The judge scores a patch on four booleans against the accepted baseline and the
cited law: ``structural_match``, ``required_fields_ok``, ``value_sanity``,
``law_consistent``. The patch PASSES only if all four hold.

A deterministic policy backstop (``policy_lint``) is always applied and the
result is **AND-ed** with Gemini's judgement — the model can only make the gate
*stricter*, never approve a declaration that still breaks a hard rule. This is
what lets the gate veto a wrong fix on a high-value parcel before any spend.
"""

from __future__ import annotations

import structlog

from clearport import llm
from clearport.config import settings
from clearport.memory.prompts import get_prompt
from clearport.schemas import (
    EvalRubric,
    EvalVerdict,
    NormalizedErrorType,
    PatchProposal,
    RejectionEvent,
)
from clearport.validation.errors import policy_lint

logger = structlog.get_logger(__name__)

_LOW_CERTAINTY_ERRORS = {NormalizedErrorType.UNKNOWN, NormalizedErrorType.OVERLAY_SCHEMA_DRIFT}


class Judge:
    def evaluate(
        self,
        rejection: RejectionEvent,
        patch: PatchProposal,
        baseline: list[dict] | None = None,
    ) -> EvalVerdict:
        rubric, confidence = self._deterministic(rejection, patch)
        judge_model = "deterministic-policy"
        rationale = self._deterministic_rationale(rubric)

        # Tighten with Gemini when available (AND-combine; never loosens).
        try:
            m_rubric, m_conf, m_rationale = self._model_judgement(rejection, patch, baseline or [])
            rubric = EvalRubric(
                structural_match=rubric.structural_match and m_rubric.structural_match,
                required_fields_ok=rubric.required_fields_ok and m_rubric.required_fields_ok,
                value_sanity=rubric.value_sanity and m_rubric.value_sanity,
                law_consistent=rubric.law_consistent and m_rubric.law_consistent,
            )
            confidence = round((confidence + m_conf) / 2, 3)
            rationale = m_rationale or rationale
            judge_model = settings.clearport_judge_model
        except llm.LLMUnavailable:
            pass
        except Exception as exc:  # noqa: BLE001 — fall back to deterministic gate
            logger.warning("judge.model_failed", error=str(exc))

        passed = rubric.all_pass
        if not passed:
            confidence = min(confidence, 0.4)

        verdict = EvalVerdict(
            patch_id=patch.id,
            judge_model=judge_model,
            passed=passed,
            confidence=confidence,
            rubric=rubric,
            rationale=rationale,
        )
        logger.info(
            "judge.verdict",
            patch=patch.id,
            passed=passed,
            confidence=confidence,
            model=judge_model,
        )
        return verdict

    # ── deterministic backstop ───────────────────────────────────────────
    def _deterministic(
        self, rejection: RejectionEvent, patch: PatchProposal
    ) -> tuple[EvalRubric, float]:
        payload = patch.patched_payload
        violation = policy_lint(payload)

        required_fields_ok = violation is None
        law_consistent = violation is None
        structural_match = bool(payload.items) and all(i.description for i in payload.items)
        value_sanity = all(
            i.value > 0 and i.quantity > 0 and i.weight_oz > 0 for i in payload.items
        ) and payload.total_value > 0

        rubric = EvalRubric(
            structural_match=structural_match,
            required_fields_ok=required_fields_ok,
            value_sanity=value_sanity,
            law_consistent=law_consistent,
        )

        if rubric.all_pass:
            confidence = 0.6 if rejection.normalized_error_type in _LOW_CERTAINTY_ERRORS else 0.9
        else:
            confidence = 0.35
        return rubric, confidence

    @staticmethod
    def _deterministic_rationale(rubric: EvalRubric) -> str:
        if rubric.all_pass:
            return "Patched declaration satisfies all required-field, value, and law checks."
        failed = [
            name
            for name, ok in (
                ("structural_match", rubric.structural_match),
                ("required_fields_ok", rubric.required_fields_ok),
                ("value_sanity", rubric.value_sanity),
                ("law_consistent", rubric.law_consistent),
            )
            if not ok
        ]
        return f"Failed checks: {', '.join(failed)}."

    # ── Gemini judgement ─────────────────────────────────────────────────
    def _model_judgement(
        self, rejection: RejectionEvent, patch: PatchProposal, baseline: list[dict]
    ) -> tuple[EvalRubric, float, str]:
        examples = "\n".join(
            f"- {b.get('input', {}).get('summary', '')}" for b in baseline[:5]
        ) or "(no baseline yet)"
        diffs = "; ".join(f"{d.field}: {d.before!r} -> {d.after!r}" for d in patch.field_diff)
        user = (
            f"Original rejection: {rejection.normalized_error_type.value}\n"
            f"Carrier message: {rejection.raw_error.message}\n"
            f"Applied changes: {diffs}\n"
            f"Patched value: ${patch.patched_payload.total_value:.2f}\n"
            f"Historically accepted shipments:\n{examples}\n\n"
            'Return JSON {"structural_match":bool,"required_fields_ok":bool,'
            '"value_sanity":bool,"law_consistent":bool,"confidence":number,'
            '"rationale":string}.'
        )
        data = llm.generate_json(get_prompt("judge"), user, temperature=0.0)
        rubric = EvalRubric(
            structural_match=bool(data.get("structural_match", False)),
            required_fields_ok=bool(data.get("required_fields_ok", False)),
            value_sanity=bool(data.get("value_sanity", False)),
            law_consistent=bool(data.get("law_consistent", False)),
        )
        confidence = float(data.get("confidence", 0.5) or 0.5)
        return rubric, confidence, str(data.get("rationale", ""))
