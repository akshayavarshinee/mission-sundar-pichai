"""Vector store abstraction with two backends.

* :class:`InMemoryVectorStore` — pure-Python cosine search; runs offline and is
  what the unit tests and key-less demos use.
* :class:`PgVectorStore` — Postgres + pgvector (the ``law_chunks`` /
  ``distilled_lessons`` tables from ``infra/cloudsql/001_init.sql``).

:func:`get_vector_store` picks the backend from ``CLEARPORT_VECTOR_BACKEND``.
The two stores share one interface so memory tiers ① and ③ are backend-agnostic.
"""

from __future__ import annotations

from typing import Protocol

import structlog
from pydantic import BaseModel, Field

from clearport.config import settings
from clearport.memory.embeddings import cosine

logger = structlog.get_logger(__name__)

# logical collection -> physical pgvector table
_TABLE_BY_COLLECTION = {
    "law": "law_chunks",
    "lessons": "distilled_lessons",
}


class VectorRecord(BaseModel):
    id: str
    text: str
    embedding: list[float]
    metadata: dict = Field(default_factory=dict)


class SearchHit(BaseModel):
    record: VectorRecord
    score: float


def _matches(metadata: dict, where: dict | None) -> bool:
    if not where:
        return True
    return all(metadata.get(k) == v for k, v in where.items())


class VectorStore(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...
    def search(
        self, query: list[float], k: int = 5, where: dict | None = None
    ) -> list[SearchHit]: ...
    def all_records(self, where: dict | None = None) -> list[VectorRecord]: ...
    def count(self) -> int: ...


class InMemoryVectorStore:
    """Cosine-similarity store backed by a dict. Deterministic and offline."""

    def __init__(self, collection: str = "default") -> None:
        self.collection = collection
        self._records: dict[str, VectorRecord] = {}

    def upsert(self, records: list[VectorRecord]) -> None:
        for r in records:
            self._records[r.id] = r

    def search(self, query: list[float], k: int = 5, where: dict | None = None) -> list[SearchHit]:
        hits = [
            SearchHit(record=r, score=cosine(query, r.embedding))
            for r in self._records.values()
            if _matches(r.metadata, where)
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    def all_records(self, where: dict | None = None) -> list[VectorRecord]:
        return [r for r in self._records.values() if _matches(r.metadata, where)]

    def count(self) -> int:
        return len(self._records)


class PgVectorStore:
    """pgvector-backed store. Lazy-imports SQLAlchemy; used in cloud/local-pg."""

    def __init__(self, table: str) -> None:
        self.table = table

    def _vector_literal(self, vec: list[float]) -> str:
        return "[" + ",".join(repr(float(x)) for x in vec) + "]"

    def upsert(self, records: list[VectorRecord]) -> None:
        from sqlalchemy import text

        from clearport.memory.db import get_engine

        stmt = text(
            f"""
            INSERT INTO {self.table} (id, content, embedding, metadata)
            VALUES (:id, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
            ON CONFLICT (id) DO UPDATE
              SET content = EXCLUDED.content,
                  embedding = EXCLUDED.embedding,
                  metadata = EXCLUDED.metadata
            """
        )
        import json

        with get_engine().begin() as conn:
            for r in records:
                conn.execute(
                    stmt,
                    {
                        "id": r.id,
                        "content": r.text,
                        "embedding": self._vector_literal(r.embedding),
                        "metadata": json.dumps(r.metadata),
                    },
                )

    def search(self, query: list[float], k: int = 5, where: dict | None = None) -> list[SearchHit]:
        from sqlalchemy import text

        from clearport.memory.db import get_engine

        where_sql = ""
        params: dict = {"q": self._vector_literal(query), "k": k}
        if where:
            clauses = []
            for i, (key, value) in enumerate(where.items()):
                clauses.append(f"metadata->>:wk{i} = :wv{i}")
                params[f"wk{i}"] = key
                params[f"wv{i}"] = str(value)
            where_sql = "WHERE " + " AND ".join(clauses)

        stmt = text(
            f"""
            SELECT id, content, embedding, metadata,
                   1 - (embedding <=> CAST(:q AS vector)) AS score
            FROM {self.table}
            {where_sql}
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :k
            """
        )
        hits: list[SearchHit] = []
        with get_engine().connect() as conn:
            for row in conn.execute(stmt, params):
                m = row.metadata if isinstance(row.metadata, dict) else {}
                hits.append(
                    SearchHit(
                        record=VectorRecord(id=row.id, text=row.content, embedding=[], metadata=m),
                        score=float(row.score),
                    )
                )
        return hits

    def all_records(self, where: dict | None = None) -> list[VectorRecord]:
        from sqlalchemy import text

        from clearport.memory.db import get_engine

        where_sql = ""
        params: dict = {}
        if where:
            clauses = []
            for i, (key, value) in enumerate(where.items()):
                clauses.append(f"metadata->>:wk{i} = :wv{i}")
                params[f"wk{i}"] = key
                params[f"wv{i}"] = str(value)
            where_sql = "WHERE " + " AND ".join(clauses)
        out: list[VectorRecord] = []
        with get_engine().connect() as conn:
            for row in conn.execute(text(f"SELECT id, content, metadata FROM {self.table} {where_sql}")):
                m = row.metadata if isinstance(row.metadata, dict) else {}
                out.append(VectorRecord(id=row.id, text=row.content, embedding=[], metadata=m))
        return out

    def count(self) -> int:
        from sqlalchemy import text

        from clearport.memory.db import get_engine

        with get_engine().connect() as conn:
            return int(conn.execute(text(f"SELECT count(*) FROM {self.table}")).scalar() or 0)


# Cache in-memory stores so repeated calls share state within a process.
_MEMORY_STORES: dict[str, InMemoryVectorStore] = {}


def get_vector_store(collection: str) -> VectorStore:
    backend = (settings.clearport_vector_backend or "memory").lower()
    if backend == "pg":
        table = _TABLE_BY_COLLECTION.get(collection, collection)
        return PgVectorStore(table)
    # default: in-memory (offline-friendly), shared per collection
    if collection not in _MEMORY_STORES:
        _MEMORY_STORES[collection] = InMemoryVectorStore(collection)
    return _MEMORY_STORES[collection]


def reset_memory_stores() -> None:
    """Test helper: clear cached in-memory collections."""
    _MEMORY_STORES.clear()
