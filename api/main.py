"""FastAPI app — REST + SSE surface for the dashboard and demo controls.

Run locally:  ``uv run clearport-api``  (defaults to http://localhost:8080)
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from clearport.api.store import RecoveryRun
from clearport.config import settings
from clearport.schemas import CustomsPayload
from clearport.service import ApprovalError, get_service
from clearport.seeds.shipments import all_seeds

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize Arize Phoenix tracing once at startup (best-effort).

    Tracing is otherwise initialized lazily on first use and silently degrades
    to a no-op when Phoenix is unreachable. Doing it here surfaces a clear log
    line (``tracing.initialized`` or ``tracing.unavailable_null``) so it's
    obvious whether spans are being exported to Phoenix.
    """
    try:
        from clearport.arize.tracing import init_tracing

        init_tracing()
    except Exception as exc:  # noqa: BLE001 — tracing must never block the API
        logger.warning("tracing.startup_skipped", error=str(exc))
    yield


app = FastAPI(title="ClearPort", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApprovalAction(BaseModel):
    note: str | None = None


class CorrectionAction(BaseModel):
    corrected: CustomsPayload
    note: str | None = None


def _run_summary(run: RecoveryRun) -> dict:
    r = run.result
    return {
        "run_id": run.id,
        "seed_id": run.seed_id,
        "status": run.status.value,
        "error_type": r.rejection.normalized_error_type.value,
        "customs_value": r.rejection.customs_value,
        "root_cause": r.diagnosis.root_cause,
        "field_diff": [d.model_dump() for d in r.patch.field_diff],
        "rationale": r.patch.rationale,
        "eval": {
            "passed": r.verdict.passed,
            "confidence": r.verdict.confidence,
            "rubric": r.verdict.rubric.model_dump(),
            "model": r.verdict.judge_model,
        },
        "risk": {
            "decision": r.risk.decision.value,
            "score": r.risk.total_score,
            "hard_line": r.risk.hard_line_triggered,
            "reasons": r.risk.reasons,
        },
        "law_citations": [c.model_dump() for c in r.diagnosis.law_citations],
        "vetoed_lesson_ids": r.vetoed_lesson_ids,
        "recovery_seconds": r.recovery_seconds,
        "label_id": run.label_id,
        "demurrage_saved_usd": r.outcome.demurrage_saved_usd,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.clearport_env.value}


@app.get("/api/seeds")
def seeds() -> list[dict]:
    return [
        {
            "id": s.id,
            "persona": s.persona,
            "note": s.note,
            "value": s.payload.total_value,
            "expected_error": s.expected_error.value if s.expected_error else None,
        }
        for s in all_seeds()
    ]


@app.post("/api/recover/{seed_id}")
def recover(seed_id: str) -> dict:
    try:
        run = get_service().submit_seed(seed_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run is None:
        return {"seed_id": seed_id, "status": "ACCEPTED", "note": "clean shipment"}
    return _run_summary(run)


@app.get("/api/runs")
def runs() -> list[dict]:
    return [_run_summary(r) for r in get_service().list_runs()]


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    run = get_service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_summary(run)


@app.get("/api/approvals")
def approvals() -> list[dict]:
    return [_run_summary(r) for r in get_service().list_approvals()]


@app.post("/api/approvals/{run_id}/approve")
def approve(run_id: str, action: ApprovalAction) -> dict:
    try:
        return _run_summary(get_service().approve(run_id, action.note))
    except ApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/approvals/{run_id}/reject")
def reject(run_id: str, action: ApprovalAction) -> dict:
    try:
        return _run_summary(get_service().reject(run_id, action.note))
    except ApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/approvals/{run_id}/correct")
def correct(run_id: str, action: CorrectionAction) -> dict:
    try:
        return _run_summary(get_service().correct(run_id, action.corrected, action.note))
    except ApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/metrics")
def metrics() -> dict:
    return get_service().metrics().model_dump()


@app.post("/api/learn")
def learn() -> list[dict]:
    """Run experiment-gated promotion (② -> ③) and report the outcome."""
    return [r.model_dump() for r in get_service().run_learning()]


@app.post("/api/drift/{seed_id}")
def drift(seed_id: str) -> dict:
    """Simulate a silent destination rule change, alert, and auto-heal."""
    try:
        return get_service().trigger_drift(seed_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/reset")
def reset() -> dict:
    """Clear all runs/approvals/memory for a clean demo (keeps SSE alive)."""
    get_service().clear()
    return {"status": "reset"}


@app.post("/api/demo/play")
def demo_play() -> dict:
    """Run the full scripted storyboard hands-free; streams events as it goes."""
    from clearport.api.demo_runner import play_scripted_demo

    return play_scripted_demo(get_service())


@app.get("/api/events")
async def events() -> EventSourceResponse:
    bus = get_service().bus

    async def generator():
        for event in bus.history():
            yield {"event": event["type"], "data": json.dumps(event)}
        queue = await bus.subscribe()
        try:
            while True:
                event = await queue.get()
                yield {"event": event["type"], "data": json.dumps(event)}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(generator())


def run() -> None:
    """Entry point for the ``clearport-api`` console script."""
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("clearport.api.main:app", host="0.0.0.0", port=port, reload=False)  # noqa: S104


if __name__ == "__main__":  # python -m clearport.api.main
    run()
