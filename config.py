"""Central configuration for ClearPort.

All runtime settings are loaded from environment variables (see ``.env.example``)
via pydantic-settings, so the same code runs locally (docker-compose Phoenix +
Postgres) or in the cloud (Phoenix Cloud + Cloud SQL + Vertex AI) by changing
only environment values — never code.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeEnv(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class Settings(BaseSettings):
    """Strongly-typed view over the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Runtime mode ──────────────────────────────────────────────────────
    clearport_env: RuntimeEnv = RuntimeEnv.LOCAL

    # ── Gemini / Google ───────────────────────────────────────────────────
    google_api_key: str | None = None
    google_genai_use_vertexai: bool = False
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    clearport_gemini_model: str = "gemini-3-pro"
    clearport_judge_model: str = "gemini-3-pro"
    clearport_embed_model: str = "gemini-embedding-001"

    # ── Arize Phoenix ─────────────────────────────────────────────────────
    phoenix_host: str = "http://localhost:6006"
    phoenix_api_key: str | None = None
    phoenix_project: str = "clearport"
    phoenix_collector_endpoint: str | None = None
    phoenix_dataset: str = "clearport-outcomes"
    phoenix_baseline_dataset: str = "clearport-accepted-baseline"

    # ── EasyPost (test mode only) ─────────────────────────────────────────
    easypost_api_key: str | None = None
    easypost_mode: str = "test"

    # ── Persistence ───────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+psycopg://clearport:clearport@localhost:5432/clearport"
    )

    # ── Memory backends ───────────────────────────────────────────────────
    # "memory" runs the whole stack offline (no Postgres); "pg" uses pgvector.
    clearport_vector_backend: str = "memory"
    # ② episodic outcomes: "memory" (offline) or "phoenix" (dataset over MCP).
    clearport_episodic_backend: str = "memory"
    # ④ prompts: "local" (in-repo templates) or "phoenix" (prompt mgmt over MCP).
    clearport_prompts_backend: str = "local"
    # "auto" -> Vertex when a GCP project is set, else a deterministic local
    # hashing embedding; "vertex" / "local" force a backend.
    clearport_embeddings_backend: str = "auto"
    clearport_embed_dim: int = 3072  # gemini-embedding-001 dimensionality

    # ── Risk / tier ───────────────────────────────────────────────────────
    clearport_hard_line_usd: float = 2500.0
    clearport_risk_threshold: float = 0.55

    # ── Economics (for the $-saved metric) ────────────────────────────────
    clearport_broker_days: float = 3.0
    clearport_demurrage_per_day_usd: float = 250.0

    # ── Learning / promotion ──────────────────────────────────────────────
    clearport_promotion_min_evidence: int = 3
    clearport_promotion_margin: float = 0.10

    # ── Drift ─────────────────────────────────────────────────────────────
    clearport_drift_window: int = 10
    clearport_drift_passrate_floor: float = 0.6
    clearport_drift_min_sample: int = 3

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def collector_endpoint(self) -> str:
        """OTel span export endpoint; defaults to the Phoenix host."""
        return self.phoenix_collector_endpoint or self.phoenix_host

    @property
    def is_cloud(self) -> bool:
        return self.clearport_env is RuntimeEnv.CLOUD

    def require(self, *names: str) -> None:
        """Fail fast with a clear message if required settings are missing.

        Example:
            settings.require("easypost_api_key", "phoenix_host")
        """
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise RuntimeError(
                "Missing required configuration: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill these in."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()


# Convenience module-level singleton for ergonomic imports.
settings = get_settings()
