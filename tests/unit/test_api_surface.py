"""API surface: provenance, evidence-confidence basis, trace waterfall, memory.

Exercised through the real FastAPI app (offline) so the contract the dashboard
depends on is locked: every run carries its rejection provenance and a computed
confidence basis, the loop exposes per-step durations, and the three memory
tiers are browsable.
"""

from __future__ import annotations

from clearport.agents.orchestrator import RecoveryLoop
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed

_EXPECTED_STEPS = ["recall", "diagnose", "patch", "verify", "decide", "act", "learn"]


def test_loop_records_named_trace_steps() -> None:
    rejection = run_seed(get_seed("S4"))
    assert rejection is not None
    result = RecoveryLoop().run(rejection)
    names = [s.name for s in result.trace_steps]
    assert names == _EXPECTED_STEPS
    assert all(s.duration_ms >= 0 for s in result.trace_steps)


def test_recover_summary_carries_provenance_and_confidence_basis() -> None:
    from clearport.service import ClearPortService

    svc = ClearPortService()
    run = svc.submit_seed("S4")
    assert run is not None

    from clearport.api.main import _run_summary

    summary = _run_summary(run)
    assert summary["rejection_source"] == "compliance"
    assert summary["caught_by"] == "ClearPort Compliance Engine"
    assert summary["eval"]["confidence_basis"]  # non-empty, computed
    assert "value" in summary["risk"]["components"]
    assert summary["diagnosis"]["confidence_basis"]


def test_trace_endpoint_payload_shape() -> None:
    from clearport.service import ClearPortService

    svc = ClearPortService()
    run = svc.submit_seed("S4")
    assert run is not None
    steps = run.result.trace_steps
    total = round(sum(s.duration_ms for s in steps), 3)
    assert [s.name for s in steps] == _EXPECTED_STEPS
    assert total >= 0


def test_memory_endpoints_return_data() -> None:
    from clearport.api.main import memory_episodic, memory_law, memory_lessons

    law = memory_law()
    assert len(law) >= 1
    assert {"source", "ref", "text"} <= set(law[0])

    # lessons start empty (only promotion writes them); shape must still be a list
    assert isinstance(memory_lessons(), list)
    assert isinstance(memory_episodic(), list)
