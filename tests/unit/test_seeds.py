"""Phase 1 unit tests: seed shipments trip exactly their expected real rule."""

from __future__ import annotations

import pytest

from clearport.schemas import NormalizedErrorType
from clearport.seeds.shipments import SEEDS, all_seeds, get_seed
from clearport.validation.errors import policy_lint
from clearport.validation.harness import run_seed


@pytest.mark.parametrize("seed", SEEDS, ids=[s.id for s in SEEDS])
def test_seed_trips_expected_rule(seed) -> None:
    assert policy_lint(seed.payload) is seed.expected_error


def test_control_is_clean() -> None:
    assert get_seed("C0").expected_error is None
    assert policy_lint(get_seed("C0").payload) is None


def test_all_seeds_have_unique_ids() -> None:
    ids = [s.id for s in all_seeds()]
    assert len(ids) == len(set(ids))


def test_run_seed_emits_event_for_failures() -> None:
    # Offline (no key) -> synthetic validation drives the harness.
    for seed in SEEDS:
        event = run_seed(seed)
        if seed.expected_error is None:
            assert event is None
        else:
            assert event is not None
            assert event.normalized_error_type is seed.expected_error
            assert event.seed_id == seed.id
            assert event.customs_value == seed.payload.total_value


def test_memory_key_shape() -> None:
    event = run_seed(get_seed("S1"))
    assert event is not None
    key = event.memory_key
    assert key.error_type is NormalizedErrorType.HS_INVALID
    assert str(event.lane) == "IN->US"
    assert key.as_str().startswith("IN->US|hs")
