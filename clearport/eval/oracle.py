"""Independent ground-truth oracle — what the *destination* actually accepts.

The eval-gate (``Judge``) decides whether to auto-clear a patched declaration.
This module answers a deliberately different question: *would the destination
gateway actually accept it once resubmitted?* That answer is **ground truth**,
and it is sourced independently of the gate's own ``policy_lint`` — which is the
whole point. If the oracle reused ``policy_lint`` we would be grading the gate
with the gate, and every "false-auto-clear ≈ 0" number would be a tautology.

Independence comes from modelling the **destination registry / single-window**,
which enforces rules the carrier does not:

* an **accepted-tariff-line allow-list** — a code can be syntactically valid (it
  passes the carrier's ``hs_is_valid``) yet not be on the destination's accepted
  lines (the silent-rule surface);
* a **legal-signer** rule — the certifier must be a plausible full name, not a stub;
* an **undervaluation** guard — implausibly low unit values are rejected.

These are the rejections a cold judge cannot see coming and a *learned* judge
must come to anticipate from experience — so the oracle is also what every
:class:`~clearport.schemas.Adjudication` is labelled by.

Live, the oracle prefers a real signal: a carrier resubmission result (EasyPost
test mode) and/or an independent "destination customs officer" LLM with its own
persona (never the gate's prompt). Offline, the deterministic destination
registry stands in so the measurement is reproducible with no keys.
"""

from __future__ import annotations

import structlog

from clearport import llm
from clearport.config import settings
from clearport.schemas import (
    Adjudication,
    CustomsPayload,
    Lane,
    NormalizedErrorType,
    OracleSource,
    RejectionEvent,
)
from clearport.validation.errors import hs_is_valid

logger = structlog.get_logger(__name__)


# ── the destination registry (the rules the carrier does NOT enforce) ─────────
# 4-digit HTS headings the destination's single-window currently accepts inbound.
# A syntactically-valid code outside this set is carrier-clean but destination-
# rejected — the silent-rule surface a learned judge must anticipate. This models
# a *published-but-changing* destination policy, not the carrier's HS syntax check.
DEST_ACCEPTED_HEADINGS: frozenset[str] = frozenset(
    {
        "8302",  # base-metal mountings/fittings (brass keychain etc.)
        "6214",  # shawls/scarves
        "6109",  # t-shirts/singlets
        "0904",  # pepper
        "4602",  # basketwork
        "6911",  # porcelain tableware
        "4421",  # other articles of wood
        "5701",  # carpets (knotted)
    }
)

# Below this per-unit declared value the destination treats the line as
# implausibly undervalued (distinct from the carrier's mere value > 0 check).
DEST_MIN_UNIT_VALUE_USD = 3.0


def _heading(hs: str | None) -> str | None:
    if not hs:
        return None
    digits = "".join(c for c in hs if c.isdigit())
    return digits[:4] if len(digits) >= 4 else None


def _full_name(name: str | None) -> bool:
    """A plausible legal signer: at least two alphabetic tokens."""
    tokens = [t for t in (name or "").split() if any(c.isalpha() for c in t)]
    return len(tokens) >= 2


def destination_registry_check(
    payload: CustomsPayload, lane: Lane | None = None
) -> tuple[bool, str]:
    """Return ``(accepted, detail)`` from the destination registry alone.

    Deliberately disjoint from :func:`policy_lint`: it assumes the carrier has
    already accepted the declaration and asks only what the *destination* adds.
    """
    dest = (lane.dest if lane else "US").upper()
    if dest != "US":
        # We only model the US destination single-window; others accept by default.
        return True, f"No destination registry modelled for {dest}; accepted."

    for item in payload.items:
        heading = _heading(item.hs_tariff_number)
        if hs_is_valid(item.hs_tariff_number) and heading not in DEST_ACCEPTED_HEADINGS:
            return (
                False,
                f"Destination registry does not accept tariff heading {heading} "
                f"for '{item.description}' (line not on the approved inbound schedule).",
            )

    if payload.customs_certify and not _full_name(payload.customs_signer):
        return (
            False,
            "Destination registry requires the certifying signer to be a full "
            f"legal name; got {payload.customs_signer!r}.",
        )

    for item in payload.items:
        unit = item.value / item.quantity if item.quantity else item.value
        if unit < DEST_MIN_UNIT_VALUE_USD:
            return (
                False,
                f"Destination registry flags '{item.description}' as undervalued "
                f"(unit value ${unit:.2f} below ${DEST_MIN_UNIT_VALUE_USD:.0f} floor).",
            )

    return True, "Destination registry accepts the declaration."


