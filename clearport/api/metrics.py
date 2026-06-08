"""The four headline metrics, computed from the run store.

    1. recovery time      — agent loop seconds vs the broker-days baseline
    2. $ demurrage saved   — summed across resolved shipments (stated assumption)
    3. % auto-resolved     — with the safe-escalation count alongside
    4. self-heal speed-up  — first vs repeat latency for the same memory key
"""

from __future__ import annotations

from statistics import mean

from pydantic import BaseModel

from clearport.api.store import RecoveryRun, RunStatus, RunStore
from clearport.config import settings

_RESOLVED = {RunStatus.AUTO_RESOLVED, RunStatus.HUMAN_APPROVED, RunStatus.HUMAN_CORRECTED}


class Metrics(BaseModel):
    runs_total: int
    auto_resolved: int
    awaiting_approval: int
    escalated: int
    resolved: int
    avg_recovery_seconds: float
    broker_baseline_seconds: float
    total_demurrage_saved_usd: float
    pct_auto_resolved: float
    self_heal_speedup: float
    assumptions: str


def _self_heal_speedup(runs: list[RecoveryRun]) -> float:
    by_key: dict[str, list[float]] = {}
    for r in sorted(runs, key=lambda x: x.created_at):
        by_key.setdefault(r.result.outcome.memory_key, []).append(r.result.recovery_seconds)
    ratios: list[float] = []
    for seconds in by_key.values():
        if len(seconds) >= 2:
            first = seconds[0]
            repeat = mean(seconds[1:]) or 1e-9
            ratios.append(first / repeat)
    return round(mean(ratios), 2) if ratios else 1.0


def compute_metrics(store: RunStore) -> Metrics:
    runs = store.list()
    total = len(runs)
    auto = sum(1 for r in runs if r.status is RunStatus.AUTO_RESOLVED)
    awaiting = sum(1 for r in runs if r.status is RunStatus.AWAITING_APPROVAL)
    resolved = sum(1 for r in runs if r.status in _RESOLVED)
    escalated = sum(
        1
        for r in runs
        if r.status
        in (RunStatus.HUMAN_APPROVED, RunStatus.HUMAN_CORRECTED, RunStatus.HUMAN_REJECTED)
    )
    recovery_times = [r.result.recovery_seconds for r in runs] or [0.0]
    demurrage = sum(r.result.outcome.demurrage_saved_usd for r in runs)
    broker_baseline = settings.clearport_broker_days * 86400.0

    return Metrics(
        runs_total=total,
        auto_resolved=auto,
        awaiting_approval=awaiting,
        escalated=escalated,
        resolved=resolved,
        avg_recovery_seconds=round(mean(recovery_times), 4),
        broker_baseline_seconds=broker_baseline,
        total_demurrage_saved_usd=round(demurrage, 2),
        pct_auto_resolved=round((auto / total * 100.0) if total else 0.0, 1),
        self_heal_speedup=_self_heal_speedup(runs),
        assumptions=(
            f"Broker baseline: {settings.clearport_broker_days:.0f} days at "
            f"${settings.clearport_demurrage_per_day_usd:.0f}/day demurrage per shipment."
        ),
    )
