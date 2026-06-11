"""Server-side scripted demo runner — drives the locked storyboard hands-free.

The dashboard's "Play full demo" button calls :func:`play_scripted_demo`, which
runs every beat against the live service so the SSE timeline animates and the
metrics update on screen — including the two beats that cannot be produced by the
plain seed buttons:

* the **eval-gate VETO** money shot (a genuinely novel item — a hand-carved
  sitar bridge — that the keyword table cannot classify and whose declared HS is
  invalid, so the eval-gate veto is *earned*, not staged), and
* the **self-heal from memory** payoff (the same case recurs *after* a lesson
  has been promoted, so it heals from memory ③ rather than the classifier).

Nothing is sabotaged: the veto falls out of a real, unrehearsed case (seed S5),
and the seed buttons can trigger the same beats individually.
"""

from __future__ import annotations

import structlog

from clearport.api.store import RecoveryRun
from clearport.config import settings
from clearport.seeds.shipments import get_seed

logger = structlog.get_logger(__name__)


def _recover(svc, seed_id: str) -> RecoveryRun:
    run = svc.submit_seed(seed_id)
    if run is None:  # a clean control seed — should not happen for these beats
        raise RuntimeError(f"seed {seed_id} cleared with no rejection")
    return run


def _beat(svc, index: int, title: str) -> None:
    svc.bus.publish("demo_beat", {"index": index, "title": title})


def _summary(beat: int, title: str, run: RecoveryRun) -> dict:
    r = run.result
    return {
        "beat": beat,
        "title": title,
        "run_id": run.id,
        "seed_id": run.seed_id,
        "status": run.status.value,
        "error_type": r.rejection.normalized_error_type.value,
        "eval_passed": r.verdict.passed,
        "eval_confidence": r.verdict.confidence,
        "decision": r.risk.decision.value,
        "fields": [d.field for d in r.patch.field_diff],
        "recovery_seconds": r.recovery_seconds,
    }


def play_scripted_demo(svc) -> dict:
    """Run the full storyboard in place; returns a per-beat summary + metrics."""
    beats: list[dict] = []
    svc.clear()  # start from a clean board (keeps the SSE bus alive)

    original_min_evidence = settings.clearport_promotion_min_evidence
    settings.clearport_promotion_min_evidence = 1  # deterministic promotion for the demo

    try:
        # Beat 1 — structural fix, fast auto-heal.
        t1 = "S4 missing customs_signer → fast AUTO heal"
        _beat(svc, 1, t1)
        beats.append(_summary(1, t1, _recover(svc, "S4")))

        # Beat 2 — the money shot: a genuinely novel item (S5) the classifier
        # cannot resolve → the naive fix stays invalid → Arize eval-gate VETO.
        t2 = "Novel sitar-bridge item, invalid HS → Arize eval-gate VETO → escalate"
        _beat(svc, 2, t2)
        money_shot = _recover(svc, "S5")
        beats.append(_summary(2, t2, money_shot))

        # Beat 3 — human corrects, experiment promotes the lesson (② → ③).
        t3 = "Human corrects HS 920992 → experiment beats baseline → PROMOTE ③"
        _beat(svc, 3, t3)
        corrected = get_seed("S5").payload.model_copy(deep=True)
        corrected.items[0].hs_tariff_number = "920992"
        svc.correct(money_shot.id, corrected, note="classified by licensed broker")
        promotions = [p.model_dump() for p in svc.run_learning()]
        beats.append(
            {"beat": 3, "title": t3, "promotions": promotions, "promoted": any(p["promoted"] for p in promotions)}
        )

        # Beat 4 — the same novel case recurs → self-heals from memory ③.
        t4 = "Same sitar-bridge case returns → self-heals from memory ③ (not the classifier)"
        _beat(svc, 4, t4)
        healed = _recover(svc, "S5")
        summary4 = _summary(4, t4, healed)
        summary4["healed_from_memory"] = "memory-lesson" in healed.result.patch.tool_calls_used
        beats.append(summary4)

        # Beat 5 — $ hard-line escalation (left awaiting approval for live HITL).
        t5 = "S2 EEI value > $2,500 → hard-line ESCALATE (awaiting your approval)"
        _beat(svc, 5, t5)
        beats.append(_summary(5, t5, _recover(svc, "S2")))

        # Beat 6 — restricted-goods escalation (left awaiting approval).
        t6 = "S3 restricted goods → danger ESCALATE (awaiting your approval)"
        _beat(svc, 6, t6)
        beats.append(_summary(6, t6, _recover(svc, "S3")))

        # Beat 7 — silent destination rule change → drift alert → auto-heal.
        t7 = "Destination silently changes a rule → DRIFT ALERT → auto-heal"
        _beat(svc, 7, t7)
        drift = svc.trigger_drift("C0")
        beats.append(
            {
                "beat": 7,
                "title": t7,
                "drift": drift.get("drift"),
                "healed_status": drift.get("healed_status"),
                "fields": [f["field"] for f in drift.get("field_diff", [])],
            }
        )

        # Wildcard — unrehearsed generality.
        t8 = "Wildcard W1 contents_explanation missing → AUTO heal"
        _beat(svc, 8, t8)
        beats.append(_summary(8, t8, _recover(svc, "W1")))
    finally:
        settings.clearport_promotion_min_evidence = original_min_evidence

    svc.bus.publish("demo_complete", {"beats": len(beats)})
    logger.info("demo.played", beats=len(beats))
    return {"beats": beats, "metrics": svc.metrics().model_dump()}
