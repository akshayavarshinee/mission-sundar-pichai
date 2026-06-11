"""End-to-end 'add shipment' (operator submission) flow.

Exercises the exact path the dashboard's New-shipment form drives:
ShipmentSubmission -> /api/shipments -> service.submit_custom -> recovery loop,
across a clean declaration and each recoverable rule, asserting the response
contract the UI consumes (run_id, status, provenance, eval, risk).
"""

from __future__ import annotations

from clearport.api.main import ShipmentSubmission, submit_shipment
from clearport.schemas import CustomsPayload


def _submission(**overrides) -> ShipmentSubmission:
    payload = {
        "contents_type": "merchandise",
        "customs_certify": True,
        "customs_signer": "Anaya Sharma",
        "restriction_type": "none",
        "eel_pfc": "NOEEI 30.37(a)",
        "items": [
            {
                "description": "Hand-block-printed silk scarf",
                "quantity": 1,
                "value": 90.0,
                "weight_oz": 6.0,
                "origin_country": "IN",
                "hs_tariff_number": "621440",
                "currency": "USD",
            }
        ],
    }
    payload.update(overrides.pop("payload", {}))
    return ShipmentSubmission(payload=CustomsPayload(**payload), **overrides)


def test_clean_shipment_is_accepted_with_no_recovery() -> None:
    res = submit_shipment(_submission())
    assert res["status"] == "ACCEPTED"
    assert "run_id" not in res


def test_missing_signer_recovers_and_returns_full_summary() -> None:
    res = submit_shipment(_submission(payload={"customs_signer": ""}))
    assert "run_id" in res
    assert res["seed_id"] is None  # a real operator submission, not a demo seed
    assert res["error_type"] == "SIGNER_MISSING"
    assert res["rejection_source"] == "compliance"
    assert res["caught_by"] == "ClearPort Compliance Engine"
    # contract the UI reads
    assert "passed" in res["eval"] and "confidence_basis" in res["eval"]
    assert "decision" in res["risk"]
    assert res["declaration"]["customs_signer"]  # signer was filled by the patch


def test_invalid_hs_is_caught_and_routed() -> None:
    res = submit_shipment(
        _submission(payload={"items": [
            {
                "description": "Hand-engraved brass keychain",
                "quantity": 10,
                "value": 80.0,
                "weight_oz": 16.0,
                "origin_country": "IN",
                "hs_tariff_number": "1234",  # invalid
                "currency": "USD",
            }
        ]})
    )
    assert "run_id" in res
    assert res["error_type"] == "HS_INVALID"


def test_over_threshold_eei_escalates_to_human() -> None:
    res = submit_shipment(
        _submission(payload={"items": [
            {
                "description": "Cotton knit t-shirts (lot)",
                "quantity": 80,
                "value": 3200.0,
                "weight_oz": 320.0,
                "origin_country": "IN",
                "hs_tariff_number": "610910",
                "currency": "USD",
            }
        ]})
    )
    assert "run_id" in res
    assert res["error_type"] == "EEI_THRESHOLD_MISMATCH"
    assert res["risk"]["decision"] == "HUMAN"
    assert res["risk"]["hard_line"] is True


def test_custom_lane_and_shipper_are_threaded() -> None:
    res = submit_shipment(
        _submission(origin="CN", dest="US", shipper_name="Lotus Exports",
                    payload={"customs_signer": ""})
    )
    assert res["origin"] == "CN"
    assert res["dest"] == "US"
    assert "Lotus Exports" in res["persona"]
