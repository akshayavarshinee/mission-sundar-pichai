"""ClearPort scripted demo — drives the locked storyboard through the real service.

Runs fully offline (no keys, no network): every external dependency has a
deterministic fallback, so the whole recovery loop executes locally. This is the
narration spine for the ~3-minute video.

    uv run clearport-demo            # or: python -m clearport.scripts.demo

Beats (locked):
    1. S4   structural signer fix        -> fast AUTO heal
    2. money shot: hard HS variant       -> eval-gate VETO -> human corrects ->
                                            experiment beats baseline -> PROMOTE ③
    3. repeat the hard variant           -> self-heals autonomously from ③
    4. S2   EEI > $2,500                  -> $-hard-line ESCALATE -> human approves
    5. S3   restricted goods             -> danger ESCALATE -> human approves
    6. drift: silent destination rule    -> DRIFT ALERT -> auto-heals the schema
    7. wildcard W1 contents_explanation  -> AUTO heal
Then prints the four headline metrics.
"""

from __future__ import annotations

from clearport.agents import patch_engine
from clearport.agents.classifier import HSClassification
from clearport.api.store import RecoveryRun
from clearport.config import settings
from clearport.seeds.shipments import get_seed
from clearport.service import ClearPortService

LINE = "─" * 72


def _h(title: str) -> None:
    print(f"\n{LINE}\n▶ {title}\n{LINE}")


def _verdict(run) -> str:
    v = run.result.verdict
    return f"eval={'PASS' if v.passed else 'VETO'}({v.confidence:.2f})"


def _diffs(run) -> str:
    diffs = run.result.patch.field_diff
    if not diffs:
        return "(no field changes)"
    return ", ".join(f"{d.field}: {d.before!r}→{d.after!r}" for d in diffs)


def _show(run, label: str) -> None:
    print(
        f"  [{label}] {run.seed_id or run.id[:8]} · {run.result.rejection.normalized_error_type.value}\n"
        f"        decision={run.result.risk.decision.value} · {_verdict(run)} · status={run.status.value}\n"
        f"        patch: {_diffs(run)}"
    )
    if run.result.risk.reasons:
        print(f"        why: {run.result.risk.reasons[0]}")


def _break_classifier() -> None:
    patch_engine.classify_hs = lambda *a, **k: HSClassification(  # type: ignore[assignment]
        code=None, description="unknown", confidence=0.1, source="none"
    )


def _recover(svc: ClearPortService, seed_id: str) -> RecoveryRun:
    run = svc.submit_seed(seed_id)
    assert run is not None, f"{seed_id} unexpectedly cleared with no rejection"
    return run


def run_demo() -> None:
    settings.clearport_promotion_min_evidence = 1  # deterministic promotion for the demo
    original_classifier = patch_engine.classify_hs
    svc = ClearPortService()

    print("ClearPort — autonomous customs-recovery agent (offline demo)")
    print("Gemini 2.5 · Google ADK · Arize Phoenix (eval-gate, experiments, drift)")

    # ── Beat 1: structural fix, fast auto-heal ───────────────────────────
    _h("Beat 1 — S4 missing customs_signer → fast AUTO heal")
    _show(_recover(svc, "S4"), "AUTO")

    # ── Beat 2: the money shot — eval-gate veto + learning ───────────────
    _h("Beat 2 — hard HS variant: the agent's naive fix is WRONG")
    _break_classifier()  # simulate a novel case the classifier cannot resolve
    run = _recover(svc, "S1")
    _show(run, "VETO")
    print("  → Arize eval-gate refused the patch; routed to a human (no label bought).")

    print("\n  Human corrects the HS code (830249) …")
    corrected = get_seed("S1").payload.model_copy(deep=True)
    corrected.items[0].hs_tariff_number = "830249"
    svc.correct(run.id, corrected, note="classified by licensed broker")

    print("  Running experiment-gated promotion (episodic ② → distilled ③) …")
    for r in svc.run_learning():
        flag = "PROMOTED" if r.promoted else "held"
        print(
            f"    [{flag}] {r.memory_key} · baseline={r.experiment.baseline_score:.2f} "
            f"candidate={r.experiment.candidate_score:.2f} · fix={r.recommended_fix}"
        )

    # ── Beat 3: self-heal from promoted memory (classifier still broken) ─
    _h("Beat 3 — same hard variant returns → self-heals from ③ (memory, not classifier)")
    run3 = _recover(svc, "S1")
    _show(run3, "AUTO")
    healed_from_memory = "memory-lesson" in run3.result.patch.tool_calls_used
    print(f"  → healed_from_promoted_lesson={healed_from_memory}")
    patch_engine.classify_hs = original_classifier  # restore the real classifier

    # ── Beat 4: $ hard-line escalation + human approval ──────────────────
    _h("Beat 4 — S2 EEI value > $2,500 → hard-line ESCALATE → human approves")
    run_s2 = _recover(svc, "S2")
    _show(run_s2, "ESCALATE")
    approved = svc.approve(run_s2.id)
    print(f"  → human approved · status={approved.status.value} · label={approved.label_id}")

    # ── Beat 5: restricted-goods escalation + human approval ─────────────
    _h("Beat 5 — S3 restricted goods → danger ESCALATE → human approves")
    run_s3 = _recover(svc, "S3")
    _show(run_s3, "ESCALATE")
    svc.approve(run_s3.id)
    print("  → human approved the restricted-goods shipment.")

    # ── Beat 6: drift — silent destination rule change, auto-healed ──────
    _h("Beat 6 — destination silently changes a rule → DRIFT ALERT → auto-heal")
    drift = svc.trigger_drift("C0")
    d = drift.get("drift", {})
    print(
        f"  drift: key={d.get('memory_key')} pass_rate={d.get('pass_rate')} "
        f"< floor={d.get('floor')} → drifted={d.get('drifted')}"
    )
    print(f"  → auto-healed: status={drift.get('healed_status')} · patch fields="
          f"{[f['field'] for f in drift.get('field_diff', [])]}")

    # ── Wildcard: unrehearsed generality ─────────────────────────────────
    _h("Wildcard — W1 contents_explanation missing → AUTO heal")
    _show(_recover(svc, "W1"), "AUTO")

    # ── Metrics ──────────────────────────────────────────────────────────
    _h("Headline metrics")
    m = svc.metrics()
    print(f"  recovery time      : {m.avg_recovery_seconds:.3f}s avg "
          f"(broker baseline {m.broker_baseline_seconds/86400:.0f} days)")
    print(f"  demurrage saved    : ${m.total_demurrage_saved_usd:,.0f} "
          f"across {m.resolved} resolved shipments")
    print(f"  auto-resolved      : {m.pct_auto_resolved:.0f}% "
          f"({m.auto_resolved}/{m.runs_total}); {m.escalated} safe escalations")
    print(f"  self-heal speed-up : {m.self_heal_speedup:.1f}× on repeat errors")
    print(f"\n  assumptions: {m.assumptions}")
    print(f"\n{LINE}\nDemo complete. Open the dashboard + Phoenix to inspect live traces.\n{LINE}")


def main() -> None:
    run_demo()


if __name__ == "__main__":
    main()
