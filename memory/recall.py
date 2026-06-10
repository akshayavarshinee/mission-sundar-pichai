"""Tiered recall — the composition that makes Design B real.

Order of operations (semantic-first, law-veto):
  1. Semantically search ③ distilled lessons for the rejection.
  2. VETO any lesson that violates ① hard law (``law_veto``).
  3. Attach ① law citations for grounding.
  4. Fetch ② episodic precedent (when an episodic store is provided).

The result is a single :class:`RecalledMemory` the Auditor reasons over.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from clearport.memory.episodic import EpisodicMemory
from clearport.memory.law_store import LawStore, law_veto
from clearport.memory.lessons import LessonsStore
from clearport.schemas import LawCitation, LessonRef, PrecedentExample, RejectionEvent

logger = structlog.get_logger(__name__)


class RecalledMemory(BaseModel):
    lessons: list[LessonRef] = Field(default_factory=list)
    law_citations: list[LawCitation] = Field(default_factory=list)
    precedents: list[PrecedentExample] = Field(default_factory=list)
    vetoed_lesson_ids: list[str] = Field(default_factory=list)


def build_query_text(rejection: RejectionEvent) -> str:
    items = "; ".join(i.description for i in rejection.payload.items)
    return (
        f"error {rejection.normalized_error_type.value} "
        f"lane {rejection.lane} "
        f"hs_chapter {rejection.payload.primary_hs_chapter} "
        f"value {rejection.customs_value} "
        f"items {items}"
    )


def recall(
    rejection: RejectionEvent,
    *,
    lessons_store: LessonsStore | None = None,
    law_store: LawStore | None = None,
    episodic: EpisodicMemory | None = None,
    k_lessons: int = 3,
    k_law: int = 3,
) -> RecalledMemory:
    lessons_store = lessons_store or LessonsStore()
    law_store = law_store or LawStore()
    query = build_query_text(rejection)

    kept: list[LessonRef] = []
    vetoed: list[str] = []
    for lesson, score in lessons_store.search(
        query, k=k_lessons, error_type=rejection.normalized_error_type
    ):
        is_vetoed, _citation = law_veto(lesson, rejection.payload)
        if is_vetoed:
            vetoed.append(lesson.id)
            continue
        kept.append(
            LessonRef(
                lesson_id=lesson.id,
                key=lesson.key.as_str(),
                recommended_fix=lesson.recommended_fix,
                score=score,
            )
        )

    citations = law_store.search(query, k=k_law)

    precedents: list[PrecedentExample] = []
    if episodic is not None:
        precedents = episodic.precedents(rejection.memory_key.as_str(), k=3)

    logger.info(
        "recall.complete",
        lessons_kept=len(kept),
        lessons_vetoed=len(vetoed),
        citations=len(citations),
        precedents=len(precedents),
    )
    return RecalledMemory(
        lessons=kept, law_citations=citations, precedents=precedents, vetoed_lesson_ids=vetoed
    )
