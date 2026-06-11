"""USITC HTS schedule validation — real tariff lookup.

The Harmonized Tariff Schedule of the United States is published by the U.S.
International Trade Commission with a public REST endpoint at
``https://hts.usitc.gov/reststop``. ClearPort uses it to verify that a declared
or freshly-classified HS code is a *real* line in the current schedule — a
strictly stronger check than the 6/10-digit structural test in
:mod:`clearport.validation.errors`.

Design goals:

* **Real provenance.** Live lookups go through the ``/reststop/search``
  endpoint (httpx + tenacity) and carry ``source=Source.HTS``; a match returns
  the official description and Column-1 general duty rate.
* **Fast + polite.** Results are cached per 6-digit subheading for the process
  lifetime, so the live API is hit at most once per subheading.
* **Safe degradation.** A small bundled table of known subheadings (the demo
  lane + common consumer goods) lets the validator answer offline and keeps
  tests/CI network-free. If the network is unavailable and a code is unknown
  offline, the structural check stands rather than emitting a false rejection.
"""

from __future__ import annotations

from functools import lru_cache

import httpx
import structlog
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from clearport.config import settings
from clearport.schemas import Source
from clearport.validation.errors import hs_is_valid

logger = structlog.get_logger(__name__)


# Known-good 6-digit subheadings → official short description. Covers every seed
# in the demo lane plus a spread of common consumer goods, so the offline path
# answers truthfully for the scenarios we ship without a network round-trip.
_OFFLINE_SUBHEADINGS: dict[str, str] = {
    "830249": "Base metal mountings, fittings and similar articles (incl. key rings)",
    "621440": "Shawls, scarves, mufflers and the like, of artificial fibres",
    "621410": "Shawls, scarves, mufflers and the like, of silk or silk waste",
    "610910": "T-shirts, singlets and other vests, knitted, of cotton",
    "090411": "Pepper of the genus Piper, neither crushed nor ground",
    "460219": "Basketwork and other articles of other (vegetable) plaiting materials",
    "851712": "Telephones for cellular networks or other wireless networks",
    "940360": "Other wooden furniture",
    "711790": "Imitation jewelry, other",
    "420221": "Handbags with outer surface of leather or composition leather",
    "691200": "Ceramic tableware and kitchenware, other than porcelain or china",
    "920992": "Parts and accessories for the string musical instruments of heading 9202",
}


class HtsLookup(BaseModel):
    """Outcome of validating one HS number against the HTS schedule."""

    code: str
    valid: bool
    structural_ok: bool
    exists_in_schedule: bool
    checked_live: bool = False
    source: Source = Source.HTS
    description: str = ""
    general_duty: str = ""
    note: str = ""


def _digits(value: str | None) -> str:
    return "".join(c for c in (value or "") if c.isdigit())


def _dotted_subheading(digits6: str) -> str:
    """``610910`` → ``6109.10`` (the form the search endpoint expects)."""
    return f"{digits6[:4]}.{digits6[4:6]}" if len(digits6) >= 6 else digits6


def _match_rows(rows: list[dict], digits: str) -> tuple[bool, str, str]:
    """Return (exists, description, general_duty) for ``digits`` over search rows.

    A subheading is considered present if any returned ``htsno`` shares the same
    6-digit prefix. Among the rows that line up with the queried code (it is a
    prefix of theirs, or vice-versa), the one whose specificity is closest to
    the query supplies the description; the Column-1 duty is inherited from the
    nearest tariff line that actually carries a rate (10-digit statistical
    breakouts usually leave it blank).
    """
    sub6 = digits[:6]
    exists = False
    aligned: list[tuple[str, str, str]] = []
    for row in rows:
        rdigits = _digits(str(row.get("htsno") or ""))
        if not rdigits or rdigits[:6] != sub6:
            continue
        exists = True
        if digits.startswith(rdigits) or rdigits.startswith(digits):
            aligned.append(
                (
                    rdigits,
                    str(row.get("description") or "").strip(),
                    str(row.get("general") or "").strip(),
                )
            )
    if not aligned:
        return exists, "", ""

    target = len(digits)
    primary = min(aligned, key=lambda r: (abs(len(r[0]) - target), len(r[0])))
    description, duty = primary[1], primary[2]
    if not duty:
        with_duty = [r for r in aligned if r[2]]
        if with_duty:
            duty = min(with_duty, key=lambda r: (abs(len(r[0]) - target), len(r[0])))[2]
    return exists, description, duty


