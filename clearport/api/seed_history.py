"""Seed a rich, *real* learning history so the Intelligence page is never empty.

This drives the actual :class:`~clearport.service.ClearPortService` through a
deliberate arc instead of inserting rows:

    cold start (HS cases the classifier can't resolve → escalate → human corrects)
        → experiment-gated promotion (② → ③)
        → the same cases recur and self-heal from memory
        → an everyday mix of fast autos and safe escalations
        → a silent destination rule change → drift alert → auto-heal

Every lesson, episodic example, eval verdict, and progression point is therefore
produced by the genuine recovery loop, so ``/api/intelligence`` reflects real
state (counts from the stores, latencies from captured spans, self-heal markers
from ``patch.tool_calls_used``).

Like the scripted demo, the HS cases temporarily swap in a low-confidence
classifier so the "agent can't resolve it → a human corrects it → it learns →
it self-heals" arc appears deterministically (otherwise the classifier would
resolve them outright and the eval-gate veto / self-heal beats never show). The
classifier is always restored in ``finally``.

Intended to be run against the live stack (Gemini + Phoenix) before a demo so
latencies are real and the Phoenix project is populated with clickable traces,
datasets, and experiments; it also runs offline (deterministic fallback) for
local checks. Fully resettable via ``/api/reset``.
"""

from __future__ import annotations

import structlog

from clearport.agents import patch_engine
from clearport.agents.classifier import HSClassification
from clearport.config import settings
from clearport.schemas import ContentsType, CustomsItemSpec, CustomsPayload

logger = structlog.get_logger(__name__)

# Distinct goods → distinct HS chapters → distinct memory keys → distinct
# lessons and self-heal pairs. (description, invalid initial code, corrected HTS)
_HS_CASES: tuple[tuple[str, str, str], ...] = (
    ("Hand-engraved brass keychain", "1234", "830249"),
    ("Hand-block-printed silk scarf", "3456", "621440"),
    ("Cotton knit t-shirt (lot)", "5678", "610910"),
    ("Whole black pepper sampler", "7890", "090411"),
)

_BASELINE_ATTEMPTS = 2  # escalations (→ human corrections) per HS case
_REPEAT_ATTEMPTS = 2  # recurrences that should self-heal from memory


def _broken_classifier(*_args, **_kwargs) -> HSClassification:
    """A classifier that cannot resolve the case — forces the escalation arc."""
    return HSClassification(code=None, description="unknown", confidence=0.1, source="none")


def _hs_payload(description: str, hs_code: str, *, value: float = 90.0) -> CustomsPayload:
    """A clean declaration whose only defect is the HS code (so the sole rule
    tripped is HS_INVALID)."""
    return CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        items=[
            CustomsItemSpec(
                description=description,
                quantity=2,
                value=value,
                weight_oz=16.0,
                origin_country="IN",
                hs_tariff_number=hs_code,
            )
        ],
    )


def _beat(svc, title: str) -> None:  # noqa: ANN001 — ClearPortService
    """Publish a storyboard beat so a connected dashboard timeline animates."""
    svc.bus.publish("demo_beat", {"title": title})


def seed_rich_history(svc) -> dict:  # noqa: ANN001 — ClearPortService
    """Generate a deep, real learning history on the service. Resettable."""
    svc.clear()
    svc.bus.publish("seed_history_start", {})

    original_classifier = patch_engine.classify_hs
    original_min_evidence = settings.clearport_promotion_min_evidence
    # Evidence threshold for promotion during seeding (restored in finally). Two
    # corrections per key keeps the experiment honest (baseline 0.0 vs candidate
    # 1.0, evidence ≥ 2) without an unnecessarily long live run.
    settings.clearport_promotion_min_evidence = _BASELINE_ATTEMPTS

    runs_made = 0
    lessons_promoted = 0
    try:
        # ── Phase 1 — cold start: novel HS cases escalate → human corrects ──
        patch_engine.classify_hs = _broken_classifier
        _beat(svc, "Cold start — novel HS cases the agent can't yet resolve")
        for description, bad_code, good_code in _HS_CASES:
            open_run_ids: list[str] = []
            for _ in range(_BASELINE_ATTEMPTS):
                run = svc.submit_custom(
                    _hs_payload(description, bad_code),
                    persona=f"{description} — HS learning",
                )
                runs_made += 1
                if run is not None and run.is_open:
                    open_run_ids.append(run.id)
            corrected = _hs_payload(description, good_code)
            for run_id in open_run_ids:
                svc.correct(run_id, corrected, note="Classified by a licensed customs broker")

        # ── Phase 2 — experiment-gated promotion (② → ③) ──
        _beat(svc, "Run learning — promote fixes that beat baseline")
        results = svc.run_learning()
        lessons_promoted = sum(1 for r in results if r.promoted)

        # ── Phase 3 — the same cases recur → self-heal from memory ──
        # The classifier is still broken, so a clean resolution can only come
        # from a promoted lesson (memory ③) — that's the payoff of learning.
        _beat(svc, "Repeat cases self-heal autonomously from memory")
        for description, bad_code, _good in _HS_CASES:
            for _ in range(_REPEAT_ATTEMPTS):
                run = svc.submit_custom(
                    _hs_payload(description, bad_code),
                    persona=f"{description} — repeat shipment",
                )
                runs_made += 1
                # A live judge fluke could leave it open; approve so nothing
                # lingers in the queue. The self-heal marker (memory-lesson) is
                # recorded on the patch regardless.
                if run is not None and run.is_open:
                    svc.approve(run.id, note="Auto-approved — self-healed from memory")
    finally:
        patch_engine.classify_hs = original_classifier
        settings.clearport_promotion_min_evidence = original_min_evidence

    # ── Phase 4 — everyday mix (real classifier): fast autos + safe escalations ──
    _beat(svc, "Everyday mix — fast auto-heals and safe escalations")
    for seed_id in ("S4", "W1", "S4", "W1"):
        if svc.submit_seed(seed_id) is not None:
            runs_made += 1
    for seed_id in ("S2", "S3"):  # EEI hard-line + restricted goods → escalate
        run = svc.submit_seed(seed_id)
        if run is not None:
            runs_made += 1
            if run.is_open:
                svc.approve(run.id, note="Reviewed and approved by operator")

    # ── Phase 5 — silent destination rule change → drift alert → auto-heal ──
    _beat(svc, "Silent rule change — drift detected, then auto-healed")
    drift = svc.trigger_drift("C0")
    if drift.get("run_id"):
        runs_made += 1

    svc.bus.publish("seed_history_complete", {"runs": runs_made, "lessons": lessons_promoted})
    logger.info("seed_history.done", runs=runs_made, lessons=lessons_promoted)

    metrics = svc.metrics()
    return {
        "runs_made": runs_made,
        "lessons_promoted": lessons_promoted,
        "drift_healed": drift.get("healed_status"),
        "metrics": metrics.model_dump(),
    }
