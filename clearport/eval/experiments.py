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


def _experiment_id_of(ran) -> str | None:  # noqa: ANN001
    if isinstance(ran, dict):
        return ran.get("experiment_id") or ran.get("id")
    return getattr(ran, "experiment_id", None) or getattr(ran, "id", None)


def _register_phoenix_experiment(
    memory_key: str,
    error_type: NormalizedErrorType,
    candidate_rows: list[dict],
    baseline: float,
    candidate: float,
    client=None,  # noqa: ANN001 — phoenix.client.Client, injected in tests
) -> str | None:
    """Register a genuine Phoenix experiment for this promotion (opt-in).

    Gated behind ``CLEARPORT_PHOENIX_EXPERIMENTS=on`` because Phoenix's
    experiment runner requires a reachable server even in dry-run; offline this
    is skipped entirely so the deterministic promotion path never blocks. When
    enabled it runs the candidate corrections through Phoenix's experiment engine
    and returns the real ``experiment_id`` (visible in the Phoenix UI).
    """
    if (settings.clearport_phoenix_experiments or "off").lower() != "on":
        return None
    if not candidate_rows:
        return None
    try:
        import contextlib
        import io

        from phoenix.client.resources.datasets import Dataset

        examples = [
            {
                "id": r.get("id", f"cand-{i}"),
                "input": r.get("input", {}) or {},
                "output": r.get("output", {}) or {},
                "metadata": r.get("metadata", {}) or {},
            }
            for i, r in enumerate(candidate_rows)
        ]
        dataset = Dataset.from_dict(
            {
                "id": memory_key,
                "name": f"clearport-promotion::{memory_key}",
                "version_id": "promotion",
                "examples": examples,
            }
        )

        def task(example):  # noqa: ANN001, ANN202
            return example["output"].get("accepted")

        def accepted(output) -> float:  # noqa: ANN001
            return 1.0 if str(output).lower() == "true" else 0.0

        if client is None:
            from phoenix.client import Client

            client = Client(base_url=settings.phoenix_host, api_key=settings.phoenix_api_key)

        # Phoenix prints a unicode summary/progress banner; redirect it so it
        # neither pollutes logs nor trips Windows console encoding.
        with contextlib.redirect_stdout(io.StringIO()):
            ran = client.experiments.run_experiment(
                dataset=dataset,
                task=task,
                evaluators={"accepted": accepted},
                experiment_name=f"promotion-{error_type.value}",
                experiment_metadata={
                    "memory_key": memory_key,
                    "baseline_score": baseline,
                    "candidate_score": candidate,
                },
                print_summary=False,
            )
        exp_id = _experiment_id_of(ran)
        if exp_id:
            logger.info(
                "experiment.phoenix_registered", memory_key=memory_key, experiment_id=exp_id
            )
        return exp_id
    except Exception as exc:  # noqa: BLE001 — never let telemetry break promotion
        logger.warning("experiment.phoenix_failed", memory_key=memory_key, error=str(exc))
        return None


def run_experiment(
    memory_key: str,
    error_type: NormalizedErrorType,
    episodic: EpisodicMemory | None = None,
    phoenix_client=None,  # noqa: ANN001 — test seam for the Phoenix experiment runner
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

    experiment_id = _register_phoenix_experiment(
        memory_key, error_type, candidate_rows, round(baseline, 3), round(candidate, 3), phoenix_client
    ) or new_id("exp")

    result = ExperimentResult(
        experiment_id=experiment_id,
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
        experiment_id=experiment_id,
    )
    return result