class HtsValidator:
    """Validates HS numbers against the live USITC HTS schedule (with cache)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        backend: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.clearport_hts_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.clearport_hts_timeout
        # "auto" → try live then fall back; "live" → live only; "off" → offline only.
        self._backend = (backend or settings.clearport_hts_backend).lower()
        self._cache: dict[str, list[dict] | None] = {}

    # ── live access ──────────────────────────────────────────────────────
    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_fixed(0.4),
        retry=retry_if_exception_type(httpx.TransportError),
    )
    def _search(self, dotted: str) -> list[dict]:
        resp = httpx.get(
            f"{self._base_url}/search",
            params={"keyword": dotted},
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            data = data.get("results", [])
        return [row for row in data if isinstance(row, dict)]

    def _live_rows(self, digits6: str) -> list[dict] | None:
        if digits6 in self._cache:
            return self._cache[digits6]
        try:
            rows = self._search(_dotted_subheading(digits6))
        except Exception as exc:  # noqa: BLE001 — degrade to offline on any failure
            logger.info("hts.live_unavailable", subheading=digits6, error=str(exc))
            self._cache[digits6] = None
            return None
        self._cache[digits6] = rows
        logger.debug("hts.live_lookup", subheading=digits6, rows=len(rows))
        return rows

    # ── public API ───────────────────────────────────────────────────────
    def validate(self, hs_tariff_number: str | None) -> HtsLookup:
        digits = _digits(hs_tariff_number)
        structural = hs_is_valid(hs_tariff_number)
        code = hs_tariff_number or ""
        if not structural:
            return HtsLookup(
                code=code,
                valid=False,
                structural_ok=False,
                exists_in_schedule=False,
                note="not a 6- or 10-digit HTS number",
            )

        digits6 = digits[:6]

        if self._backend != "off":
            rows = self._live_rows(digits6)
            if rows is not None:
                exists, desc, duty = _match_rows(rows, digits)
                return HtsLookup(
                    code=code,
                    valid=exists,
                    structural_ok=True,
                    exists_in_schedule=exists,
                    checked_live=True,
                    description=desc,
                    general_duty=duty,
                    note="" if exists else "no matching subheading in the live HTS schedule",
                )
            if self._backend == "live":
                # Live-only and the API was unreachable: trust structure, flag it.
                return HtsLookup(
                    code=code,
                    valid=True,
                    structural_ok=True,
                    exists_in_schedule=False,
                    checked_live=False,
                    note="live HTS lookup unavailable; structural check only",
                )

        # Offline path (backend == "off", or "auto" with the API unreachable).
        offline_desc = _OFFLINE_SUBHEADINGS.get(digits6)
        if offline_desc is not None:
            return HtsLookup(
                code=code,
                valid=True,
                structural_ok=True,
                exists_in_schedule=True,
                checked_live=False,
                description=offline_desc,
                note="offline HTS table",
            )
        return HtsLookup(
            code=code,
            valid=True,
            structural_ok=True,
            exists_in_schedule=False,
            checked_live=False,
            note="offline; structural check only (subheading not in local table)",
        )


@lru_cache(maxsize=1)
def get_hts_validator() -> HtsValidator:
    """Process-wide cached validator (so the subheading cache is shared)."""
    return HtsValidator()


def validate_hs(hs_tariff_number: str | None) -> HtsLookup:
    """Convenience wrapper over the cached validator."""
    return get_hts_validator().validate(hs_tariff_number)