def features_of(payload: CustomsPayload, error_type: NormalizedErrorType) -> str:
    """A compact, structured retrieval key for a declaration.

    Shared by the oracle (what it labelled), the adjudication store (what it
    embeds), and the learned judge (what it retrieves on), so the same case maps
    to the same key everywhere. The representation surfaces *raw* tariff-line
    attributes at several granularities — full HS code, 4-digit heading, 2-digit
    chapter — rather than burying them in free text. That is plain feature
    engineering (no oracle rule is encoded here): it lets similarity see the
    tariff line a destination rule turns on, and lets experience on one code
    generalise to other codes under the same rejected heading.
    """
    parts = [f"error={error_type.value}"]
    for item in payload.items:
        digits = "".join(c for c in (item.hs_tariff_number or "") if c.isdigit())
        heading = digits[:4] if len(digits) >= 4 else digits or "none"
        chapter = digits[:2] if len(digits) >= 2 else digits or "none"
        unit = (item.value / item.quantity) if item.quantity else item.value
        # Heading/chapter repeated so the tariff line carries weight against the
        # free-text description tokens in a bag-of-tokens embedding.
        parts.append(
            f"hs={item.hs_tariff_number} heading={heading} heading={heading} "
            f"chapter={chapter} desc={item.description} unit_value={unit:.2f}"
        )
    signer = (payload.customs_signer or "").replace(" ", "_") or "none"
    parts.append(
        f"signer={signer} contents={payload.contents_type.value} "
        f"total={payload.total_value:.2f} restriction={payload.restriction_type.value}"
    )
    return " ".join(parts)


class IndependentOracle:
    """Adjudicates the true destination outcome of a (patched) declaration."""

    def adjudicate(
        self,
        payload: CustomsPayload,
        *,
        lane: Lane | None = None,
        error_type: NormalizedErrorType = NormalizedErrorType.UNKNOWN,
        memory_key: str = "",
    ) -> Adjudication:
        accepted, detail = destination_registry_check(payload, lane)
        source = OracleSource.DESTINATION_REGISTRY
        confidence = 1.0

        # Live enrichment: an independent "destination customs officer" LLM with
        # its own persona may add a verdict. It can only make the oracle *stricter*
        # (reject what the registry passed) — modelling a human destination officer
        # catching something the published rules missed — and never auto-approves
        # a registry rejection, so the deterministic floor always holds.
        if accepted and self._officer_enabled():
            try:
                officer_ok, officer_detail = self._destination_officer(payload, lane)
                if not officer_ok:
                    accepted = False
                    detail = officer_detail or detail
                    source = OracleSource.DESTINATION_OFFICER
                    confidence = 0.9
            except llm.LLMUnavailable:
                pass
            except Exception as exc:  # noqa: BLE001 — never let the oracle break a run
                logger.warning("oracle.officer_failed", error=str(exc))

        return Adjudication(
            memory_key=memory_key,
            error_type=error_type,
            accepted=accepted,
            source=source,
            detail=detail,
            confidence=confidence,
            features=features_of(payload, error_type),
        )

    def adjudicate_outcome(
        self, rejection: RejectionEvent, patched: CustomsPayload, *, carrier_accepted: bool
    ) -> Adjudication:
        """Adjudicate a completed loop outcome.

        ``carrier_accepted`` is the observed carrier result (EasyPost test mode or
        the offline carrier lint). The destination registry is then layered on top
        — both surfaces must accept for the resubmission to truly clear.
        """
        if not carrier_accepted:
            return Adjudication(
                memory_key=rejection.memory_key.as_str(),
                error_type=rejection.normalized_error_type,
                accepted=False,
                source=OracleSource.CARRIER_RESUBMIT,
                detail="Carrier rejected the resubmission.",
                features=features_of(patched, rejection.normalized_error_type),
            )
        return self.adjudicate(
            patched,
            lane=rejection.lane,
            error_type=rejection.normalized_error_type,
            memory_key=rejection.memory_key.as_str(),
        )

    # ── live destination officer (independent persona) ───────────────────
    @staticmethod
    def _officer_enabled() -> bool:
        return settings.oracle_officer_enabled and llm.is_live()

    @staticmethod
    def _destination_officer(
        payload: CustomsPayload, lane: Lane | None
    ) -> tuple[bool, str]:
        """Ask an independent LLM destination officer to adjudicate.

        Uses the tier-④ ``oracle`` prompt (a destination-officer persona distinct
        from the gate judge) so this signal never collapses into the gate's logic.
        Returns ``(accepted, detail)``; raises ``LLMUnavailable`` when offline.
        """
        from clearport.memory.prompts import get_prompt

        items = "\n".join(
            f"- {i.description}: HTS {i.hs_tariff_number}, qty {i.quantity}, "
            f"value ${i.value:.2f}, origin {i.origin_country}"
            for i in payload.items
        )
        user = (
            f"Destination: {(lane.dest if lane else 'US')}\n"
            f"Declared total value: ${payload.total_value:.2f}\n"
            f"Certifying signer: {payload.customs_signer!r}\n"
            f"Contents type: {payload.contents_type.value}\n"
            f"Line items:\n{items}\n\n"
            "Decide whether your destination single-window would ACCEPT this "
            "inbound declaration. Respond ONLY as JSON: "
            '{"accepted": true|false, "reason": "..."}.'
        )
        data = llm.generate_json(get_prompt("oracle"), user, temperature=0.0)
        accepted = bool(data.get("accepted", True))
        reason = str(data.get("reason", "")).strip()
        return accepted, reason or "Destination officer adjudication."


_ORACLE: IndependentOracle | None = None


def get_oracle() -> IndependentOracle:
    global _ORACLE
    if _ORACLE is None:
        _ORACLE = IndependentOracle()
    return _ORACLE
