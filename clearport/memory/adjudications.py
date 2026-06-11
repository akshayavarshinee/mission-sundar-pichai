"""Adjudication memory — the experience the adaptive judge learns from.

Every time the independent oracle (:mod:`clearport.eval.oracle`) labels a
declaration as accepted or rejected by the destination, that labelled case is
stored here. The :class:`~clearport.eval.learned_judge.LearnedJudge` retrieves
the semantically-nearest adjudications for a new case and uses their *real*
destination outcomes to anticipate the verdict — so the judge gets measurably
better as this corpus grows, with no retraining and nothing hard-coded.

The store keeps a small in-process vector index for kNN retrieval (offline,
deterministic) and — when Phoenix is live — mirrors each adjudication into the
episodic ② dataset so the growing experience is visible in the Phoenix UI.
"""

from __future__ import annotations

import structlog

from clearport.config import settings
from clearport.memory.embeddings import embed_text
from clearport.memory.vector_store import InMemoryVectorStore, VectorRecord
from clearport.schemas import Adjudication, NormalizedErrorType

logger = structlog.get_logger(__name__)


class AdjudicationStore:
    """Semantic store of independently-adjudicated declarations.

    Backed by an in-process cosine index (adjudications are operational memory,
    like episodic ② — not part of the pgvector law/lessons schema). Pass an
    ``episodic`` store to also mirror writes into the Phoenix-visible ② dataset.
    """

    def __init__(self, episodic=None) -> None:  # noqa: ANN001 — EpisodicMemory | None
        self._store = InMemoryVectorStore(collection="adjudications")
        self._episodic = episodic

    def add(self, adj: Adjudication) -> None:
        text = adj.features or f"{adj.error_type.value} {adj.memory_key}"
        record = VectorRecord(
            id=adj.id,
            text=text,
            embedding=embed_text(text),
            metadata={
                "adjudication": adj.model_dump(mode="json"),
                "error_type": adj.error_type.value,
                "accepted": str(adj.accepted).lower(),
            },
        )
        self._store.upsert([record])
        self._mirror_to_episodic(adj)
        logger.info(
            "adjudication.add",
            id=adj.id,
            accepted=adj.accepted,
            source=adj.source.value,
            error_type=adj.error_type.value,
        )

    def search(
        self,
        features: str,
        k: int = 5,
        error_type: NormalizedErrorType | None = None,
    ) -> list[tuple[Adjudication, float]]:
        """Return the ``k`` nearest adjudications to ``features`` with scores."""
        where = {"error_type": error_type.value} if error_type else None
        hits = self._store.search(embed_text(features), k=k, where=where)
        out: list[tuple[Adjudication, float]] = []
        for h in hits:
            payload = h.record.metadata.get("adjudication")
            if payload:
                out.append((Adjudication.model_validate(payload), round(h.score, 4)))
        return out

    def count(self) -> int:
        return self._store.count()

    def all(self) -> list[Adjudication]:
        return [
            Adjudication.model_validate(r.metadata["adjudication"])
            for r in self._store.all_records()
            if "adjudication" in r.metadata
        ]

    # ── Phoenix mirror (episodic ②) ──────────────────────────────────────
    def _mirror_to_episodic(self, adj: Adjudication) -> None:
        if self._episodic is None or not settings.adjudications_mirror_enabled:
            return
        try:
            self._episodic.add_example(
                input={"summary": adj.features, "error_type": adj.error_type.value},
                output={"accepted": adj.accepted},
                metadata={
                    "memory_key": adj.memory_key,
                    "error_type": adj.error_type.value,
                    "kind": "adjudication",
                    "oracle_source": adj.source.value,
                    "accepted": str(adj.accepted).lower(),
                },
            )
        except Exception as exc:  # noqa: BLE001 — mirroring is best-effort telemetry
            logger.warning("adjudication.mirror_failed", error=str(exc))


_STORE: AdjudicationStore | None = None


def get_adjudications() -> AdjudicationStore:
    """Process-wide adjudication store (the loop's shared, growing experience)."""
    global _STORE
    if _STORE is None:
        _STORE = AdjudicationStore()
    return _STORE


def reset_adjudications() -> None:
    """Test helper: drop the process-wide store so cases don't leak across tests."""
    global _STORE
    _STORE = None
