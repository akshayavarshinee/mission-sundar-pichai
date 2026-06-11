"""In-process Phoenix-client episodic backend: fast reads + mirrored writes.

A fake Phoenix client captures the dataset calls so the mirroring + hydrate
logic is verified without a live Phoenix server.
"""

from __future__ import annotations

from clearport.memory.episodic import PhoenixClientEpisodicMemory


class _FakeDatasets:
    def __init__(self) -> None:
        self.added: list[dict] = []
        self.created: list[dict] = []
        self.dataset_obj = type("DS", (), {"examples": []})()

    def get_dataset(self, *, dataset, **_):  # noqa: ANN001, ANN002
        return self.dataset_obj

    def add_examples_to_dataset(self, *, dataset, inputs, outputs, metadata, **_):  # noqa: ANN001
        self.added.append({"dataset": dataset, "inputs": inputs, "outputs": outputs, "metadata": metadata})

    def create_dataset(self, *, name, inputs, outputs, metadata, **_):  # noqa: ANN001
        self.created.append({"name": name, "inputs": inputs})


class _FakeClient:
    def __init__(self) -> None:
        self.datasets = _FakeDatasets()


def _wired() -> tuple[PhoenixClientEpisodicMemory, _FakeClient]:
    mem = PhoenixClientEpisodicMemory(dataset="clearport-outcomes")
    fake = _FakeClient()
    mem._client = fake  # inject the fake transport
    return mem, fake


def test_reads_served_from_cache_after_write() -> None:
    mem, _ = _wired()
    mem.add_example(
        input={"summary": "S4 signer"},
        output={"accepted": True},
        metadata={"memory_key": "IN->US|hs62|SIGNER_MISSING", "kind": "outcome"},
    )
    rows = mem.get_examples(where={"memory_key": "IN->US|hs62|SIGNER_MISSING"})
    assert len(rows) == 1
    assert rows[0]["output"]["accepted"] is True


def test_write_is_mirrored_to_phoenix_dataset() -> None:
    mem, fake = _wired()
    mem.add_example(input={"summary": "x"}, output={"accepted": False}, metadata={"kind": "outcome"})
    assert len(fake.datasets.added) == 1
    call = fake.datasets.added[0]
    assert call["dataset"] == "clearport-outcomes"
    assert call["metadata"][0]["kind"] == "outcome"
    # the local example id is threaded into the mirrored metadata
    assert "id" in call["metadata"][0]


def test_mirror_failure_falls_back_to_create_then_never_raises() -> None:
    mem, fake = _wired()

    def _boom(**_):  # noqa: ANN003
        raise RuntimeError("dataset missing")

    fake.datasets.add_examples_to_dataset = _boom  # type: ignore[assignment]
    # Must not raise; should attempt create_dataset as the fallback.
    mem.add_example(input={"summary": "y"}, output={"accepted": True}, metadata={"kind": "outcome"})
    assert len(fake.datasets.created) == 1
    # read path still works from the in-process cache
    assert len(mem.get_examples()) == 1
