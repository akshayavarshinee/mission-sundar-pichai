"""Gemini structured-generation wrapper with an explicit offline switch.

The agents call :func:`generate_json` for grounded reasoning. When no Gemini
credentials are configured (``is_live()`` is False) the call raises
:class:`LLMUnavailable`, and each agent falls back to its deterministic,
rule-based path — so the entire recovery loop runs with no keys (for local
checking and a laptop demo) and uses Gemini for richer reasoning when available.
"""

from __future__ import annotations

import json

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when a live Gemini call is requested but no credentials exist."""


def is_live() -> bool:
    if settings.google_genai_use_vertexai:
        return bool(settings.google_cloud_project)
    return bool(settings.google_api_key)


def _client():  # noqa: ANN202 — google-genai Client, imported lazily
    from google import genai

    if settings.google_genai_use_vertexai:
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    return genai.Client(api_key=settings.google_api_key)


def generate_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> dict:
    """Return a parsed JSON object from a single Gemini call.

    Raises :class:`LLMUnavailable` when not live so callers can fall back.
    """
    if not is_live():
        raise LLMUnavailable("No Gemini credentials configured.")

    from google.genai import types

    client = _client()
    response = client.models.generate_content(
        model=model or settings.clearport_gemini_model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    text = (response.text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("llm.json_parse_failed", head=text[:160])
        return _salvage_json(text)


def generate_text(system: str, user: str, *, model: str | None = None, temperature: float = 0.2) -> str:
    if not is_live():
        raise LLMUnavailable("No Gemini credentials configured.")

    from google.genai import types

    client = _client()
    response = client.models.generate_content(
        model=model or settings.clearport_gemini_model,
        contents=user,
        config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
    )
    return (response.text or "").strip()


def _salvage_json(text: str) -> dict:
    """Best-effort: pull the first {...} block out of a noisy response."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}
