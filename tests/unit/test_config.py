"""Phase 0 unit tests: configuration loads and derives correctly."""

from __future__ import annotations

import pytest

from clearport.config import RuntimeEnv, Settings


def test_settings_default_local() -> None:
    s = Settings()
    assert s.clearport_env is RuntimeEnv.LOCAL
    assert s.is_cloud is False


def test_collector_endpoint_defaults_to_host() -> None:
    s = Settings(phoenix_collector_endpoint=None, phoenix_host="http://localhost:6006")
    assert s.collector_endpoint == "http://localhost:6006"


def test_collector_endpoint_override() -> None:
    s = Settings(phoenix_collector_endpoint="http://collector:4317")
    assert s.collector_endpoint == "http://collector:4317"


def test_require_raises_on_missing() -> None:
    s = Settings(easypost_api_key=None)
    with pytest.raises(RuntimeError) as exc:
        s.require("easypost_api_key")
    assert "easypost_api_key" in str(exc.value)


def test_require_passes_when_present() -> None:
    s = Settings(easypost_api_key="EZTK_test_dummy")
    s.require("easypost_api_key")  # should not raise


def test_hard_line_default_is_2500() -> None:
    assert Settings().clearport_hard_line_usd == 2500.0
