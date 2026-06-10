"""Error normalization + declaration policy linting.

Two pure, offline-testable concerns live here:

1. :func:`normalize_error` — map a raw carrier/overlay error onto the stable
   :class:`NormalizedErrorType` vocabulary, using the error field/message first
   and falling back to payload context.
2. :func:`policy_lint` — ClearPort's own pre-submission lint of a declaration
   against the *same real rules* EasyPost enforces (signer/explanation/
   restriction/zero-value/HS) plus the EEI $2,500 threshold. This is what lets
   us classify a rejection deterministically and predict seed outcomes.

Both are deterministic and import nothing heavy.
"""

from __future__ import annotations

from clearport.schemas import (
    ContentsType,
    CustomsPayload,
    NormalizedErrorType,
    RawError,
    RestrictionType,
    Source,
)

# The EEI / Electronic Export Information threshold (FTR §30.37(a)).
EEI_THRESHOLD_USD = 2500.0

# Ordered field/message keyword rules. Order matters: most specific first, the
# generic "zero value" numeric checks last so they don't shadow field rules.
_KEYWORD_RULES: tuple[tuple[NormalizedErrorType, tuple[str, ...]], ...] = (
    (NormalizedErrorType.SIGNER_MISSING, ("customs_signer", "signer")),
    (
        NormalizedErrorType.CONTENTS_EXPLANATION_MISSING,
        ("contents_explanation", "explanation"),
    ),
    (
        NormalizedErrorType.RESTRICTION_COMMENTS_MISSING,
        ("restriction_comments", "restriction"),
    ),
    (
        NormalizedErrorType.HS_INVALID,
        ("hs_tariff", "tariff", "harmonized", "hs_code", "hs code"),
    ),
    (NormalizedErrorType.EEI_THRESHOLD_MISMATCH, ("eel_pfc", "eei", "aes", "30.37")),
    (
        NormalizedErrorType.ZERO_VALUE,
        ("must be greater than", "greater than 0", "cannot be zero", "must be a positive"),
    ),
)


def hs_is_valid(hs_tariff_number: str | None) -> bool:
    """HTS codes are 6 (international) or 10 (full US) digit numeric strings."""
    if not hs_tariff_number:
        return False
    digits = "".join(c for c in hs_tariff_number if c.isdigit())
    if len(digits) != len(hs_tariff_number.replace(".", "").strip()):
        # contains non-digit, non-dot characters
        return False
    return len(digits) in (6, 10)


def policy_lint(payload: CustomsPayload) -> NormalizedErrorType | None:
    """Return the first rule a declaration violates, or ``None`` if clean.

    Mirrors EasyPost's real conditional customs validations, in a deterministic
    priority order, plus the EEI threshold policy.
    """
    if payload.customs_certify and not (payload.customs_signer or "").strip():
        return NormalizedErrorType.SIGNER_MISSING

    if payload.contents_type is ContentsType.OTHER and not (
        payload.contents_explanation or ""
    ).strip():
        return NormalizedErrorType.CONTENTS_EXPLANATION_MISSING

    if payload.restriction_type is not RestrictionType.NONE and not (
        payload.restriction_comments or ""
    ).strip():
        return NormalizedErrorType.RESTRICTION_COMMENTS_MISSING

    for item in payload.items:
        if item.value <= 0 or item.quantity <= 0 or item.weight_oz <= 0:
            return NormalizedErrorType.ZERO_VALUE

    for item in payload.items:
        if not hs_is_valid(item.hs_tariff_number):
            return NormalizedErrorType.HS_INVALID

    eel = (payload.eel_pfc or "").upper()
    if payload.total_value >= EEI_THRESHOLD_USD and eel.startswith("NOEEI"):
        return NormalizedErrorType.EEI_THRESHOLD_MISMATCH

    return None


def normalize_error(
    raw: RawError,
    payload: CustomsPayload | None = None,
    source: Source = Source.EASYPOST,
) -> NormalizedErrorType:
    """Classify a raw error into a :class:`NormalizedErrorType`.

    Strategy: overlay marker → field/message keywords → payload-context lint →
    UNKNOWN.
    """
    if source is Source.OVERLAY or (raw.code or "").upper() == "OVERLAY_SCHEMA_DRIFT":
        return NormalizedErrorType.OVERLAY_SCHEMA_DRIFT

    haystack = " ".join(
        part.lower() for part in (raw.field or "", raw.message or "", raw.code or "")
    )
    for error_type, keywords in _KEYWORD_RULES:
        if any(kw in haystack for kw in keywords):
            return error_type

    if payload is not None:
        inferred = policy_lint(payload)
        if inferred is not None:
            return inferred

    return NormalizedErrorType.UNKNOWN
