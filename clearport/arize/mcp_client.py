"""Phoenix MCP client — the *active* half of ClearPort's Arize integration.

This is what satisfies the hackathon's partner requirement: at runtime the
agent reaches into Arize Phoenix through the official ``@arizeai/phoenix-mcp``
Model Context Protocol server to read traces/spans/annotations, pull dataset
examples (memory tier ②), inspect experiments (the promotion gate), and manage
prompts (memory tier ④).

The server is a Node package launched on demand via ``npx`` over stdio. This
module wraps the MCP session so the rest of the codebase can call high-level
helpers (and so the agent can expose them as ADK tools in Phase 3).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog

from clearport.config import settings

logger = structlog.get_logger(__name__)

# Tool names exposed by @arizeai/phoenix-mcp that ClearPort relies on. Kept
# explicit so we fail loudly if the server surface changes under us. Every name
# here is verified against the published tool coverage (v4.x) AND is actually
# called somewhere in ClearPort (prompts ④, episodic datasets ②, experiments,
# and span/trace read-back), so the handshake guards the real runtime surface.
REQUIRED_TOOLS: frozenset[str] = frozenset(
    {
        "list-projects",
        "get-trace",
        "get-spans",
        "get-span-annotations",
        "list-datasets",
        "get-dataset",
        "get-dataset-examples",
        "add-dataset-examples",
        "list-experiments-for-dataset",
        "get-experiment-by-id",
        "list-prompts",
        "get-prompt-by-identifier",
        "upsert-prompt",
    }
)


def _server_params():
    """Build stdio params that launch the Phoenix MCP server via npx."""
    from mcp import StdioServerParameters

    args = [
        "-y",
        "@arizeai/phoenix-mcp@latest",
        "--baseUrl",
        settings.phoenix_host,
    ]
    if settings.phoenix_api_key:
        args += ["--apiKey", settings.phoenix_api_key]

    return StdioServerParameters(
        command="npx",
        args=args,
        env={"PHOENIX_PROJECT": settings.phoenix_project},
    )


@asynccontextmanager
async def phoenix_session():
    """Yield an initialized MCP ``ClientSession`` bound to Phoenix.

    Usage:
        async with phoenix_session() as session:
            tools = await session.list_tools()
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = _server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            logger.debug("mcp.session.initialized", host=settings.phoenix_host)
            yield session


async def list_tool_names() -> list[str]:
    """Return the tool names advertised by the Phoenix MCP server."""
    async with phoenix_session() as session:
        result = await session.list_tools()
        return [t.name for t in result.tools]


async def verify_tooling() -> dict[str, Any]:
    """Handshake check used by the Phase 0 acceptance test.

    Confirms the server starts, advertises the tools we depend on, and answers
    a trivial read call. Returns a small report dict.
    """
    names = set(await list_tool_names())
    missing = sorted(REQUIRED_TOOLS - names)

    projects: Any = None
    async with phoenix_session() as session:
        if "list-projects" in names:
            projects = await session.call_tool("list-projects", arguments={})

    report = {
        "ok": not missing,
        "advertised_tool_count": len(names),
        "missing_required_tools": missing,
        "list_projects_ok": projects is not None,
    }
    logger.info("mcp.handshake", **{k: report[k] for k in ("ok", "advertised_tool_count")})
    return report


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call a single Phoenix MCP tool and return its result."""
    async with phoenix_session() as session:
        return await session.call_tool(name, arguments=arguments or {})
