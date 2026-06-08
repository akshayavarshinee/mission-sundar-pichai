"""Phase 1 unit tests: error normalization + HS validity + policy lint."""

from __future__ import annotations

import pytest

from clearport.schemas import (
    ContentsType,
    CustomsItemSpec,
    CustomsPayload,
    NormalizedErrorType,
    RawError,
    RestrictionType,
    Source,
)
from clearport.validation.errors import hs_is_valid, normalize_error, policy_lint


def _payload(**over) -> CustomsPayload:
    base = dict(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Signer",
        items=[
            CustomsItemSpec(
                description="thing",
                quantity=1,
                value=50.0,
                weight_oz=8.0,
                origin_country="IN",
                hs_tariff_number="621440",
            )
        ],
    )
    base.update(over)
    return CustomsPayload(**base)


@pytest.mark.parametrize(
    ("field", "message", "expected"),
    [
        ("customs_signer", "signer required", NormalizedErrorType.SIGNER_MISSING),
        ("contents_explanation", "explanation required", NormalizedErrorType.CONTENTS_EXPLANATION_MISSING),
        ("restriction_comments", "comments required", NormalizedErrorType.RESTRICTION_COMMENTS_MISSING),
        ("hs_tariff_number", "tariff invalid", NormalizedErrorType.HS_INVALID),
        ("eel_pfc", "EEI/AES filing required", NormalizedErrorType.EEI_THRESHOLD_MISMATCH),
        (None, "value must be greater than 0", NormalizedErrorType.ZERO_VALUE),
    ],
)
def test_normalize_by_keyword(field, message, expected) -> None:
    assert normalize_error(RawError(field=field, message=message)) is expected


def test_overlay_source_is_drift() -> None:
    raw = RawError(message="new required field date_format")
    assert normalize_error(raw, source=Source.OVERLAY) is NormalizedErrorType.OVERLAY_SCHEMA_DRIFT


def test_unknown_falls_back_to_payload_context() -> None:
    # Opaque message, but payload is missing a signer -> infer from context.
    raw = RawError(message="declaration could not be processed")
    payload = _payload(customs_signer="")
    assert normalize_error(raw, payload) is NormalizedErrorType.SIGNER_MISSING


def test_unknown_without_payload_is_unknown() -> None:
    assert normalize_error(RawError(message="???")) is NormalizedErrorType.UNKNOWN


@pytest.mark.parametrize(
    ("hs", "ok"),
    [("610910", True), ("6109101000", True), ("1234", False), ("61091", False), (None, False), ("abc123", False)],
)
def test_hs_is_valid(hs, ok) -> None:
    assert hs_is_valid(hs) is ok


def test_policy_lint_priority_signer_first() -> None:
    # Missing signer AND invalid HS -> signer reported first (priority order).
    payload = _payload(customs_signer="")
    payload.items[0].hs_tariff_number = "12"
    assert policy_lint(payload) is NormalizedErrorType.SIGNER_MISSING


def test_policy_lint_clean_is_none() -> None:
    assert policy_lint(_payload()) is None


def test_policy_lint_eei_threshold() -> None:
    payload = _payload(eel_pfc="NOEEI 30.37(a)")
    payload.items[0].value = 3200.0
    assert policy_lint(payload) is NormalizedErrorType.EEI_THRESHOLD_MISMATCH


def test_policy_lint_restriction() -> None:
    payload = _payload(restriction_type=RestrictionType.QUARANTINE, restriction_comments=None)
    assert policy_lint(payload) is NormalizedErrorType.RESTRICTION_COMMENTS_MISSING
