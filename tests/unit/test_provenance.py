"""Provenance: a rejection is labeled by the surface that actually caught it.

The honesty contract: ClearPort never lets a rejection caught by its own
compliance rules masquerade as a live carrier (EasyPost) rejection.
"""

from __future__ import annotations

from clearport.schemas import Source
from clearport.seeds.shipments import get_seed
from clearport.validation.easypost_client import synthetic_validation
from clearport.validation.harness import run_seed


def test_source_enum_has_provenance_surfaces() -> None:
    assert {s.value for s in Source} >= {"easypost", "hts", "compliance", "overlay"}


def test_source_labels_are_human_readable() -> None:
    assert Source.COMPLIANCE.label == "ClearPort Compliance Engine"
    assert Source.EASYPOST.label == "EasyPost carrier API"
    assert Source.HTS.label == "USITC HTS tariff schedule"


def test_synthetic_violation_labeled_compliance() -> None:
    # EEI threshold is a ClearPort/FTR policy rule (EasyPost test mode never
    # enforces it), so offline it must be attributed to the compliance engine.
    result = synthetic_validation(get_seed("S2").payload)
    assert result.ok is False
    assert result.source is Source.COMPLIANCE


def test_clean_payload_is_ok_with_no_error() -> None:
    result = synthetic_validation(get_seed("C0").payload)
    assert result.ok is True
    assert result.raw_error is None


def test_rejection_event_carries_compliance_source_offline() -> None:
    # Offline (no EASYPOST_API_KEY) every seed is validated by ClearPort's own
    # engine, so the emitted RejectionEvent is labeled COMPLIANCE, not EASYPOST.
    rejection = run_seed(get_seed("S2"))
    assert rejection is not None
    assert rejection.source is Source.COMPLIANCE
