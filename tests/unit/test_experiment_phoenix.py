"""Opt-in Phoenix experiment registration for the promotion gate.

Verifies the wiring deterministically with a fake Phoenix client: when enabled,
the candidate corrections are run through ``experiments.run_experiment`` and the
real experiment id is threaded onto the result; when disabled (the offline
default) the promotion stays fully local.
"""

from __future__ import annotations

from clearport.config import settings
from clearport.eval.experiments import run_experiment
from clearport.memory.episodic import InMemoryEpisodicMemory
from clearport.schemas import NormalizedErrorType

_KEY = "IN->US|hs62|SIGNER_MISSING"


class _FakeExperiments:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_experiment(self, *, dataset, task, evaluators, **kw):  # noqa: ANN001, ANN003
        self.calls.append({"dataset": dataset, "task": task, "evaluators": evaluators, "kw": kw})
        return {"experiment_id": "exp-live-7"}


class _FakeClient:
    def __init__(self) -> None:
        self.experiments = _FakeExperiments()


def _seed_candidates(mem: InMemoryEpisodicMemory, n: int = 3) -> None:
    for _ in range(n):
        mem.add_example(
            input={"summary": "signer filled"},
            output={"accepted": True},
            metadata={"memory_key": _KEY, "kind": "human_correction", "error_type": "SIGNER_MISSING"},
        )


def test_phoenix_experiment_registered_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "clearport_phoenix_experiments", "on", raising=False)
    mem = InMemoryEpisodicMemory()
    _seed_candidates(mem)
    fake = _FakeClient()

    result = run_experiment(
        _KEY, NormalizedErrorType.SIGNER_MISSING, episodic=mem, phoenix_client=fake
    )

    assert result.experiment_id == "exp-live-7"
    assert len(fake.experiments.calls) == 1
    assert fake.experiments.calls[0]["dataset"].example_count == 3
    assert "accepted" in fake.experiments.calls[0]["evaluators"]


def test_promotion_stays_local_when_disabled() -> None:
    # Default (flag off): no Phoenix call, deterministic local experiment id.
    mem = InMemoryEpisodicMemory()
    _seed_candidates(mem)
    result = run_experiment(_KEY, NormalizedErrorType.SIGNER_MISSING, episodic=mem)
    assert result.experiment_id.startswith("exp")
    assert result.experiment_id != "exp-live-7"
