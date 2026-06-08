"""Phase 0 acceptance: confirm the Phoenix MCP server starts and exposes the
tools ClearPort depends on.

Run (after filling `.env`; requires Node/npx on PATH):

    uv run clearport-mcp-handshake
    # or
    python -m clearport.scripts.mcp_handshake

Success = prints a report with ok=True and no missing required tools.
"""

from __future__ import annotations

import asyncio
import json
import sys

from clearport.arize.mcp_client import verify_tooling


def main() -> int:
    try:
        report = asyncio.run(verify_tooling())
    except FileNotFoundError:
        print(
            "✗ Could not launch the Phoenix MCP server.\n"
            "  Ensure Node.js + npx are installed and on PATH "
            "(the server is `npx -y @arizeai/phoenix-mcp`).",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001 — surface any handshake failure clearly
        print(f"✗ MCP handshake failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2))
    if report["ok"]:
        print("\n✓ Phoenix MCP handshake OK — all required tools advertised.")
        return 0
    print(
        "\n✗ Handshake reachable but missing required tools: "
        f"{report['missing_required_tools']}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
