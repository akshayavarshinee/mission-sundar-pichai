"""Phase 0 unit test: the MCP tools ClearPort depends on are a subset of the
tools the Phoenix MCP server actually advertises.

This is a *contract* test. The reference list mirrors the published
``@arizeai/phoenix-mcp`` tool coverage; if Phoenix changes its surface, this
test tells us before a live handshake fails in the demo.
"""

from __future__ import annotations

from clearport.arize.mcp_client import REQUIRED_TOOLS

# Published tool surface of @arizeai/phoenix-mcp (Prompts, Projects, Traces,
# Spans, Sessions, Annotation Configs, Datasets, Experiments).
PHOENIX_MCP_PUBLISHED_TOOLS = frozenset(
    {
        # Prompts
        "list-prompts",
        "get-prompt",
        "get-latest-prompt",
        "get-prompt-by-identifier",
        "get-prompt-version",
        "list-prompt-versions",
        "get-prompt-version-by-tag",
        "list-prompt-version-tags",
        "add-prompt-version-tag",
        "upsert-prompt",
        # Projects
        "list-projects",
        "get-project",
        # Traces
        "list-traces",
        "get-trace",
        # Spans
        "get-spans",
        "get-span-annotations",
        # Sessions
        "list-sessions",
        "get-session",
        # Annotation Configs
        "list-annotation-configs",
        # Datasets
        "list-datasets",
        "get-dataset",
        "get-dataset-examples",
        "get-dataset-experiments",
        "add-dataset-examples",
        # Experiments
        "list-experiments-for-dataset",
        "get-experiment-by-id",
    }
)


def test_required_tools_are_published() -> None:
    unknown = REQUIRED_TOOLS - PHOENIX_MCP_PUBLISHED_TOOLS
    assert not unknown, f"ClearPort depends on tools Phoenix MCP does not publish: {unknown}"


def test_required_tools_cover_three_load_bearing_uses() -> None:
    # evidence (traces/spans), memory (datasets), learning (experiments)
    assert {"get-trace", "get-spans"} <= REQUIRED_TOOLS
    assert {"get-dataset-examples", "add-dataset-examples"} <= REQUIRED_TOOLS
    assert {"list-experiments-for-dataset", "get-experiment-by-id"} <= REQUIRED_TOOLS


def test_required_tools_match_prompt_backend_calls() -> None:
    # Guard the exact tool names the prompts ④ backend invokes at runtime, so the
    # handshake validates the surface the code actually depends on (not a stale
    # alias). See clearport.memory.prompts.get_prompt / upsert_prompt.
    assert {"get-prompt-by-identifier", "upsert-prompt"} <= REQUIRED_TOOLS


def test_parse_annotations_extracts_from_text_block() -> None:
    from clearport.arize.mcp_client import _parse_annotations

    class _Block:
        text = (
            '{"annotations": [{"id": "a1", "span_id": "s1", "name": "eval_gate", '
            '"result": {"label": "pass", "score": 0.8}}], "nextCursor": null}'
        )

    class _Result:
        structuredContent = None
        content = [_Block()]

    annotations = _parse_annotations(_Result())
    assert annotations and annotations[0]["name"] == "eval_gate"


def test_investigate_span_sync_noop_when_disabled(monkeypatch) -> None:
    from clearport.arize import mcp_client
    from clearport.config import settings

    monkeypatch.setattr(settings, "clearport_mcp_enabled", "off", raising=False)
    assert mcp_client.investigate_span_sync("deadbeefdeadbeef") is None


def test_investigate_span_sync_reads_back_via_mcp(monkeypatch) -> None:
    # Force MCP on and stub the async tool call so no npx/Node server is needed:
    # the sync wrapper must run it and surface the parsed annotations.
    from clearport.arize import mcp_client
    from clearport.config import settings

    monkeypatch.setattr(settings, "clearport_mcp_enabled", "on", raising=False)

    async def _fake_get(span_id: str):
        return [{"id": "a1", "span_id": span_id, "name": "eval_gate",
                 "result": {"label": "pass", "score": 0.82}}]

    monkeypatch.setattr(mcp_client, "get_span_annotations", _fake_get)
    out = mcp_client.investigate_span_sync("deadbeefdeadbeef")
    assert out is not None
    assert out["tool"] == "get-span-annotations"
    assert out["annotations"][0]["name"] == "eval_gate"
