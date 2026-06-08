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
