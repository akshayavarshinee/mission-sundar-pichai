"""Seed shipments — the cinematic-but-real demo spine (India -> US).

Each seed deterministically trips one real customs rule (validated both by
EasyPost test mode and by ClearPort's policy lint), except the clean control.
``expected_error`` is asserted by the seed unit test so the demo never drifts.

    S1  brass keychain   $80    invalid HS "1234"          -> HS_INVALID (auto, reasoning)
    S2  cotton tees      $3,200 NOEEI but >= $2,500        -> EEI_THRESHOLD_MISMATCH ($-veto)
    S3  spice sampler    $40    restricted, no comments     -> RESTRICTION_COMMENTS_MISSING (danger escalate)
    S4  silk scarf       $90    certify=true, signer=""     -> SIGNER_MISSING (fast auto heal)
    S5  sitar bridge     $140   novel item, invalid HS      -> HS_INVALID (earned eval-gate VETO)
    C0  silk scarf       $90    clean control               -> accepted
    W1  artisan bundle   $120   contents=other, no expl.    -> CONTENTS_EXPLANATION_MISSING (live wildcard)
"""

from __future__ import annotations

from pydantic import BaseModel

from clearport.schemas import (
    Address,
    ContentsType,
    CustomsItemSpec,
    CustomsPayload,
    Lane,
    NormalizedErrorType,
    ParcelSpec,
    RestrictionType,
)

# ── shared demo parties ──────────────────────────────────────────────────────
SELLER_IN = Address(
    name="Anaya Handicrafts",
    street1="14 MG Road",
    city="Jaipur",
    state="RJ",
    zip="302001",
    country="IN",
    phone="911412345678",
    email="anaya@example.com",
)

BUYER_US = Address(
    name="Dana Mercer",
    street1="1600 Amphitheatre Pkwy",
    city="Mountain View",
    state="CA",
    zip="94043",
    country="US",
    phone="16505551234",
    email="dana@example.com",
)

LANE_IN_US = Lane(origin="IN", dest="US")
DEFAULT_PARCEL = ParcelSpec(weight_oz=16.0, length_in=9.0, width_in=6.0, height_in=2.0)


class SeedShipment(BaseModel):
    id: str
    persona: str
    note: str
    lane: Lane = LANE_IN_US
    from_address: Address = SELLER_IN
    to_address: Address = BUYER_US
    parcel: ParcelSpec = DEFAULT_PARCEL
    payload: CustomsPayload
    expected_error: NormalizedErrorType | None = None


# ── the seeds ────────────────────────────────────────────────────────────────
S1 = SeedShipment(
    id="S1",
    persona="India -> US handicrafts seller",
    note="Invalid 4-digit HS code; agent must classify the correct HTS.",
    expected_error=NormalizedErrorType.HS_INVALID,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        items=[
            CustomsItemSpec(
                description="Hand-engraved brass keychain",
                quantity=10,
                value=80.0,
                weight_oz=16.0,
                origin_country="IN",
                hs_tariff_number="1234",  # invalid (4 digits)
            )
        ],
    ),
)

S2 = SeedShipment(
    id="S2",
    persona="India -> US textiles seller",
    note="$3,200 declared with NOEEI; over the $2,500 EEI threshold -> hard-line escalate.",
    expected_error=NormalizedErrorType.EEI_THRESHOLD_MISMATCH,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        eel_pfc="NOEEI 30.37(a)",
        items=[
            CustomsItemSpec(
                description="Cotton knit t-shirts (lot)",
                quantity=80,
                value=3200.0,
                weight_oz=320.0,
                origin_country="IN",
                hs_tariff_number="610910",  # valid 6-digit
            )
        ],
    ),
)

S3 = SeedShipment(
    id="S3",
    persona="India -> US food/spice seller",
    note="Quarantine-restricted spices with no restriction_comments -> danger escalate.",
    expected_error=NormalizedErrorType.RESTRICTION_COMMENTS_MISSING,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        restriction_type=RestrictionType.QUARANTINE,
        restriction_comments=None,
        items=[
            CustomsItemSpec(
                description="Whole black pepper sampler",
                quantity=4,
                value=40.0,
                weight_oz=12.0,
                origin_country="IN",
                hs_tariff_number="090411",  # valid 6-digit
            )
        ],
    ),
)

S4 = SeedShipment(
    id="S4",
    persona="India -> US handicrafts seller",
    note="customs_certify=true with empty signer -> fast structural auto-heal.",
    expected_error=NormalizedErrorType.SIGNER_MISSING,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="",  # missing
        items=[
            CustomsItemSpec(
                description="Hand-block-printed silk scarf",
                quantity=1,
                value=90.0,
                weight_oz=6.0,
                origin_country="IN",
                hs_tariff_number="621440",  # valid 6-digit
            )
        ],
    ),
)

C0 = SeedShipment(
    id="C0",
    persona="India -> US handicrafts seller",
    note="Clean control; should be accepted with no recovery needed.",
    expected_error=None,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        items=[
            CustomsItemSpec(
                description="Hand-block-printed silk scarf",
                quantity=1,
                value=90.0,
                weight_oz=6.0,
                origin_country="IN",
                hs_tariff_number="621440",
            )
        ],
    ),
)

W1 = SeedShipment(
    id="W1",
    persona="India -> US gift sender (live wildcard)",
    note="contents_type=other with no explanation -> unrehearsed generality proof.",
    expected_error=NormalizedErrorType.CONTENTS_EXPLANATION_MISSING,
    payload=CustomsPayload(
        contents_type=ContentsType.OTHER,
        contents_explanation=None,
        customs_certify=True,
        customs_signer="Anaya Sharma",
        items=[
            CustomsItemSpec(
                description="Assorted artisan gift bundle",
                quantity=1,
                value=120.0,
                weight_oz=24.0,
                origin_country="IN",
                hs_tariff_number="460219",  # valid 6-digit (basketwork)
            )
        ],
    ),
)

S5 = SeedShipment(
    id="S5",
    persona="India -> US specialty instrument-maker (novel case)",
    note=(
        "Obscure item the keyword table cannot classify + invalid HS -> the "
        "eval-gate VETO is genuinely earned (no sabotaged classifier)."
    ),
    expected_error=NormalizedErrorType.HS_INVALID,
    payload=CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer="Ravi Menon",
        items=[
            CustomsItemSpec(
                description="Hand-carved rosewood sitar bridge (jawari)",
                quantity=2,
                value=140.0,
                weight_oz=10.0,
                origin_country="IN",
                hs_tariff_number="9999",  # invalid (4 digits) and genuinely novel
            )
        ],
    ),
)

SEEDS: list[SeedShipment] = [S1, S2, S3, S4, S5, C0, W1]
_SEED_INDEX = {s.id: s for s in SEEDS}


def all_seeds() -> list[SeedShipment]:
    return list(SEEDS)


def get_seed(seed_id: str) -> SeedShipment:
    try:
        return _SEED_INDEX[seed_id]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown seed id {seed_id!r}; known: {sorted(_SEED_INDEX)}") from exc
