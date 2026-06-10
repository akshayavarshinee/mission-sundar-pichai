"""Embeddings with a Vertex/Gemini backend and a deterministic offline fallback.

* ``vertex`` — calls ``gemini-embedding-001`` via google-genai (Developer API or
  Vertex AI), 3072-dim.
* ``local``  — a deterministic feature-hashing embedding so the vector stores,
  recall, and tests work with no network and no API key. Overlapping tokens
  produce similar vectors, so cosine similarity is meaningful for the demo.

Backend is chosen by ``CLEARPORT_EMBEDDINGS_BACKEND`` (auto|vertex|local); on a
Vertex failure we fall back to local rather than crashing the loop.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed_dim() -> int:
    return settings.clearport_embed_dim


def _resolve_backend() -> str:
    backend = (settings.clearport_embeddings_backend or "auto").lower()
    if backend in ("vertex", "local"):
        return backend
    # auto
    if settings.google_cloud_project or settings.google_api_key:
        return "vertex"
    return "local"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _local_embed(text: str) -> list[float]:
    """Feature-hashing embedding: signed token hashing into ``embed_dim`` buckets."""
    # Cached because it is pure + deterministic; repeated demo runs stay warm.
    return list(_local_embed_cached(text, embed_dim()))


@lru_cache(maxsize=4096)
def _local_embed_cached(text: str, dim: int) -> tuple[float, ...]:
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        h = int.from_bytes(digest, "big")
        idx = h % dim
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(v / norm for v in vec)


def _genai_embed(texts: list[str]) -> list[list[float]]:
    from google import genai

    if settings.google_genai_use_vertexai:
        client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    else:
        client = genai.Client(api_key=settings.google_api_key)

    result = client.models.embed_content(
        model=settings.clearport_embed_model,
        contents=texts,
    )
    return [list(e.values) for e in result.embeddings]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    backend = _resolve_backend()
    if backend == "vertex":
        try:
            return _genai_embed(texts)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully, never crash recall
            logger.warning("embeddings.vertex_failed_fallback_local", error=str(exc))
    return [_local_embed(t) for t in texts]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
