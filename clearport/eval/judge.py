"""LLM-as-judge eval-gate — the hero capability.

The patch is scored on four booleans against the accepted baseline and the cited
law: ``structural_match``, ``required_fields_ok``, ``value_sanity``,
``law_consistent``; it PASSES only if all four hold.

A deterministic policy backstop (``policy_lint``) is always applied and AND-ed
with an Arize **phoenix-evals** classifier (see ``clearport.arize.evals``) — the
model can only make the gate *stricter*, never approve a declaration that still
breaks a hard rule. Every judgement therefore runs through Arize's evaluation
engine and is traced to Phoenix. Offline, or on any failure, the deterministic
gate stands alone so the loop never blocks on the model.
"""

from __future__ import annotations

import structlog

from clearport.arize.evals import evals_available, judge_declaration
from clearport.config import settings
from clearport.eval.confidence import eval_confidence
from clearport.eval.learned_judge import LearnedJudge
from clearport.eval.oracle import features_of
from clearport.schemas import (
    Diagnosis,
    EvalRubric,
    EvalVerdict,
    LearnedVerdict,
    PatchProposal,
    RejectionEvent,
)
from clearport.validation.errors import policy_lint

logger = structlog.get_logger(__name__)


class Judge:
    def __init__(self, learned: LearnedJudge | None = None) -> None:
        # The learned judge is bound lazily to the process-wide adjudication
        # store; inject one (bound to a private store) for isolated evaluation.
        self.learned = learned or LearnedJudge()

    def evaluate(
        self,
        rejection: RejectionEvent,
        patch: PatchProposal,
        baseline: list[dict] | None = None,
        diagnosis: Diagnosis | None = None,
    ) -> EvalVerdict:
        rubric = self._deterministic(patch)
        judge_model = "deterministic-policy"
        rationale = self._deterministic_rationale(rubric)

        # Safety invariant: a recovery may correct a declaration but must never
        # *weaken* it — reducing the declared value or stripping certification is
        # a classic threshold-evasion attack and fails the gate outright,
        # regardless of what the policy lint or the model say.
        safety_reason = self._safety_violation(rejection, patch)
        if safety_reason:
            rubric = rubric.model_copy(update={"value_sanity": False})
            rationale = safety_reason

        # Tighten with the phoenix-evals judge when available (AND-combine; the
        # model can only make the gate stricter). The model decides one holistic
        # valid/invalid call — an `invalid` verdict vetoes via ``law_consistent`` —
        # while the confidence *scalar* is computed from evidence below, never
        # taken from the model's self-report.
        if evals_available():
            try:
                valid, explanation = self._evals_judgement(rejection, patch, baseline or [])
                if not valid:
                    rubric = rubric.model_copy(update={"law_consistent": False})
                rationale = explanation or rationale
                judge_model = settings.evals_model
            except Exception as exc:  # noqa: BLE001 — fall back to deterministic gate
                logger.warning("judge.evals_failed", error=str(exc))

        # Learned tightening: anticipate a *destination* rejection the carrier-side
        # policy lint can't see, generalising from independently-adjudicated
        # precedent (kNN offline / Gemini few-shot live). It only ever tightens —
        # a confident veto fails an otherwise-passing gate — and abstains until it
        # has enough relevant experience, so a cold store changes nothing.
        learned: LearnedVerdict | None = None
        if settings.learned_judge_enabled and rubric.all_pass:
            try:
                learned = self.learned.assess(
                    features_of(patch.patched_payload, rejection.normalized_error_type),
                    rejection.normalized_error_type,
                )
                if learned.is_veto:
                    rubric = rubric.model_copy(update={"law_consistent": False})
                    rationale = f"Learned judge veto — {learned.basis}."
                    judge_model = f"{judge_model}+learned:{learned.source}"
            except Exception as exc:  # noqa: BLE001 — never let learning break the gate
                logger.warning("judge.learned_failed", error=str(exc))

        passed = rubric.all_pass
        # Evidence-derived confidence: rubric outcome + law grounding + precedent
        # coverage − error-type ambiguity. Deterministic and inspectable.
        result = eval_confidence(
            rubric=rubric,
            error_type=rejection.normalized_error_type,
            law_citations=diagnosis.law_citations if diagnosis else None,
            baseline=baseline,
            has_changes=bool(patch.field_diff),
        )

        verdict = EvalVerdict(
            patch_id=patch.id,
            judge_model=judge_model,
            passed=passed,
            confidence=result.score,
            confidence_basis=result.basis,
            rubric=rubric,
            rationale=rationale,
            learned=learned,
        )
        logger.info(
            "judge.verdict",
            patch=patch.id,
            passed=passed,
            confidence=result.score,
            confidence_basis=result.basis,
            model=judge_model,
        )
        return verdict

    # ── deterministic backstop ───────────────────────────────────────────
    def _deterministic(self, patch: PatchProposal) -> EvalRubric:
        payload = patch.patched_payload
        violation = policy_lint(payload)

        required_fields_ok = violation is None
        law_consistent = violation is None
        structural_match = bool(payload.items) and all(i.description for i in payload.items)
        value_sanity = all(
            i.value > 0 and i.quantity > 0 and i.weight_oz > 0 for i in payload.items
        ) and payload.total_value > 0

        return EvalRubric(
            structural_match=structural_match,
            required_fields_ok=required_fields_ok,
            value_sanity=value_sanity,
            law_consistent=law_consistent,
        )

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

    # ── safety invariant (anti-threshold-evasion) ────────────────────────
    @staticmethod
    def _safety_violation(rejection: RejectionEvent, patch: PatchProposal) -> str | None:
        """Catch a patch that games the gate by weakening the declaration.

        A legitimate fix corrects a defect; it never lowers the declared value
        (which could duck the $2,500 EEI threshold) or removes certification.
        These are checked against the *original* declaration, so they hold even
        when the patched declaration would otherwise pass the policy lint.
        """
        original = rejection.payload.total_value
        patched = patch.patched_payload.total_value
        if patched < original - 0.01:
            return (
                f"Unsafe patch: declared value dropped from ${original:.2f} to "
                f"${patched:.2f}; a recovery must never understate value to evade "
                "a customs threshold."
            )
        if rejection.payload.customs_certify and not patch.patched_payload.customs_certify:
            return (
                "Unsafe patch: certification was removed from a certified "
                "declaration."
            )
        return None

    # ── phoenix-evals judgement ──────────────────────────────────────────
    def _evals_judgement(
        self, rejection: RejectionEvent, patch: PatchProposal, baseline: list[dict]
    ) -> tuple[bool, str]:
        """Run the Arize phoenix-evals classifier. Returns (valid, explanation)."""
        precedent = "\n".join(
            f"- {b.get('input', {}).get('summary', '')}" for b in baseline[:5]
        ) or "(no baseline yet)"
        diffs = "; ".join(
            f"{d.field}: {d.before!r} -> {d.after!r}" for d in patch.field_diff
        ) or "(no field changes)"
        valid, explanation, _score = judge_declaration(
            error_type=rejection.normalized_error_type.value,
            carrier_message=rejection.raw_error.message,
            diffs=diffs,
            total_value=patch.patched_payload.total_value,
            precedent=precedent,
        )
        return valid, explanation
