"""Write eval verdicts back onto Phoenix spans as annotations.

This is the visible proof of the eval conscience: after the loop's ``verify``
span is emitted, the verdict (pass/fail + confidence + rationale) is attached to
that exact span as a Phoenix annotation, so a judge can open the trace in the
Phoenix UI and see *why* a fix was cleared or vetoed — not just a pass/fail bit
buried in span attributes.

Writes go through the in-process ``arize-phoenix-client`` (HTTP), gated behind a
live Phoenix and ``CLEARPORT_ANNOTATIONS_ENABLED``. Everything here is
best-effort: a missing client, an unreachable server, or an as-yet-uningested
span degrades to a no-op and never breaks a recovery run.
"""

from __future__ import annotations

import structlog

from clearport.config import settings
from clearport.schemas import EvalVerdict

logger = structlog.get_logger(__name__)


def annotations_available() -> bool:
    """True when eval verdicts should be written back as Phoenix annotations."""
    if not settings.annotations_enabled:
        return False
    try:
        import phoenix.client  # noqa: F401
    except Exception:  # noqa: BLE001 — package missing / import failure
        return False
    return True


def _annotation_id_of(result) -> str | None:  # noqa: ANN001
    if isinstance(result, dict):
        return result.get("id") or result.get("annotation_id")
    return getattr(result, "id", None) or getattr(result, "annotation_id", None)


def annotate_eval(
    span_id: str | None,
    verdict: EvalVerdict,
    client=None,  # noqa: ANN001 — phoenix.client.Client, injected in tests
) -> str | None:
    """Attach the eval verdict to its Phoenix ``verify`` span. Returns the
    annotation id (or ``None``). Best-effort — never raises."""
    if not span_id or not annotations_available():
        return None
    try:
        if client is None:
            # Make sure the span has been exported before we annotate it.
            from clearport.arize.tracing import flush_tracing

            flush_tracing()
            from phoenix.client import Client

            client = Client(base_url=settings.phoenix_host, api_key=settings.phoenix_api_key)

        result = client.spans.add_span_annotation(
            span_id=span_id,
            annotation_name="eval_gate",
            annotator_kind="LLM",
            label="pass" if verdict.passed else "fail",
            score=verdict.confidence,
            explanation=verdict.rationale or verdict.confidence_basis,
        )
        ann_id = _annotation_id_of(result)
        logger.info(
            "annotation.eval_written",
            span_id=span_id,
            passed=verdict.passed,
            annotation_id=ann_id,
        )
        return ann_id
    except Exception as exc:  # noqa: BLE001 — annotation is best-effort telemetry
        logger.warning("annotation.eval_failed", span_id=span_id, error=str(exc))
        return None
