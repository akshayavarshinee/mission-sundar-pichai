"""Promotion pipeline — cluster human corrections, run the experiment, promote.

When an experiment shows the human-corrected approach beats the agent's own
baseline, we synthesize a :class:`DistilledLesson` and write it to memory ③ with
its ``experiment_id`` and scores. Lessons never enter ③ any other way.
"""

from __future__ import annotations

import re

import structlog
from pydantic import BaseModel

from clearport.eval.experiments import ExperimentResult, run_experiment
from clearport.memory.episodic import EpisodicMemory, get_episodic
from clearport.memory.lessons import LessonsStore
from clearport.schemas import DistilledLesson, MemoryKey, NormalizedErrorType, utcnow

logger = structlog.get_logger(__name__)

_HS_RE = re.compile(r"\b(\d{6}(?:\d{4})?)\b")


class PromotionResult(BaseModel):
    promoted: bool
    experiment: ExperimentResult
    lesson_id: str | None = None
    recommended_fix: str | None = None


def _parse_key(memory_key: str) -> MemoryKey | None:
    try:
        lane, hs, error = memory_key.split("|")
        return MemoryKey(
            lane=lane,
            hs_chapter=hs.replace("hs", "", 1),
            error_type=NormalizedErrorType(error),
        )
    except (ValueError, KeyError):
        return None


def _synthesize_fix(error_type: NormalizedErrorType, examples: list[dict]) -> str:
    if error_type is NormalizedErrorType.HS_INVALID:
        for ex in reversed(examples):
            payload = ex.get("input", {}).get("patched_payload", {}) or {}
            for item in payload.get("items", []):
                code = str(item.get("hs_tariff_number") or "")
                if _HS_RE.fullmatch(code):
                    return f"Classify this item as HTS {code}."
    return {
        NormalizedErrorType.EEI_THRESHOLD_MISMATCH: (
            "File an EEI/AES ITN; do not claim NOEEI at or above $2,500 per line."
        ),
        NormalizedErrorType.RESTRICTION_COMMENTS_MISSING: (
            "Add restriction_comments describing the restriction and any permit."
        ),
        NormalizedErrorType.SIGNER_MISSING: (
            "Populate customs_signer with the certifying shipper's name."
        ),
        NormalizedErrorType.CONTENTS_EXPLANATION_MISSING: (
            "Add a contents_explanation when contents_type is 'other'."
        ),
    }.get(error_type, "Apply the human-corrected declaration fields.")


def _synthesize_lesson(
    key: MemoryKey, examples: list[dict], experiment: ExperimentResult
) -> DistilledLesson:
    fix = _synthesize_fix(key.error_type, examples)
    return DistilledLesson(
        key=key,
        pattern=f"Repeated {key.error_type.value} on lane {key.lane} (HS chapter {key.hs_chapter}).",
        recommended_fix=fix,
        evidence_count=experiment.evidence_count,
        experiment_id=experiment.experiment_id,
        baseline_score=experiment.baseline_score,
        candidate_score=experiment.candidate_score,
        promoted_at=utcnow(),
        pass_rate=experiment.candidate_score,
    )


def run_promotion(
    episodic: EpisodicMemory | None = None,
    lessons_store: LessonsStore | None = None,
) -> list[PromotionResult]:
    episodic = episodic or get_episodic()
    lessons_store = lessons_store or LessonsStore()

    # Candidate keys = those with at least one human correction.
    keys: dict[str, str] = {}
    for ex in episodic.get_examples():
        if ex.get("metadata", {}).get("kind") == "human_correction":
            meta = ex["metadata"]
            keys[meta.get("memory_key", "")] = meta.get("error_type", "")

    results: list[PromotionResult] = []
    for memory_key, error_type_str in keys.items():
        key = _parse_key(memory_key)
        if key is None:
            continue
        experiment = run_experiment(memory_key, key.error_type, episodic)
        if not experiment.passed:
            results.append(PromotionResult(promoted=False, experiment=experiment))
            continue

        examples = [
            ex
            for ex in episodic.get_examples(where={"memory_key": memory_key})
            if ex.get("metadata", {}).get("kind") == "human_correction"
        ]
        lesson = _synthesize_lesson(key, examples, experiment)
        lessons_store.add(lesson)
        logger.info("promotion.promoted", lesson=lesson.id, key=memory_key, fix=lesson.recommended_fix)
        results.append(
            PromotionResult(
                promoted=True,
                experiment=experiment,
                lesson_id=lesson.id,
                recommended_fix=lesson.recommended_fix,
            )
        )
    return results
