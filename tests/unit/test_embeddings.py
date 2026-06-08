"""Phase 2 unit tests: embeddings backend (local fallback)."""

from __future__ import annotations

import pytest

from clearport.memory.embeddings import cosine, embed_dim, embed_text, embed_texts


def test_embedding_has_expected_dim() -> None:
    assert len(embed_text("brass keychain")) == embed_dim()


def test_embedding_is_deterministic() -> None:
    assert embed_text("hand-block-printed silk scarf") == embed_text(
        "hand-block-printed silk scarf"
    )


def test_self_similarity_is_one() -> None:
    v = embed_text("cotton knit t-shirts")
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-6)


def test_overlapping_text_more_similar_than_disjoint() -> None:
    a = embed_text("cotton t-shirt textile apparel garment")
    b = embed_text("cotton t-shirt textile apparel clothing")
    c = embed_text("brass metal keychain fitting hardware")
    assert cosine(a, b) > cosine(a, c)


def test_embed_texts_batches() -> None:
    vecs = embed_texts(["one", "two", "three"])
    assert len(vecs) == 3
    assert all(len(v) == embed_dim() for v in vecs)


def test_empty_batch() -> None:
    assert embed_texts([]) == []
