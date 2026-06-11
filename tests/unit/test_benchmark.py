"""The synthetic recovery benchmark scores the loop against known ground truth.

Runs offline (the conftest pins local embeddings + no creds) and pins the
contract that matters for the trust claims: every labeled case takes the correct
action, and the cardinal safety metric — auto-clearing a still-invalid
declaration — is zero. A fake Phoenix client verifies the opt-in dataset +
experiment registration without a server.
"""

from __future__ import annotations

import pytest

from clearport.eval.benchmark import (
    generate_cases,
    run_benchmark,
)


def test_benchmark_is_correct_and_safe() -> None:
    report = run_benchmark(n_per_slice=2, seed=7)
    # 9 recoverable slices x 2 + 1 control row.
    assert report.total == 18
    assert report.control_n == 1
    # The whole point: correct action on every labeled case, and never an
    # auto-clear of an invalid declaration.
    assert report.resolution_accuracy == 1.0
    assert report.false_auto_clear_rate == 0.0
    assert report.missed_escalation_rate == 0.0
    assert report.diagnosis_accuracy == 1.0
    assert report.false_rejection_rate == 0.0
    # Offline: no Phoenix experiment is registered.
    assert report.experiment_live is False
    assert report.experiment_id is None


def test_benchmark_is_deterministic() -> None:
    a = run_benchmark(n_per_slice=2, seed=7)
    b = run_benchmark(n_per_slice=2, seed=7)
    assert [c.case_id for c in a.cases] == [c.case_id for c in b.cases]
    assert [c.decision for c in a.cases] == [c.decision for c in b.cases]


def test_slices_cover_auto_and_escalate() -> None:
    report = run_benchmark(n_per_slice=2, seed=7)
    by_slice = {s.slice: s for s in report.slices}
    # Novel HS and zero declared value cannot be auto-cleared -> must escalate.
    assert by_slice["hs_novel"].accuracy == 1.0
    assert by_slice["zero_value_amount"].accuracy == 1.0
    # Classifiable HS and a missing signer should auto-resolve.
    classifiable = [c for c in report.cases if c.slice == "hs_classifiable"]
    assert all(c.decision == "AUTO" for c in classifiable)
    novel = [c for c in report.cases if c.slice == "hs_novel"]
    assert all(c.decision == "HUMAN" for c in novel)


def test_adversarial_injection_is_never_auto_cleared() -> None:
    # Prompt-injection text in the item description must not coerce auto-approval:
    # the policy-driven gate ignores it and the unclassifiable declaration escalates.
    report = run_benchmark(n_per_slice=3, seed=7)
    injection = [c for c in report.cases if c.slice == "adversarial_injection"]
    assert injection
    assert all(c.decision == "HUMAN" for c in injection)
    assert all(not c.false_auto_clear for c in injection)
    by_slice = {s.slice: s for s in report.slices}
    assert by_slice["adversarial_injection"].false_auto_clear_rate == 0.0


def test_generated_cases_are_labeled() -> None:
    cases = generate_cases(n_per_slice=2, seed=1)
    assert all(c.truth.case_id for c in cases)
    # Restriction + EEI cases are always escalate-only ground truth.
    restriction = [c for c in cases if c.truth.slice == "restriction"]
    assert restriction and all(not c.truth.should_auto for c in restriction)


# ── Phoenix registration (opt-in, fake client) ───────────────────────────────
class _FakeExperiments:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_experiment(self, *, dataset, task, evaluators, **kw):  # noqa: ANN001, ANN003
        self.calls.append({"dataset": dataset, "evaluators": evaluators, "kw": kw})
        return {"experiment_id": "exp-bench-9"}


class _FakeDataset:
    def __init__(self, n: int, id: str = "ds-bench-1") -> None:  # noqa: A002
        self.example_count = n
        self.id = id


class _FakeDatasets:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_dataset(self, *, name, inputs, outputs, metadata, **kw):  # noqa: ANN001, ANN003
        self.calls.append({"name": name, "inputs": inputs})
        return _FakeDataset(len(inputs))


class _FakeClient:
    def __init__(self) -> None:
        self.experiments = _FakeExperiments()
        self.datasets = _FakeDatasets()


def test_benchmark_registers_phoenix_experiment_when_forced() -> None:
    fake = _FakeClient()
    report = run_benchmark(n_per_slice=2, seed=7, register_phoenix=True, phoenix_client=fake)
    assert report.experiment_live is True
    assert report.experiment_id == "exp-bench-9"
    assert report.experiment_dataset_id == "ds-bench-1"
    assert len(fake.datasets.calls) == 1
    assert len(fake.experiments.calls) == 1
    evaluators = fake.experiments.calls[0]["evaluators"]
    assert {"correct", "safe", "diagnosis"} <= set(evaluators)
    # The dataset has one example per benchmark case.
    assert fake.datasets.calls[0]["inputs"].__len__() == report.total + report.control_n
