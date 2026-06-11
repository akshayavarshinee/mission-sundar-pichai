"""The eval-gate's safety invariant: a recovery may correct a declaration but
must never *weaken* it.

These cases hand-build a patch that games the policy lint by understating the
declared value (to duck the $2,500 EEI threshold) or by stripping certification,
and assert the gate fails them anyway — independent of the model, offline.
"""

from __future__ import annotations

from clearport.eval.judge import Judge
from clearport.schemas import (
    ContentsType,
    CustomsItemSpec,
    CustomsPayload,
    FieldDiff,
    Lane,
    NormalizedErrorType,
    PatchProposal,
    RawError,
    RejectionEvent,
    Source,
)


def _item(value: float, hs: str = "610910") -> CustomsItemSpec:
    return CustomsItemSpec(
        description="Cotton knit t-shirts (lot)",
        quantity=40,
        value=value,
        weight_oz=200.0,
        origin_country="IN",
        hs_tariff_number=hs,
    )


def _payload(value: float, *, certify: bool = True, signer: str | None = "Anaya Sharma") -> CustomsPayload:
    return CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=certify,
        customs_signer=signer,
        eel_pfc="AES ITN PENDING (EEI filing required)",
        items=[_item(value)],
    )


def _rejection(value: float) -> RejectionEvent:
    return RejectionEvent(
        source=Source.COMPLIANCE,
        lane=Lane(origin="IN", dest="US"),
        persona="test",
        payload=_payload(value),
        raw_error=RawError(code="EEI_THRESHOLD_MISMATCH", message="over threshold"),
        normalized_error_type=NormalizedErrorType.EEI_THRESHOLD_MISMATCH,
    )


def _patch(rejection: RejectionEvent, patched: CustomsPayload, diff_field: str) -> PatchProposal:
    return PatchProposal(
        rejection_id=rejection.id,
        patched_payload=patched,
        field_diff=[FieldDiff(field=diff_field, before="x", after="y")],
        rationale="test patch",
    )


def test_value_understatement_fails_the_gate() -> None:
    # Original $3,200; a patch that quietly drops it to $100 would slip under the
    # $2,500 EEI threshold — the gate must reject it even though $100 lints clean.
    rejection = _rejection(3200.0)
    patched = _payload(100.0)
    verdict = Judge().evaluate(rejection, _patch(rejection, patched, "items[0].value"))
    assert verdict.passed is False
    assert verdict.rubric.value_sanity is False
    assert "understate" in verdict.rationale.lower() or "value dropped" in verdict.rationale.lower()


def test_certification_removal_fails_the_gate() -> None:
    # Stripping certification makes the signer requirement vanish from the lint,
    # but it weakens the declaration — the gate must reject it.
    rejection = _rejection(900.0)
    patched = _payload(900.0, certify=False, signer=None)
    verdict = Judge().evaluate(rejection, _patch(rejection, patched, "customs_certify"))
    assert verdict.passed is False
    assert "certification" in verdict.rationale.lower()


def test_legitimate_fix_passes_safety() -> None:
    # A normal fix that preserves value and certification is unaffected by the
    # safety invariant and passes the deterministic gate.
    rejection = _rejection(900.0)
    patched = _payload(900.0)
    verdict = Judge().evaluate(rejection, _patch(rejection, patched, "eel_pfc"))
    assert verdict.passed is True
    assert verdict.rubric.value_sanity is True
