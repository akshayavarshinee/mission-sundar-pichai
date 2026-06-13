"""Executor — re-submit the corrected declaration and (when gated) buy a label.

The label purchase is the real-money action. It is only ever requested by the
loop when the risk tier returns AUTO, or after a human approves. Offline, the
synthetic surface validates the patched payload and mints a synthetic label so
the loop completes without keys.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from clearport.config import settings
from clearport.schemas import CarrierResult, PatchProposal, RawError, RejectionEvent
from clearport.validation.easypost_client import EasyPostClient, synthetic_validation

logger = structlog.get_logger(__name__)


class ExecutionResult(BaseModel):
    carrier_result: CarrierResult
    label_id: str | None = None
    shipment_id: str | None = None
    rate_usd: float | None = None
    raw_error: RawError | None = None
    bought: bool = False
    # Set when the declaration cleared but no label could be purchased because no
    # enabled carrier services the lane (carrier-coverage gap, not a rejection).
    note: str | None = None


class Executor:
    def __init__(self, client: EasyPostClient | None = None) -> None:
        self._client = client

    def _live(self, rejection: RejectionEvent) -> bool:
        return bool(
            settings.easypost_api_key
            and rejection.from_address
            and rejection.to_address
            and rejection.parcel
        )

    def finalize(
        self, rejection: RejectionEvent, patch: PatchProposal, *, buy: bool, live: bool = True
    ) -> ExecutionResult:
        """Validate the patched payload; optionally buy the cheapest label.

        ``live=False`` forces the offline synthetic surface (used by the dry-run
        benchmark) so an evaluation never touches the live carrier.
        """
        if live and self._live(rejection):
            result = self._finalize_live(rejection, patch, buy=buy)
        else:
            result = self._finalize_offline(patch, buy=buy)
        return self._apply_overlay(patch, result)

    def _apply_overlay(self, patch: PatchProposal, result: ExecutionResult) -> ExecutionResult:
        """Second surface: the destination registry may reject after the carrier."""
        if result.carrier_result is not CarrierResult.ACCEPTED:
            return result
        from clearport.validation.regional_overlay import get_overlay

        overlay = get_overlay().validate(patch.patched_payload)
        if overlay.ok:
            return result
        field = overlay.raw_error.field if overlay.raw_error else None
        logger.info("executor.overlay_rejected", field=field)
        return ExecutionResult(
            carrier_result=CarrierResult.REJECTED,
            shipment_id=result.shipment_id,
            raw_error=overlay.raw_error,
        )

    def _finalize_live(
        self, rejection: RejectionEvent, patch: PatchProposal, *, buy: bool
    ) -> ExecutionResult:
        client = self._client or EasyPostClient()
        vr = client.validate(
            patch.patched_payload,
            rejection.from_address,  # type: ignore[arg-type]
            rejection.to_address,  # type: ignore[arg-type]
            rejection.parcel,  # type: ignore[arg-type]
        )
        if not vr.ok:
            return ExecutionResult(carrier_result=CarrierResult.REJECTED, raw_error=vr.raw_error)
        if not buy:
            return ExecutionResult(
                carrier_result=CarrierResult.ACCEPTED, shipment_id=vr.shipment_id
            )
        label = client.buy_cheapest(vr.shipment_id) if vr.shipment_id else None
        if label and label.ok:
            return ExecutionResult(
                carrier_result=CarrierResult.ACCEPTED,
                shipment_id=label.shipment_id,
                label_id=label.label_id,
                rate_usd=label.rate_usd,
                bought=True,
            )
        if label and label.no_rates:
            # The declaration CLEARED customs (CustomsInfo + Shipment created,
            # compliance + live HS all passed) but no enabled carrier services
            # this lane, so there is no label to buy. That is a carrier-coverage
            # gap of the account, not a customs rejection — keep it ACCEPTED so
            # an AUTO clear resolves and a human approval does not read as
            # "could not clear". A real carrier for the lane buys a label as before.
            origin = rejection.from_address.country if rejection.from_address else "?"
            note = (
                f"Customs cleared. No carrier on this EasyPost account services "
                f"origin {origin} for this lane, so no shipping label was purchased."
            )
            logger.info(
                "executor.cleared_without_label",
                origin=origin,
                shipment_id=vr.shipment_id,
                reason=label.raw_error.message if label.raw_error else None,
            )
            return ExecutionResult(
                carrier_result=CarrierResult.ACCEPTED,
                shipment_id=vr.shipment_id,
                bought=False,
                note=note,
            )
        return ExecutionResult(
            carrier_result=CarrierResult.REJECTED,
            shipment_id=vr.shipment_id,
            raw_error=label.raw_error if label else None,
        )

    def _finalize_offline(self, patch: PatchProposal, *, buy: bool) -> ExecutionResult:
        vr = synthetic_validation(patch.patched_payload)
        if not vr.ok:
            return ExecutionResult(carrier_result=CarrierResult.REJECTED, raw_error=vr.raw_error)
        return ExecutionResult(
            carrier_result=CarrierResult.ACCEPTED,
            shipment_id="shp_synthetic",
            label_id="lbl_synthetic" if buy else None,
            rate_usd=12.50 if buy else None,
            bought=buy,
        )
