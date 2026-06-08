"""Regional Rule Overlay — the second, *controllable* validation surface.

Real cross-border flows are validated twice: by the carrier (EasyPost, real and
fixed) and by the destination registry / single-window (jurisdiction rules that
change silently). EasyPost gives us authentic carrier rejections; this overlay is
a small versioned rule engine we own, so we can simulate a *silent schema change*
and demonstrate drift detection — without ever faking an EasyPost error.

Default state is inactive (no effect on the carrier-driven seeds). Flipping it on
bumps the registry version and enforces a new required field.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from clearport.schemas import (
    NormalizedErrorType,
    RawError,
    RejectionEvent,
    Source,
)

logger = structlog.get_logger(__name__)


class OverlayRule(BaseModel):
    id: str
    version: int
    description: str
    requires_field: str


class OverlayResult(BaseModel):
    ok: bool
    version: int
    raw_error: RawError | None = None


class RegionalRuleOverlay:
    """A destination registry that can silently change a rule."""

    def __init__(self) -> None:
        self.active = False
        self.version = 1
        self.rule = OverlayRule(
            id="dest-us-contents-explanation",
            version=2,
            description=(
                "Destination registry now requires a non-empty contents_explanation "
                "on all inbound declarations."
            ),
            requires_field="contents_explanation",
        )

    def flip(self, active: bool = True) -> None:
        self.active = active
        self.version = self.rule.version if active else 1
        logger.info("overlay.flip", active=active, version=self.version)

    def validate(self, payload) -> OverlayResult:  # noqa: ANN001 — CustomsPayload
        if self.active and not (getattr(payload, "contents_explanation", None) or "").strip():
            return OverlayResult(
                ok=False,
                version=self.version,
                raw_error=RawError(
                    code="OVERLAY_SCHEMA_DRIFT",
                    message=(
                        f"Destination registry v{self.version} requires "
                        f"'{self.rule.requires_field}'."
                    ),
                    field=self.rule.requires_field,
                ),
            )
        return OverlayResult(ok=True, version=self.version)

    def make_rejection(self, seed) -> RejectionEvent | None:  # noqa: ANN001 — SeedShipment
        """Produce an OVERLAY-sourced rejection if the active rule is violated."""
        result = self.validate(seed.payload)
        if result.ok or result.raw_error is None:
            return None
        return RejectionEvent(
            source=Source.OVERLAY,
            lane=seed.lane,
            persona=seed.persona,
            payload=seed.payload.model_copy(deep=True),
            raw_error=result.raw_error,
            normalized_error_type=NormalizedErrorType.OVERLAY_SCHEMA_DRIFT,
            seed_id=seed.id,
            shipper_name=seed.from_address.name,
            from_address=seed.from_address,
            to_address=seed.to_address,
            parcel=seed.parcel,
        )


_OVERLAY: RegionalRuleOverlay | None = None


def get_overlay() -> RegionalRuleOverlay:
    global _OVERLAY
    if _OVERLAY is None:
        _OVERLAY = RegionalRuleOverlay()
    return _OVERLAY


def reset_overlay() -> None:
    """Test helper: restore the inactive default."""
    global _OVERLAY
    _OVERLAY = None
