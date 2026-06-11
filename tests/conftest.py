"""Shared pytest fixtures.

Unit tests must run with no network, no Docker, and no API keys. We pin every
ClearPort backend to its offline mode and reset shared in-memory stores between
tests so collections never leak across cases.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLEARPORT_ENV", "local")
    monkeypatch.setenv("PHOENIX_HOST", "http://localhost:6006")
    monkeypatch.setenv("PHOENIX_PROJECT", "clearport-test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://clearport:clearport@localhost:5432/clearport",
    )
    for leaky in ("GOOGLE_API_KEY", "EASYPOST_API_KEY", "PHOENIX_API_KEY"):
        monkeypatch.delenv(leaky, raising=False)

    # Pin the cached settings singleton to offline backends.
    from clearport.config import settings

    monkeypatch.setattr(settings, "google_api_key", None, raising=False)
    monkeypatch.setattr(settings, "google_cloud_project", None, raising=False)
    monkeypatch.setattr(settings, "easypost_api_key", None, raising=False)
    monkeypatch.setattr(settings, "clearport_vector_backend", "memory", raising=False)
    monkeypatch.setattr(settings, "clearport_embeddings_backend", "local", raising=False)
    monkeypatch.setattr(settings, "clearport_episodic_backend", "memory", raising=False)
    monkeypatch.setattr(settings, "clearport_prompts_backend", "local", raising=False)
    # Keep HS validation offline (bundled USITC subheading table) so unit tests
    # never touch the live hts.usitc.gov API.
    monkeypatch.setattr(settings, "clearport_hts_backend", "off", raising=False)

    # Reset shared stores so collections do not leak across tests.
    from clearport.memory.episodic import reset_episodic
    from clearport.memory.vector_store import reset_memory_stores
    from clearport.validation.hts_client import get_hts_validator
    from clearport.validation.regional_overlay import reset_overlay

    get_hts_validator.cache_clear()
    reset_memory_stores()
    reset_episodic()
    reset_overlay()
    yield
    get_hts_validator.cache_clear()
    reset_memory_stores()
    reset_episodic()
    reset_overlay()
