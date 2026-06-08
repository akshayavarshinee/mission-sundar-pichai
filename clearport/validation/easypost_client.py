"""Live EasyPost (test-mode) customs validation surface.

EasyPost ``CustomsInfo`` / ``CustomsItem`` objects are immutable once created,
so "patching" a declaration means re-creating the CustomsInfo from a corrected
:class:`~clearport.schemas.CustomsPayload`. This client:

* builds CustomsItems + a CustomsInfo (which triggers the real conditional
  validations: signer / explanation / restriction / zero-value);
* optionally builds a Shipment + fetches rates (which surfaces HS / address
  issues);
* buys the cheapest test-mode label (the Executor's real-money action — free in
  test mode, but gated by the eval/risk tier in production).

The ``easypost`` SDK is imported lazily so this module imports cleanly offline.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel

from clearport.config import settings
from clearport.schemas import (
    Address,
    CustomsPayload,
    ParcelSpec,
    RawError,
    Source,
)
from clearport.validation.errors import normalize_error, policy_lint

logger = structlog.get_logger(__name__)


class ValidationResult(BaseModel):
    ok: bool
    source: Source = Source.EASYPOST
    customs_info_id: str | None = None
    shipment_id: str | None = None
    rates_count: int = 0
    raw_error: RawError | None = None


class LabelResult(BaseModel):
    ok: bool
    shipment_id: str | None = None
    label_id: str | None = None
    tracking_code: str | None = None
    rate_usd: float | None = None
    raw_error: RawError | None = None


def _raw_error_from_exception(exc: Exception) -> RawError:
    """Best-effort extraction of EasyPost's structured error fields."""
    message = str(getattr(exc, "message", None) or exc)
    code = getattr(exc, "code", None)
    field = None
    # EasyPost ApiError exposes `.errors` as a list of {field, message}.
    sub_errors = getattr(exc, "errors", None)
    if isinstance(sub_errors, list) and sub_errors:
        first = sub_errors[0]
        if isinstance(first, dict):
            field = first.get("field")
            message = first.get("message") or message
            code = first.get("code") or code
    return RawError(code=str(code) if code is not None else None, message=message, field=field)


class EasyPostClient:
    """Thin wrapper over the EasyPost test-mode API."""

    def __init__(self, api_key: str | None = None, mode: str | None = None) -> None:
        self._api_key = api_key or settings.easypost_api_key
        self._mode = mode or settings.easypost_mode
        self._client = None  # lazily constructed

    # ── lifecycle ────────────────────────────────────────────────────────
    @property
    def client(self):  # noqa: ANN201 — SDK type imported lazily
        if self._client is None:
            if not self._api_key:
                raise RuntimeError(
                    "EASYPOST_API_KEY is not set. Copy .env.example to .env and add "
                    "your EasyPost *test* key."
                )
            from easypost import EasyPostClient as _SDKClient

            self._client = _SDKClient(self._api_key)
        return self._client

    # ── payload → SDK args ───────────────────────────────────────────────
    @staticmethod
    def _customs_item_args(payload: CustomsPayload) -> list[dict]:
        return [
            {
                "description": i.description,
                "quantity": i.quantity,
                "value": i.value,
                "weight": i.weight_oz,
                "hs_tariff_number": i.hs_tariff_number,
                "origin_country": i.origin_country,
                "currency": i.currency,
            }
            for i in payload.items
        ]

    @staticmethod
    def _customs_info_args(payload: CustomsPayload, customs_items: list) -> dict:
        return {
            "contents_type": payload.contents_type.value,
            "contents_explanation": payload.contents_explanation or "",
            "customs_certify": payload.customs_certify,
            "customs_signer": payload.customs_signer or "",
            "restriction_type": payload.restriction_type.value,
            "restriction_comments": payload.restriction_comments or "",
            "eel_pfc": payload.eel_pfc or "",
            "non_delivery_option": payload.non_delivery_option,
            "customs_items": customs_items,
        }

    @staticmethod
    def _address_args(addr: Address) -> dict:
        return addr.model_dump(exclude_none=True)

    @staticmethod
    def _parcel_args(parcel: ParcelSpec) -> dict:
        args: dict = {"weight": parcel.weight_oz}
        if parcel.length_in:
            args["length"] = parcel.length_in
        if parcel.width_in:
            args["width"] = parcel.width_in
        if parcel.height_in:
            args["height"] = parcel.height_in
        return args

    # ── operations ───────────────────────────────────────────────────────
    def create_customs_info(self, payload: CustomsPayload):  # noqa: ANN201
        """Create a CustomsInfo; raises the SDK error on validation failure."""
        items = [self.client.customs_item.create(**a) for a in self._customs_item_args(payload)]
        return self.client.customs_info.create(**self._customs_info_args(payload, items))

    def validate(
        self,
        payload: CustomsPayload,
        from_address: Address,
        to_address: Address,
        parcel: ParcelSpec,
    ) -> ValidationResult:
        """Attempt CustomsInfo + Shipment creation; capture the first real error."""
        try:
            customs_info = self.create_customs_info(payload)
        except Exception as exc:  # noqa: BLE001 — surface as structured error
            logger.info("easypost.customs_info.rejected", error=str(exc))
            return ValidationResult(ok=False, raw_error=_raw_error_from_exception(exc))

        try:
            shipment = self.client.shipment.create(
                from_address=self._address_args(from_address),
                to_address=self._address_args(to_address),
                parcel=self._parcel_args(parcel),
                customs_info={"id": customs_info.id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("easypost.shipment.rejected", error=str(exc))
            return ValidationResult(
                ok=False,
                customs_info_id=customs_info.id,
                raw_error=_raw_error_from_exception(exc),
            )

        rates = getattr(shipment, "rates", []) or []
        return ValidationResult(
            ok=True,
            customs_info_id=customs_info.id,
            shipment_id=shipment.id,
            rates_count=len(rates),
        )

    def buy_cheapest(self, shipment_id: str) -> LabelResult:
        """Buy the lowest test-mode rate (the gated real-money action)."""
        try:
            shipment = self.client.shipment.retrieve(shipment_id)
            bought = self.client.shipment.buy(
                shipment.id, rate=shipment.lowest_rate()
            )
        except Exception as exc:  # noqa: BLE001
            return LabelResult(ok=False, shipment_id=shipment_id, raw_error=_raw_error_from_exception(exc))

        label = getattr(bought, "postage_label", None)
        selected = getattr(bought, "selected_rate", None)
        return LabelResult(
            ok=True,
            shipment_id=bought.id,
            label_id=getattr(label, "id", None),
            tracking_code=getattr(bought, "tracking_code", None),
            rate_usd=float(getattr(selected, "rate", 0.0) or 0.0),
        )


def synthetic_validation(payload: CustomsPayload) -> ValidationResult:
    """Offline equivalent of :meth:`EasyPostClient.validate`.

    Runs ClearPort's policy lint (the same real rules) without a network call,
    so the loop, tests, and demos work even before an API key is configured.
    The result is clearly marked ``source=EASYPOST`` semantics but produced
    locally; the live client is used whenever a key is present.
    """
    violation = policy_lint(payload)
    if violation is None:
        return ValidationResult(ok=True, customs_info_id="ci_synthetic_ok")
    raw = RawError(
        code=violation.value,
        message=f"[synthetic] declaration violates rule {violation.value}",
        field=None,
    )
    # round-trip through normalize_error to mirror the live path exactly
    _ = normalize_error(raw, payload)
    return ValidationResult(ok=False, raw_error=raw)
