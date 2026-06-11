"""Phoenix MCP client — ClearPort's Model Context Protocol surface to Arize.

ClearPort exercises the official ``@arizeai/phoenix-mcp`` server (launched on
demand via ``npx`` over stdio) in three concrete places:

* **Startup handshake** (:func:`verify_tooling`) — confirms the server starts and
  advertises the tools we depend on.
* **On-demand investigate** (:func:`investigate_span_sync`, behind
  ``/api/investigate``) — reads a run's verify-span annotations back out of
  Phoenix through MCP, so the eval verdict can be re-grounded from the source of
  truth on a judge's click.
* **ADK agent toolset** (``clearport.arize.toolset``) — the Agent Builder agent
  carries these tools so Gemini can read/write Arize in its own reasoning.

The hot recovery path deliberately uses the in-process ``arize-phoenix-client``
(HTTP) for annotations/datasets/experiments — reliable and npx-free — while MCP
covers ops handshake, prompt management ④, and the agent/investigate surfaces.
This module wraps the MCP session behind high-level helpers; ``mcp`` is imported
lazily so the package stays importable offline.
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


def _parse_annotations(result: Any) -> list[dict]:
    """Extract the ``annotations`` array from a get-span-annotations result.

    The MCP server returns its JSON payload in a text content block (and, on
    newer clients, also as ``structuredContent``). Handle both.
    """
    import json

    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and isinstance(structured.get("annotations"), list):
        return structured["annotations"]
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("annotations"), list):
            return data["annotations"]
    return []


async def get_span_annotations(span_id: str) -> list[dict]:
    """Read a span's annotations back through the Phoenix MCP ``get-span-annotations`` tool."""
    result = await call_tool(
        "get-span-annotations",
        {"project_identifier": settings.phoenix_project, "span_ids": [span_id]},
    )
    return _parse_annotations(result)


def investigate_span_sync(span_id: str) -> dict | None:
    """Best-effort, synchronous Phoenix MCP read-back of a span's annotations.

    Returns ``{"tool": "get-span-annotations", "annotations": [...]}`` or ``None``
    when MCP is disabled/unavailable (offline, no ``npx``/Node, or a server
    error). Never raises — the caller falls back to a deterministic explanation.
    Safe to call from a FastAPI sync endpoint (runs in a worker thread with no
    active event loop).
    """
    if not span_id or not settings.mcp_enabled:
        return None
    try:
        import asyncio

        annotations = asyncio.run(get_span_annotations(span_id))
        logger.info("mcp.investigate", span_id=span_id, annotations=len(annotations))
        return {"tool": "get-span-annotations", "annotations": annotations}
    except Exception as exc:  # noqa: BLE001 — MCP read-back is best-effort
        logger.warning("mcp.investigate_failed", span_id=span_id, error=str(exc))
        return None
