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
from clearport.schemas import CustomsPayload, Lane
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


class ShipmentSubmission(BaseModel):
    payload: CustomsPayload
    origin: str = "IN"
    dest: str = "US"
    persona: str | None = None
    shipper_name: str | None = None


def _run_summary(run: RecoveryRun) -> dict:
    r = run.result
    items = r.rejection.payload.items
    title = items[0].description if items else (run.seed_id or "Shipment")
    return {
        "run_id": run.id,
        "seed_id": run.seed_id,
        "status": run.status.value,
        "created_at": run.created_at.isoformat(),
        "resolved_at": run.resolved_at.isoformat() if run.resolved_at else None,
        "title": title,
        "persona": r.rejection.persona,
        "lane": str(r.rejection.lane),
        "origin": r.rejection.lane.origin,
        "dest": r.rejection.lane.dest,
        "contents_type": r.rejection.payload.contents_type.value,
        "items": [
            {
                "description": i.description,
                "quantity": i.quantity,
                "value": i.value,
                "hs_tariff_number": i.hs_tariff_number,
                "origin_country": i.origin_country,
            }
            for i in items
        ],
        "error_type": r.rejection.normalized_error_type.value,
        "raw_error": r.rejection.raw_error.message,
        "customs_value": r.rejection.customs_value,
        "rejection_source": r.rejection.source.value,
        "caught_by": r.rejection.source.label,
        "human_note": run.human_note,
        "root_cause": r.diagnosis.root_cause,
        "declaration": r.patch.patched_payload.model_dump(mode="json"),
        "diagnosis": {
            "confidence": r.diagnosis.confidence,
            "confidence_basis": r.diagnosis.confidence_basis,
        },
        "field_diff": [d.model_dump() for d in r.patch.field_diff],
        "rationale": r.patch.rationale,
        "eval": {
            "passed": r.verdict.passed,
            "confidence": r.verdict.confidence,
            "confidence_basis": r.verdict.confidence_basis,
            "rubric": r.verdict.rubric.model_dump(),
            "model": r.verdict.judge_model,
        },
        "risk": {
            "decision": r.risk.decision.value,
            "score": r.risk.total_score,
            "components": {
                "value": r.risk.value_component,
                "danger": r.risk.danger_component,
                "confidence": r.risk.confidence_component,
            },
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


@app.post("/api/shipments")
def submit_shipment(submission: ShipmentSubmission) -> dict:
    """Run an operator-submitted declaration through the recovery loop."""
    run = get_service().submit_custom(
        submission.payload,
        lane=Lane(origin=submission.origin, dest=submission.dest),
        persona=submission.persona,
        shipper_name=submission.shipper_name,
    )
    if run is None:
        return {"status": "ACCEPTED", "note": "Declaration is clean — no recovery needed."}
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


@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str) -> dict:
    """Per-step durations of the recovery loop for the trace-waterfall view.

    These are the same spans exported to Phoenix, captured locally so the
    dashboard can render the waterfall without round-tripping to Phoenix.
    """
    run = get_service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    steps = run.result.trace_steps
    total = round(sum(s.duration_ms for s in steps), 3)
    return {
        "run_id": run.id,
        "rejection_id": run.result.rejection.id,
        "recovery_seconds": run.result.recovery_seconds,
        "total_ms": total,
        "steps": [s.model_dump() for s in steps],
    }


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


@app.get("/api/memory/law")
def memory_law() -> list[dict]:
    """Browse memory tier ① — the grounded customs-law citation corpus."""
    from clearport.memory.law_store import LawStore

    store = LawStore()
    store.bootstrap()
    return [
        {
            "id": r.id,
            "source": r.metadata.get("source", "LAW"),
            "ref": r.metadata.get("ref", "?"),
            "hs_chapter": r.metadata.get("hs_chapter"),
            "text": r.text,
        }
        for r in store.store.all_records()
    ]


@app.get("/api/memory/lessons")
def memory_lessons() -> list[dict]:
    """Browse memory tier ③ — lessons promoted only via a winning experiment."""
    from clearport.memory.lessons import LessonsStore

    return [lesson.model_dump(mode="json") for lesson in LessonsStore().all()]


@app.get("/api/memory/episodic")
def memory_episodic() -> list[dict]:
    """Browse memory tier ② — the episodic outcome record (self-healing log)."""
    return get_service().loop.episodic.get_examples()


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


@app.post("/api/demo/seed-history")
def demo_seed_history() -> dict:
    """Seed a deep, real learning history by driving the genuine loop ~24 runs.

    Never inserts rows directly — it submits/corrects/learns through the live
    ``ClearPortService`` so the Intelligence page shows authentic progression.
    """
    from clearport.api.seed_history import seed_rich_history

    return seed_rich_history(get_service())


@app.get("/api/intelligence")
def intelligence() -> dict:
    """Aggregated LTM tiers + Arize touchpoints and the over-time progression."""
    from clearport.api.intelligence import compute_intelligence

    return compute_intelligence(get_service()).model_dump(mode="json")


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
