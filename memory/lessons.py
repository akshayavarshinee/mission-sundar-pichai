"""Memory tier ③ — distilled lessons (semantic-first, always-on).

A lesson only ever enters this store through the experiment-gated promotion
pipeline (Phase 7). Retrieval is by semantic similarity to the current
rejection, optionally filtered by error type. The full lesson is stored in the
record metadata so it round-trips through either backend.
"""

from __future__ import annotations

import structlog

from clearport.memory.embeddings import embed_text
from clearport.memory.vector_store import VectorRecord, get_vector_store
from clearport.schemas import DistilledLesson, NormalizedErrorType

logger = structlog.get_logger(__name__)


def _lesson_text(lesson: DistilledLesson) -> str:
    return f"{lesson.pattern} || fix: {lesson.recommended_fix} || key: {lesson.key.as_str()}"


class LessonsStore:
    def __init__(self) -> None:
        self.store = get_vector_store("lessons")

    def add(self, lesson: DistilledLesson) -> None:
        text = _lesson_text(lesson)
        record = VectorRecord(
            id=lesson.id,
            text=text,
            embedding=embed_text(text),
            metadata={
                "lesson": lesson.model_dump(mode="json"),
                "error_type": lesson.key.error_type.value,
                "lane": lesson.key.lane,
                "hs_chapter": lesson.key.hs_chapter,
            },
        )
        self.store.upsert([record])
        logger.info("lessons.add", lesson=lesson.id, key=lesson.key.as_str())

    def search(
        self, query_text: str, k: int = 3, error_type: NormalizedErrorType | None = None
    ) -> list[tuple[DistilledLesson, float]]:
        where = {"error_type": error_type.value} if error_type else None
        hits = self.store.search(embed_text(query_text), k=k, where=where)
        out: list[tuple[DistilledLesson, float]] = []
        for h in hits:
            payload = h.record.metadata.get("lesson")
            if payload:
                out.append((DistilledLesson.model_validate(payload), round(h.score, 4)))
        return out

    def all(self, error_type: NormalizedErrorType | None = None) -> list[DistilledLesson]:
        where = {"error_type": error_type.value} if error_type else None
        return [
            DistilledLesson.model_validate(r.metadata["lesson"])
            for r in self.store.all_records(where=where)
            if "lesson" in r.metadata
        ]

    def get(self, lesson_id: str) -> DistilledLesson | None:
        for lesson in self.all():
            if lesson.id == lesson_id:
                return lesson
        return None
