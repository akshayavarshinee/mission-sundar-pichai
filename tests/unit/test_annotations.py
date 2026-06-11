"""Eval verdicts are written back onto their Phoenix ``verify`` span.

The Phoenix client is faked, so these run offline and pin the contract: when
annotations are live the verdict is logged with a pass/fail label, the
confidence score, and the rationale; offline (or with no span id) it is a no-op
that never touches Phoenix.
"""

from __future__ import annotations

import pytest

from clearport.arize import annotations as ann_mod
from clearport.arize.annotations import annotate_eval
from clearport.schemas import EvalVerdict


class _FakeSpans:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add_span_annotation(self, **kw):  # noqa: ANN003
        self.calls.append(kw)
        return {"id": "annotation-1"}


class _FakeClient:
    def __init__(self) -> None:
        self.spans = _FakeSpans()


def _verdict(passed: bool) -> EvalVerdict:
    return EvalVerdict(
        patch_id="patch-1",
        judge_model="vertex_ai/gemini-2.5-pro",
        passed=passed,
        confidence=0.82,
        rationale="Matches accepted precedent and cited law.",
    )


def test_writes_pass_annotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ann_mod, "annotations_available", lambda: True)
    fake = _FakeClient()
    ann_id = annotate_eval("0123456789abcdef", _verdict(True), client=fake)
    assert ann_id == "annotation-1"
    call = fake.spans.calls[0]
    assert call["span_id"] == "0123456789abcdef"
    assert call["annotation_name"] == "eval_gate"
    assert call["label"] == "pass"
    assert call["score"] == 0.82
    assert "precedent" in call["explanation"]


def test_writes_fail_annotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ann_mod, "annotations_available", lambda: True)
    fake = _FakeClient()
    annotate_eval("0123456789abcdef", _verdict(False), client=fake)
    assert fake.spans.calls[0]["label"] == "fail"


def test_no_op_without_span_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ann_mod, "annotations_available", lambda: True)
    fake = _FakeClient()
    assert annotate_eval(None, _verdict(True), client=fake) is None
    assert fake.spans.calls == []


def test_no_op_when_disabled_offline() -> None:
    # Default offline: annotations_available() is False, so nothing is written
    # even with a span id and an injected client.
    fake = _FakeClient()
    assert annotate_eval("0123456789abcdef", _verdict(True), client=fake) is None
    assert fake.spans.calls == []
