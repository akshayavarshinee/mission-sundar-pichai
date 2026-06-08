"""Rejection harness: seed -> validation surface -> normalized RejectionEvent.

Uses the live EasyPost client when a key is configured, otherwise falls back to
the offline synthetic validation (same real rules) so the loop runs anywhere.
A clean shipment returns ``None`` (nothing to recover).
"""

from __future__ import annotations

import structlog

from clearport.config import settings
from clearport.schemas import RejectionEvent, Source
from clearport.seeds.shipments import SeedShipment
from clearport.validation.easypost_client import (
    EasyPostClient,
    ValidationResult,
    synthetic_validation,
)
from clearport.validation.errors import normalize_error

logger = structlog.get_logger(__name__)


def validate_seed(seed: SeedShipment, client: EasyPostClient | None = None) -> ValidationResult:
    """Validate a seed against EasyPost (if a key exists) or synthetically."""
    if settings.easypost_api_key:
        client = client or EasyPostClient()
        return client.validate(seed.payload, seed.from_address, seed.to_address, seed.parcel)
    logger.debug("harness.synthetic", seed=seed.id, reason="no EASYPOST_API_KEY")
    return synthetic_validation(seed.payload)


def to_rejection_event(seed: SeedShipment, result: ValidationResult) -> RejectionEvent | None:
    """Build a normalized RejectionEvent from a failed validation result."""
    if result.ok or result.raw_error is None:
        return None
    error_type = normalize_error(result.raw_error, seed.payload, source=result.source)
    return RejectionEvent(
        source=result.source,
        lane=seed.lane,
        persona=seed.persona,
        payload=seed.payload.model_copy_deep(),
        raw_error=result.raw_error,
        normalized_error_type=error_type,
        seed_id=seed.id,
        shipper_name=seed.from_address.name,
        from_address=seed.from_address,
        to_address=seed.to_address,
        parcel=seed.parcel,
    )


def run_seed(seed: SeedShipment, client: EasyPostClient | None = None) -> RejectionEvent | None:
    """Validate a seed and emit a RejectionEvent (or ``None`` if accepted)."""
    result = validate_seed(seed, client=client)
    event = to_rejection_event(seed, result)
    if event is not None:
        logger.info(
            "harness.rejection",
            seed=seed.id,
            error_type=event.normalized_error_type.value,
            value=event.customs_value,
            source=event.source.value if isinstance(event.source, Source) else event.source,
        )
    else:
        logger.info("harness.accepted", seed=seed.id)
    return event
