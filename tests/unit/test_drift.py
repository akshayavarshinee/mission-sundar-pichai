"""Phase 8 tests: Regional Rule Overlay + drift detection + auto-heal."""

from __future__ import annotations

from clearport.api.store import RunStatus
from clearport.arize.drift import DriftMonitor
from clearport.config import settings
from clearport.schemas import NormalizedErrorType, Source
from clearport.seeds.shipments import get_seed
from clearport.service import ClearPortService
from clearport.validation.regional_overlay import RegionalRuleOverlay


def test_overlay_inactive_by_default() -> None:
    overlay = RegionalRuleOverlay()
    assert overlay.validate(get_seed("C0").payload).ok is True
    assert overlay.make_rejection(get_seed("C0")) is None


def test_overlay_flip_requires_new_field() -> None:
    overlay = RegionalRuleOverlay()
    overlay.flip(True)
    result = overlay.validate(get_seed("C0").payload)  # no contents_explanation
    assert result.ok is False
    assert result.raw_error.field == "contents_explanation"

    rejection = overlay.make_rejection(get_seed("C0"))
    assert rejection is not None
    assert rejection.source is Source.OVERLAY
    assert rejection.normalized_error_type is NormalizedErrorType.OVERLAY_SCHEMA_DRIFT


def test_drift_monitor_math(monkeypatch) -> None:
    monkeypatch.setattr(settings, "clearport_drift_min_sample", 3, raising=False)
    monkeypatch.setattr(settings, "clearport_drift_passrate_floor", 0.6, raising=False)
    monitor = DriftMonitor()
    key = "IN->US|hs62|OVERLAY_SCHEMA_DRIFT"

    for _ in range(5):
        monitor.observe(key, passed=True)
    assert monitor.status(key).drifted is False

    for _ in range(8):
        monitor.observe(key, passed=False)
    status = monitor.status(key)
    assert status.pass_rate < 0.6
    assert status.drifted is True


def test_service_trigger_drift_alerts_and_heals() -> None:
    svc = ClearPortService()
    result = svc.trigger_drift("C0")

    assert result["drift"]["drifted"] is True
    assert result["healed_status"] == RunStatus.AUTO_RESOLVED.value
    # the heal added the newly-required field
    fields = {d["field"] for d in result["field_diff"]}
    assert "contents_explanation" in fields

    # a drift_alert event was published for the dashboard
    types = {e["type"] for e in svc.bus.history()}
    assert "drift_alert" in types
