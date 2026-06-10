"""Experiment-gated promotion — the only path from episodic ② to lessons ③.

An experiment compares two strategies over the episodic dataset for a memory key:

* **baseline** — the agent's own autonomous attempts (``kind="outcome"``)
* **candidate** — the human-corrected approach (``kind="human_correction"``)

A candidate is promotable only if its accepted-rate beats the baseline by a
margin and it has enough evidence. Offline this is computed directly from the
dataset examples; with the Phoenix episodic backend the same examples come from a
Phoenix dataset over MCP, so the comparison maps onto a real Phoenix experiment.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from clearport.config import settings
from clearport.memory.episodic import EpisodicMemory, get_episodic
from clearport.schemas import NormalizedErrorType, new_id

logger = structlog.get_logger(__name__)


class ExperimentResult(BaseModel):
    experiment_id: str
    memory_key: str
    error_type: str
    baseline_score: float
    candidate_score: float
    margin: float
    evidence_count: int
    passed: bool


def _kind(example: dict) -> str:
    return str(example.get("metadata", {}).get("kind", ""))


def _accepted_rate(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    accepted = sum(
        1 for r in rows if str(r.get("output", {}).get("accepted")).lower() == "true"
    )
    return accepted / len(rows)


def run_experiment(
    memory_key: str,
    error_type: NormalizedErrorType,
    episodic: EpisodicMemory | None = None,
) -> ExperimentResult:
    episodic = episodic or get_episodic()
    rows = episodic.get_examples(where={"memory_key": memory_key})
    baseline_rows = [r for r in rows if _kind(r) == "outcome"]
    candidate_rows = [r for r in rows if _kind(r) == "human_correction"]

    baseline = _accepted_rate(baseline_rows)
    candidate = _accepted_rate(candidate_rows)
    margin = settings.clearport_promotion_margin
    evidence = len(candidate_rows)
    passed = candidate >= baseline + margin and evidence >= settings.clearport_promotion_min_evidence

    result = ExperimentResult(
        experiment_id=new_id("exp"),
        memory_key=memory_key,
        error_type=error_type.value,
        baseline_score=round(baseline, 3),
        candidate_score=round(candidate, 3),
        margin=margin,
        evidence_count=evidence,
        passed=passed,
    )
    logger.info(
        "experiment.run",
        memory_key=memory_key,
        baseline=result.baseline_score,
        candidate=result.candidate_score,
        passed=passed,
    )
    return result
