"""Phase 6 tests: the application service + approval flow (offline)."""

from __future__ import annotations

import pytest

from clearport.api.store import RunStatus
from clearport.schemas import CustomsPayload
from clearport.seeds.shipments import get_seed
from clearport.service import ApprovalError, ClearPortService


def _service() -> ClearPortService:
    return ClearPortService()


def test_clean_control_returns_none() -> None:
    assert _service().submit_seed("C0") is None


def test_auto_resolved_run() -> None:
    run = _service().submit_seed("S4")
    assert run is not None
    assert run.status is RunStatus.AUTO_RESOLVED
    assert run.result.outcome.demurrage_saved_usd > 0


def test_escalation_then_approval() -> None:
    svc = _service()
    run = svc.submit_seed("S2")  # EEI hard line -> awaiting approval
    assert run.status is RunStatus.AWAITING_APPROVAL
    assert run in svc.list_approvals()

    approved = svc.approve(run.id, note="ITN filed by broker")
    assert approved.status is RunStatus.HUMAN_APPROVED
    assert approved.label_id is not None
    assert approved.result.outcome.demurrage_saved_usd > 0
    assert svc.list_approvals() == []


def test_escalation_then_rejection() -> None:
    svc = _service()
    run = svc.submit_seed("S3")
    rejected = svc.reject(run.id, note="missing phytosanitary permit")
    assert rejected.status is RunStatus.HUMAN_REJECTED


def test_human_correction_flow() -> None:
    svc = _service()
    run = svc.submit_seed("S2")
    corrected: CustomsPayload = get_seed("S2").payload.model_copy(deep=True)
    corrected.eel_pfc = "AES X20250101123456"  # human supplies a real ITN
    out = svc.correct(run.id, corrected, note="filed EEI")
    assert out.status is RunStatus.HUMAN_CORRECTED
    assert out.label_id is not None


def test_double_approval_is_conflict() -> None:
    svc = _service()
    run = svc.submit_seed("S2")
    svc.approve(run.id)
    with pytest.raises(ApprovalError):
        svc.approve(run.id)


def test_metrics_reflect_runs() -> None:
    svc = _service()
    svc.submit_seed("S4")  # auto
    svc.submit_seed("S1")  # auto
    r = svc.submit_seed("S2")  # escalate
    svc.approve(r.id)

    m = svc.metrics()
    assert m.runs_total == 3
    assert m.auto_resolved == 2
    assert m.resolved == 3
    assert m.pct_auto_resolved == pytest.approx(66.7, abs=0.2)
    assert m.total_demurrage_saved_usd > 0
