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

    # ── Evaluation conscience (Arize Phoenix evals as the LLM judge) ──────
    # "auto" turns the phoenix-evals judge on whenever a live Phoenix is in the
    # loop; "on"/"off" force it. Offline (or on any failure) the judge falls back
    # to the deterministic policy gate, so the loop never blocks on the model.
    clearport_evals_enabled: str = "auto"
    # phoenix.evals LLM adapter. "litellm" reuses the VM's Vertex ADC via the
    # "vertex_ai/<model>" route (no extra key); "google" uses a Gemini API key.
    clearport_evals_provider: str = "litellm"
    # Judge model for phoenix-evals; defaults to "vertex_ai/<judge_model>".
    clearport_evals_model: str | None = None

    # ── Span annotations (write eval verdicts back onto Phoenix spans) ─────
    # "auto" writes the eval verdict as a Phoenix span annotation when Phoenix
    # is live; "on"/"off" force it. Best-effort — never blocks or breaks a run.
    clearport_annotations_enabled: str = "auto"

    # ── Phoenix MCP (runtime read-back via @arizeai/phoenix-mcp) ───────────
    # Gates the on-demand /api/investigate Phoenix MCP read-back. "auto" enables
    # it when Phoenix is live; "on"/"off" force it. Best-effort: a missing npx /
    # Node runtime or server error degrades to the deterministic explanation.
    clearport_mcp_enabled: str = "auto"

    # ── Independent oracle (destination ground truth, NOT policy_lint) ─────
    # The live "destination customs officer" LLM is an extra, independent model
    # call, so it is opt-in even live; "on"/"auto" enable it when Gemini is live.
    # The deterministic destination registry is always available as the floor.
    clearport_oracle_officer: str = "off"

    # ── Adaptive eval-gate (judge that learns from adjudicated experience) ─
    # The learned judge predicts the destination's verdict from semantically-
    # similar adjudicated precedent (kNN offline / LLM few-shot live). It only
    # ever *tightens* the gate and abstains until it has enough relevant
    # experience, so an empty store leaves the gate's behaviour unchanged.
    # "auto" enables it when Phoenix is live; "on"/"off" force it.
    clearport_learned_judge: str = "auto"
    clearport_learned_judge_k: int = 5
    clearport_learned_judge_min_evidence: int = 3
    clearport_learned_judge_min_similarity: float = 0.25
    # Fraction of (similarity-weighted) neighbours that must have been rejected
    # by the destination before the learned judge will veto a carrier-clean fix.
    clearport_learned_judge_veto_fraction: float = 0.6
    # Mirror each adjudication into episodic ② (so it shows up in Phoenix). "auto"
    # follows whether Phoenix is live; "on"/"off" force it.
    clearport_adjudications_mirror: str = "auto"

    # ── EasyPost (test mode only) ─────────────────────────────────────────
    easypost_api_key: str | None = None
    easypost_mode: str = "test"

    # ── USITC HTS (Harmonized Tariff Schedule) validation ─────────────────
    # "auto" tries the live USITC REST API then falls back to the bundled
    # offline subheading table; "live" forces live; "off" uses the table only.
    clearport_hts_backend: str = "auto"
    clearport_hts_base_url: str = "https://hts.usitc.gov/reststop"
    clearport_hts_timeout: float = 4.0

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
    # Cost-of-wrong ceiling: an AUTO clear is escalated when the expected cost of
    # being wrong — (1 − eval confidence) × declared value — exceeds this. It
    # makes the tier value-aware below the hard line: a low-confidence fix on a
    # mid-value parcel goes to a human even if the weighted score is under
    # threshold.
    clearport_max_auto_error_cost_usd: float = 400.0

    # ── Economics (for the $-saved metric) ────────────────────────────────
    clearport_broker_days: float = 3.0
    clearport_demurrage_per_day_usd: float = 250.0

    # ── Learning / promotion ──────────────────────────────────────────────
    clearport_promotion_min_evidence: int = 3
    clearport_promotion_margin: float = 0.10
    # "off" keeps promotion fully deterministic + offline; "on" additionally
    # registers a native Phoenix experiment (real experiment_id, visible in the
    # Phoenix UI) when a Phoenix server is reachable. The promotion decision is
    # always computed deterministically, so the loop never blocks on Phoenix.
    clearport_phoenix_experiments: str = "off"

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
    def phoenix_live(self) -> bool:
        """True when a real Phoenix is in the loop.

        Mirrors the memory factories' own notion of "live": episodic ② on the
        in-process arize-phoenix-client ("phoenix-client"/"client") or the MCP
        backend ("phoenix"); prompts ④ on "phoenix"; or a set Phoenix API key
        (Arize cloud). Single source of truth for the "auto" toggles below.
        """
        episodic = (self.clearport_episodic_backend or "").lower()
        prompts = (self.clearport_prompts_backend or "").lower()
        return (
            bool(self.phoenix_api_key)
            or episodic in {"phoenix", "phoenix-client", "client"}
            or prompts == "phoenix"
        )

    @staticmethod
    def _resolve_toggle(value: str | None, *, live: bool) -> bool:
        """Resolve an "auto"/"on"/"off" tri-state against whether Phoenix is live."""
        v = (value or "auto").strip().lower()
        if v in {"on", "true", "1", "yes"}:
            return True
        if v in {"off", "false", "0", "no"}:
            return False
        return live  # "auto"

    @property
    def evals_enabled(self) -> bool:
        """Whether the phoenix-evals LLM judge should run (else deterministic gate)."""
        return self._resolve_toggle(self.clearport_evals_enabled, live=self.phoenix_live)

    @property
    def annotations_enabled(self) -> bool:
        """Whether eval verdicts are written back as Phoenix span annotations."""
        return self._resolve_toggle(
            self.clearport_annotations_enabled, live=self.phoenix_live
        )

    @property
    def mcp_enabled(self) -> bool:
        """Whether the on-demand Phoenix MCP read-back (investigate) should run."""
        return self._resolve_toggle(self.clearport_mcp_enabled, live=self.phoenix_live)

    @property
    def oracle_officer_enabled(self) -> bool:
        """Whether the live independent destination-officer LLM oracle should run."""
        return self._resolve_toggle(self.clearport_oracle_officer, live=False)

    @property
    def learned_judge_enabled(self) -> bool:
        """Whether the adaptive (learned) judge influences the eval-gate."""
        return self._resolve_toggle(self.clearport_learned_judge, live=self.phoenix_live)

    @property
    def adjudications_mirror_enabled(self) -> bool:
        """Whether adjudications are mirrored into episodic ② (Phoenix-visible)."""
        return self._resolve_toggle(self.clearport_adjudications_mirror, live=self.phoenix_live)

    @property
    def evals_model(self) -> str:
        """Resolved phoenix-evals judge model id (provider-aware default)."""
        if self.clearport_evals_model:
            return self.clearport_evals_model
        if (self.clearport_evals_provider or "").lower() == "litellm":
            return f"vertex_ai/{self.clearport_judge_model}"
        return self.clearport_judge_model

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
