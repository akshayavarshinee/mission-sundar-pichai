"""Drift detection — watch the pass-rate of promoted lessons over time.

When a destination silently changes a rule, a previously-reliable lesson starts
failing. The monitor keeps a sliding window of recent pass/fail observations per
memory key; when the windowed pass-rate falls below the floor (with enough
samples), it raises a drift alert so the loop can re-investigate and re-promote.
"""

from __future__ import annotations

from collections import deque
from statistics import mean

import structlog
from pydantic import BaseModel

from clearport.config import settings

logger = structlog.get_logger(__name__)


class DriftStatus(BaseModel):
    memory_key: str
    observations: int
    pass_rate: float
    floor: float
    window: int
    drifted: bool


class DriftMonitor:
    def __init__(self) -> None:
        self._windows: dict[str, deque[bool]] = {}

    def observe(self, memory_key: str, passed: bool) -> None:
        window = self._windows.setdefault(
            memory_key, deque(maxlen=settings.clearport_drift_window)
        )
        window.append(bool(passed))

    def status(self, memory_key: str) -> DriftStatus:
        window = self._windows.get(memory_key, deque())
        observations = len(window)
        rate = mean(1.0 if p else 0.0 for p in window) if observations else 1.0
        floor = settings.clearport_drift_passrate_floor
        drifted = (
            observations >= settings.clearport_drift_min_sample and rate < floor
        )
        status = DriftStatus(
            memory_key=memory_key,
            observations=observations,
            pass_rate=round(rate, 3),
            floor=floor,
            window=settings.clearport_drift_window,
            drifted=drifted,
        )
        if drifted:
            logger.info("drift.detected", memory_key=memory_key, pass_rate=status.pass_rate)
        return status

    def reset(self) -> None:
        self._windows.clear()
