"""USITC HTS validator: structural gate, offline table, and live lookup.

The live cases use ``respx`` to mock the hts.usitc.gov REST endpoint so the
real-tariff-schedule logic is exercised without touching the network.
"""

from __future__ import annotations

import httpx
import respx

from clearport.agents.classifier import classify_hs
from clearport.schemas import Source
from clearport.validation.hts_client import HtsValidator, validate_hs

_BASE = "https://hts.usitc.gov/reststop"

# A trimmed but realistic slice of what /reststop/search returns for 6109.10.
_SEARCH_6109_10 = [
    {"htsno": "6109.10.00", "description": "Of cotton", "general": "16.5%"},
    {"htsno": "6109.10.00.04", "description": "T-shirts, all white ...", "general": ""},
    {"htsno": "6109.10.00.12", "description": "Men's (338)", "general": ""},
    {"htsno": "9820.11.12", "description": "Unrelated keyword hit", "general": "Free"},
]


def test_structural_reject_short_code() -> None:
    result = validate_hs("1234")
    assert result.valid is False
    assert result.structural_ok is False
    assert result.source is Source.HTS


def test_offline_table_validates_seed_subheadings() -> None:
    for code in ("830249", "621440", "610910", "090411", "460219"):
        result = validate_hs(code)
        assert result.valid is True
        assert result.exists_in_schedule is True
        assert result.checked_live is False
        assert result.description  # official short description attached


def test_offline_unknown_subheading_trusts_structure() -> None:
    # Structurally valid but unknown offline: we never fail closed.
    result = validate_hs("999999")
    assert result.structural_ok is True
    assert result.exists_in_schedule is False
    assert result.valid is True
    assert "structural" in result.note


@respx.mock
def test_live_match_attaches_description_and_duty() -> None:
    respx.get(f"{_BASE}/search").mock(
        return_value=httpx.Response(200, json=_SEARCH_6109_10)
    )
    validator = HtsValidator(base_url=_BASE, backend="live")
    result = validator.validate("610910")
    assert result.checked_live is True
    assert result.exists_in_schedule is True
    assert result.valid is True
    assert result.general_duty == "16.5%"
    assert "cotton" in result.description.lower()


@respx.mock
def test_live_definitive_miss_invalidates_code() -> None:
    # Search returns only unrelated rows -> no 9999.99 subheading exists.
    respx.get(f"{_BASE}/search").mock(
        return_value=httpx.Response(200, json=[{"htsno": "9820.11.12", "description": "x"}])
    )
    validator = HtsValidator(base_url=_BASE, backend="live")
    result = validator.validate("999999")
    assert result.checked_live is True
    assert result.exists_in_schedule is False
    assert result.valid is False


@respx.mock
def test_live_lookup_is_cached_per_subheading() -> None:
    route = respx.get(f"{_BASE}/search").mock(
        return_value=httpx.Response(200, json=_SEARCH_6109_10)
    )
    validator = HtsValidator(base_url=_BASE, backend="live")
    validator.validate("610910")
    validator.validate("6109100012")  # same 6-digit subheading
    assert route.call_count == 1


def test_classifier_attaches_official_description_offline() -> None:
    # Offline keyword path: brass keychain -> 8302.49, enriched from HTS table.
    result = classify_hs("Hand-engraved brass keychain")
    assert result.code == "830249"
    assert result.official_description  # from the offline HTS subheading table
