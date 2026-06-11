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
    experiment_dataset_id: str | None = None
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


def _dataset_id_of(dataset) -> str | None:  # noqa: ANN001
    if isinstance(dataset, dict):
        return dataset.get("id") or dataset.get("dataset_id")
    return getattr(dataset, "id", None) or getattr(dataset, "dataset_id", None)


def _register_phoenix_experiment(
    memory_key: str,
    error_type: NormalizedErrorType,
    candidate_rows: list[dict],
    baseline: float,
    candidate: float,
    client=None,  # noqa: ANN001 — phoenix.client.Client, injected in tests
) -> tuple[str, str | None] | None:
    """Register a genuine Phoenix experiment for this promotion (opt-in).

    Gated behind ``CLEARPORT_PHOENIX_EXPERIMENTS=on`` because Phoenix's
    experiment runner requires a reachable server even in dry-run; offline this
    is skipped entirely so the deterministic promotion path never blocks. When
    enabled it uploads the candidate corrections as a real **server-side**
    Phoenix dataset (so the experiment is visible and clickable in the Phoenix
    UI) and runs them through Phoenix's experiment engine, returning the real
    ``(experiment_id, dataset_id)`` pair.
    """
    if (settings.clearport_phoenix_experiments or "off").lower() != "on":
        return None
    if not candidate_rows:
        return None
    try:
        import contextlib
        import io

        if client is None:
            from phoenix.client import Client

            client = Client(base_url=settings.phoenix_host, api_key=settings.phoenix_api_key)

        # Fold the recorded outcome into the input so the task can echo it
        # without depending on how the client binds expected/reference params.
        inputs = [
            {
                **(r.get("input", {}) or {}),
                "accepted": (r.get("output", {}) or {}).get("accepted"),
            }
            for r in candidate_rows
        ]
        outputs = [r.get("output", {}) or {} for r in candidate_rows]
        metadata = [r.get("metadata", {}) or {} for r in candidate_rows]
        dataset_name = f"clearport-promotion::{memory_key}::{new_id('v')}"

        def task(input):  # noqa: ANN001, ANN202 — bound to example["input"]
            return {"accepted": input.get("accepted")}

        def accepted(output) -> float:  # noqa: ANN001
            val = output.get("accepted") if isinstance(output, dict) else output
            return 1.0 if str(val).lower() == "true" else 0.0

        # Phoenix prints a unicode summary/progress banner; redirect it so it
        # neither pollutes logs nor trips Windows console encoding.
        with contextlib.redirect_stdout(io.StringIO()):
            dataset = client.datasets.create_dataset(
                name=dataset_name,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )
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
        dataset_id = _dataset_id_of(dataset)
        if exp_id:
            logger.info(
                "experiment.phoenix_registered",
                memory_key=memory_key,
                experiment_id=exp_id,
                dataset_id=dataset_id,
            )
            return exp_id, dataset_id
        return None
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
    )
    if experiment_id is None:
        experiment_id, experiment_dataset_id = new_id("exp"), None
    else:
        experiment_id, experiment_dataset_id = experiment_id

    result = ExperimentResult(
        experiment_id=experiment_id,
        experiment_dataset_id=experiment_dataset_id,
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
