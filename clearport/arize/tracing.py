"""OTel → Phoenix tracing bootstrap.

This is the *passive* half of ClearPort's Arize integration: every step the
agent takes is emitted as an OpenTelemetry span to Phoenix, where it becomes
the evidence the Self-Healer later reads back (via MCP) and the substrate for
evals, experiments, and drift detection.

Call :func:`init_tracing` exactly once at process start (API server, scripts,
or tests that need traces). It is idempotent.
"""

from __future__ import annotations

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)

_TRACER_PROVIDER = None  # module-level guard for idempotency
_TRACING_FAILED = False  # avoid retrying a failed bootstrap on every call


class _NullSpan:
    """No-op span used when OpenTelemetry/Phoenix are unavailable (offline)."""

    def set_attribute(self, *_args, **_kwargs) -> None:  # noqa: D401
        return None

    def __enter__(self) -> _NullSpan:
        return self

    def __exit__(self, *_exc) -> bool:
        return False


class _NullTracer:
    def start_as_current_span(self, *_args, **_kwargs) -> _NullSpan:
        return _NullSpan()


def init_tracing(project_name: str | None = None):
    """Register a Phoenix-aware tracer provider and instrument Gemini + ADK.

    Returns the tracer provider so callers can create manual spans if desired.
    Safe to call multiple times; subsequent calls return the same provider.
    """
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is not None:
        return _TRACER_PROVIDER

    # Imported lazily so that importing this module never hard-requires the
    # optional tracing stack (keeps unit tests light).
    from phoenix.otel import register
    project = project_name or settings.phoenix_project

    headers = {}
    if settings.phoenix_api_key:
        # Phoenix Cloud auth header.
        headers["api_key"] = settings.phoenix_api_key

    _TRACER_PROVIDER = register(
        project_name=project,
        endpoint=f"{settings.collector_endpoint.rstrip('/')}/v1/traces",
        headers=headers or None,
        # auto-instrument what we can; we add explicit instrumentors below too.
        auto_instrument=True,
        batch=not settings.is_cloud,  # simpler synchronous export locally
        set_global_tracer_provider=True,
    )

    _instrument_frameworks()

    logger.info(
        "tracing.initialized",
        project=project,
        endpoint=settings.collector_endpoint,
        cloud=settings.is_cloud,
    )
    return _TRACER_PROVIDER


def _instrument_frameworks() -> None:
    """Best-effort instrumentation of Gemini, ADK, and MCP.

    Each is optional; a missing instrumentor logs a warning rather than failing,
    so the system still runs (with reduced trace coverage) in minimal installs.
    """
    instrumentors = (
        ("openinference.instrumentation.google_adk", "GoogleADKInstrumentor"),
        ("openinference.instrumentation.google_genai", "GoogleGenAIInstrumentor"),
        ("openinference.instrumentation.mcp", "MCPInstrumentor"),
    )
    for module_path, class_name in instrumentors:
        try:
            module = __import__(module_path, fromlist=[class_name])
            getattr(module, class_name)().instrument(tracer_provider=_TRACER_PROVIDER)
            logger.debug("tracing.instrumented", framework=class_name)
        except Exception as exc:  # noqa: BLE001 — instrumentation is best-effort
            logger.warning(
                "tracing.instrument_skipped", framework=class_name, error=str(exc)
            )


def get_tracer(name: str = "clearport"):
    """Return an OTel tracer, or a no-op tracer when tracing is unavailable."""
    global _TRACING_FAILED
    if _TRACING_FAILED:
        return _NullTracer()
    try:
        from opentelemetry import trace

        if _TRACER_PROVIDER is None:
            init_tracing()
        return trace.get_tracer(name)
    except Exception as exc:  # noqa: BLE001 — degrade to no-op tracing offline
        _TRACING_FAILED = True
        logger.warning("tracing.unavailable_null", error=str(exc))
        return _NullTracer()
