"""Memory tier ① — static customs law, with a hard VETO over experience.

Two responsibilities:

* **Grounding** — semantically retrieve law chunks to cite in a diagnosis.
* **Veto** — :func:`law_veto` rejects a learned lesson whose recommended fix
  would violate hard law (e.g. claiming NOEEI at/above the $2,500 threshold, or
  proposing a malformed HTS code). This is what makes "law has veto over
  experience" real, and it is covered by a unit test.
"""

from __future__ import annotations

import re

import structlog

from clearport.memory.embeddings import embed_text, embed_texts
from clearport.memory.vector_store import VectorRecord, get_vector_store
from clearport.schemas import CustomsPayload, DistilledLesson, LawCitation, NormalizedErrorType
from clearport.seeds.kb.law import LAW_CHUNKS, law_fact_for
from clearport.validation.errors import EEI_THRESHOLD_USD, hs_is_valid

logger = structlog.get_logger(__name__)

_HS_RE = re.compile(r"\b(\d{6}(?:\d{4})?)\b")


class LawStore:
    def __init__(self) -> None:
        self.store = get_vector_store("law")

    def bootstrap(self, force: bool = False) -> int:
        """Embed and upsert the curated law chunks (idempotent)."""
        if not force and self.store.count() >= len(LAW_CHUNKS):
            return self.store.count()
        texts = [c["text"] for c in LAW_CHUNKS]
        vectors = embed_texts(texts)
        records = [
            VectorRecord(
                id=c["id"],
                text=c["text"],
                embedding=v,
                metadata={"source": c["source"], "ref": c["ref"], "hs_chapter": c["hs_chapter"]},
            )
            for c, v in zip(LAW_CHUNKS, vectors, strict=True)
        ]
        self.store.upsert(records)
        logger.info("law_store.bootstrapped", chunks=len(records))
        return len(records)

    def search(self, query: str, k: int = 3) -> list[LawCitation]:
        self.bootstrap()
        hits = self.store.search(embed_text(query), k=k)
        return [
            LawCitation(
                source=h.record.metadata.get("source", "LAW"),
                ref=h.record.metadata.get("ref", "?"),
                text=h.record.text,
                score=round(h.score, 4),
            )
            for h in hits
        ]


def law_veto(
    lesson: DistilledLesson, payload: CustomsPayload
) -> tuple[bool, LawCitation | None]:
    """Return ``(vetoed, citation)`` — True if the lesson violates hard law."""
    et = lesson.key.error_type
    fix = (lesson.recommended_fix or "").upper()

    vetoed = False
    if et is NormalizedErrorType.EEI_THRESHOLD_MISMATCH:
        if payload.total_value >= EEI_THRESHOLD_USD and "NOEEI" in fix:
            vetoed = True
    elif et is NormalizedErrorType.HS_INVALID:
        match = _HS_RE.search(lesson.recommended_fix or "")
        if match and not hs_is_valid(match.group(1)):
            vetoed = True

    if not vetoed:
        return False, None

    fact = law_fact_for(et)
    citation = (
        LawCitation(source=fact["source"], ref=fact["ref"], text=fact["text"], score=1.0)
        if fact
        else None
    )
    logger.info("law_store.veto", lesson=lesson.id, error_type=et.value)
    return True, citation
