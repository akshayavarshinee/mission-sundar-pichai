"""Bind the Arize Phoenix MCP server into Google ADK as an agent toolset.

This is the hackathon's partner integration at the *agent* layer: the
Orchestrator (an ADK ``LlmAgent`` running Gemini) gets the Phoenix MCP tools
(traces, datasets, experiments, prompts, annotations) as callable tools, so the
agent reads and writes Arize inside its own reasoning loop.

ADK and MCP are imported lazily; this module imports cleanly with neither
installed (e.g. during offline static checks).
"""

from __future__ import annotations

import structlog

from clearport.arize.mcp_client import _server_params  # reuse the npx launch config

logger = structlog.get_logger(__name__)


def build_phoenix_toolset():  # noqa: ANN201 — ADK MCPToolset, imported lazily
    """Construct an ADK ``MCPToolset`` that launches ``@arizeai/phoenix-mcp``."""
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset

    server_params = _server_params()

    # ADK has shifted the connection-params wrapper across versions; support both.
    try:
        from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams

        connection_params = StdioConnectionParams(server_params=server_params)
    except Exception:  # noqa: BLE001 — older ADK takes StdioServerParameters directly
        connection_params = server_params

    logger.info("toolset.phoenix.created")
    return MCPToolset(connection_params=connection_params)


def phoenix_tool_filter() -> list[str]:
    """The Phoenix MCP tools we expect the agent to actually use."""
    from clearport.arize.mcp_client import REQUIRED_TOOLS

    return sorted(REQUIRED_TOOLS)
