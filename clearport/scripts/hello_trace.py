"""Phase 0 acceptance: emit one Gemini call as a Phoenix trace ("hello-trace").

Run (after `docker compose up -d` and filling `.env`):

    uv run clearport-hello-trace
    # or
    python -m clearport.scripts.hello_trace

Success = the script prints the model reply AND a new trace appears in the
Phoenix UI (http://localhost:6006) under project "clearport".
"""

from __future__ import annotations

import sys

from clearport.arize.tracing import get_tracer, init_tracing
from clearport.config import settings


def _make_client():
    """Construct a google-genai client for either Gemini Developer API or Vertex."""
    from google import genai

    if settings.google_genai_use_vertexai:
        settings.require("google_cloud_project")
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    settings.require("google_api_key")
    return genai.Client(api_key=settings.google_api_key)


def main() -> int:
    init_tracing()
    tracer = get_tracer("clearport.hello")
    client = _make_client()

    prompt = (
        "In one sentence, state what a customs HS tariff code is. "
        "This is a ClearPort tracing smoke-test."
    )

    # The OpenInference Gemini instrumentor turns generate_content into a span
    # automatically; we wrap it in an explicit parent span so the trace has a
    # clear ClearPort root.
    with tracer.start_as_current_span("hello-trace") as span:
        span.set_attribute("clearport.phase", "0")
        span.set_attribute("clearport.check", "hello-trace")
        response = client.models.generate_content(
            model=settings.clearport_gemini_model,
            contents=prompt,
        )
        text = (response.text or "").strip()
        span.set_attribute("clearport.reply_chars", len(text))

    print("\n── Gemini reply ─────────────────────────────────────────────")
    print(text or "(empty response)")
    print("─────────────────────────────────────────────────────────────")
    print(
        f"✓ Trace emitted to Phoenix project '{settings.phoenix_project}' "
        f"at {settings.collector_endpoint}\n"
        "  Open the Phoenix UI to confirm the 'hello-trace' span."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
