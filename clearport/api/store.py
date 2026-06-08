"""In-memory store for recovery runs and the approval queue.

Offline-friendly and dependency-light so the service layer can be unit-tested
without Postgres or FastAPI. A Cloud SQL-backed store can replace this behind the
same interface in production.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from clearport.agents.orchestrator import LoopResult, LoopStatus
from clearport.schemas import new_id, utcnow


class RunStatus(str, Enum):
    AUTO_RESOLVED = "AUTO_RESOLVED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REJECTED = "REJECTED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    HUMAN_CORRECTED = "HUMAN_CORRECTED"


_FROM_LOOP = {
    LoopStatus.AUTO_RESOLVED: RunStatus.AUTO_RESOLVED,
    LoopStatus.AWAITING_APPROVAL: RunStatus.AWAITING_APPROVAL,
    LoopStatus.REJECTED: RunStatus.REJECTED,
}


class RecoveryRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    created_at: datetime = Field(default_factory=utcnow)
    seed_id: str | None = None
    result: LoopResult
    status: RunStatus
    resolved_at: datetime | None = None
    label_id: str | None = None
    human_note: str | None = None

    @classmethod
    def from_result(cls, result: LoopResult) -> RecoveryRun:
        status = _FROM_LOOP.get(result.status, RunStatus.AWAITING_APPROVAL)
        return cls(
            seed_id=result.rejection.seed_id,
            result=result,
            status=status,
            label_id=result.outcome.label_id,
            resolved_at=utcnow() if status is RunStatus.AUTO_RESOLVED else None,
        )

    @property
    def is_open(self) -> bool:
        return self.status is RunStatus.AWAITING_APPROVAL


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RecoveryRun] = {}

    def add(self, run: RecoveryRun) -> RecoveryRun:
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> RecoveryRun | None:
        return self._runs.get(run_id)

    def list(self) -> list[RecoveryRun]:
        return sorted(self._runs.values(), key=lambda r: r.created_at)

    def open_approvals(self) -> list[RecoveryRun]:
        return [r for r in self.list() if r.is_open]

    def clear(self) -> None:
        self._runs.clear()
