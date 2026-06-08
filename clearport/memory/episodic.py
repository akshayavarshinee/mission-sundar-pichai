"""Memory tier ② — episodic outcomes.

Episodes are stored as dataset examples (``input`` / ``output`` / ``metadata``),
the same shape Phoenix datasets use, so the in-memory and Phoenix backends are
interchangeable:

* :class:`InMemoryEpisodicMemory` — offline default; powers tests and key-less demos.
* :class:`PhoenixEpisodicMemory` — reads/writes a Phoenix dataset over the MCP
  server (``add-dataset-examples`` / ``get-dataset-examples``).

This tier feeds two things downstream: *precedent* in recall, and the
*accepted-baseline* the eval-gate (Phase 5) judges patches against.
"""

from __future__ import annotations

import asyncio

import structlog

from clearport.config import settings
from clearport.schemas import PrecedentExample, new_id

logger = structlog.get_logger(__name__)


class EpisodicMemory:
    """Interface for the episodic tier."""

    def add_example(self, input: dict, output: dict, metadata: dict | None = None) -> str:  # noqa: A002
        raise NotImplementedError

    def get_examples(self, where: dict | None = None, k: int | None = None) -> list[dict]:
        raise NotImplementedError

    # ── convenience views ────────────────────────────────────────────────
    def precedents(self, memory_key: str, k: int = 3) -> list[PrecedentExample]:
        rows = self.get_examples(where={"memory_key": memory_key}, k=k)
        out: list[PrecedentExample] = []
        for r in rows:
            out.append(
                PrecedentExample(
                    example_id=r.get("id", "?"),
                    summary=str(r.get("input", {}).get("summary", "")),
                    accepted=bool(r.get("output", {}).get("accepted", False)),
                )
            )
        return out

    def baseline_examples(self, error_type: str | None = None, k: int = 20) -> list[dict]:
        where = {"accepted": "true"}
        if error_type:
            where["error_type"] = error_type
        return self.get_examples(where=where, k=k)


class InMemoryEpisodicMemory(EpisodicMemory):
    def __init__(self) -> None:
        self._rows: list[dict] = []

    def add_example(self, input: dict, output: dict, metadata: dict | None = None) -> str:  # noqa: A002
        ex_id = new_id("ex")
        self._rows.append({"id": ex_id, "input": input, "output": output, "metadata": metadata or {}})
        return ex_id

    def get_examples(self, where: dict | None = None, k: int | None = None) -> list[dict]:
        def ok(row: dict) -> bool:
            if not where:
                return True
            flat = {**row.get("metadata", {}), **row.get("input", {})}
            # normalize booleans to lowercase strings for uniform matching
            if "accepted" in row.get("output", {}):
                flat["accepted"] = str(row["output"]["accepted"]).lower()
            return all(str(flat.get(key)) == str(val) for key, val in where.items())

        rows = [r for r in self._rows if ok(r)]
        return rows[-k:] if k else rows


class PhoenixEpisodicMemory(EpisodicMemory):
    """Phoenix dataset backend over MCP (best-effort sync wrappers)."""

    def __init__(self, dataset: str | None = None) -> None:
        self.dataset = dataset or settings.phoenix_dataset

    @staticmethod
    def _run(coro):  # noqa: ANN001, ANN205
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # already inside a loop: run in a private loop on a worker thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()

    def add_example(self, input: dict, output: dict, metadata: dict | None = None) -> str:  # noqa: A002
        from clearport.arize.mcp_client import call_tool

        ex_id = new_id("ex")
        example = {"input": input, "output": output, "metadata": {**(metadata or {}), "id": ex_id}}
        try:
            self._run(
                call_tool(
                    "add-dataset-examples",
                    {"dataset": self.dataset, "examples": [example]},
                )
            )
        except Exception as exc:  # noqa: BLE001 — never break the loop on telemetry write
            logger.warning("episodic.phoenix.add_failed", error=str(exc))
        return ex_id

    def get_examples(self, where: dict | None = None, k: int | None = None) -> list[dict]:
        from clearport.arize.mcp_client import call_tool

        try:
            result = self._run(call_tool("get-dataset-examples", {"dataset": self.dataset}))
        except Exception as exc:  # noqa: BLE001
            logger.warning("episodic.phoenix.get_failed", error=str(exc))
            return []
        rows = _coerce_examples(result)

        def ok(row: dict) -> bool:
            if not where:
                return True
            flat = {**row.get("metadata", {}), **row.get("input", {})}
            if "accepted" in row.get("output", {}):
                flat["accepted"] = str(row["output"]["accepted"]).lower()
            return all(str(flat.get(key)) == str(val) for key, val in where.items())

        rows = [r for r in rows if ok(r)]
        return rows[-k:] if k else rows


def _coerce_examples(mcp_result) -> list[dict]:  # noqa: ANN001
    """Normalize an MCP tool result into a list of {input, output, metadata}."""
    data = getattr(mcp_result, "structuredContent", None) or mcp_result
    if isinstance(data, dict):
        data = data.get("examples", data.get("data", []))
    if not isinstance(data, list):
        return []
    return [d for d in data if isinstance(d, dict)]


_DEFAULT: EpisodicMemory | None = None


def get_episodic() -> EpisodicMemory:
    global _DEFAULT
    if _DEFAULT is None:
        backend = (settings.clearport_episodic_backend or "memory").lower()
        _DEFAULT = PhoenixEpisodicMemory() if backend == "phoenix" else InMemoryEpisodicMemory()
    return _DEFAULT


def reset_episodic() -> None:
    """Test helper."""
    global _DEFAULT
    _DEFAULT = None
