"""Settings validators (BUILD_PLAN 4.2 fail-fast rules) — constructed directly, no app."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ConfigError


def test_settings_fail_fast_without_key_in_live_mode() -> None:
    """Live mode (fixtures off) with an empty key must be refused at construction."""
    with pytest.raises(ValidationError, match="SERPAPI_API_KEY"):
        Settings(serpapi_use_fixtures=False, serpapi_api_key="")


def test_settings_fixture_mode_needs_no_key() -> None:
    """Fixture mode is the default development path and must work keyless."""
    settings = Settings(serpapi_use_fixtures=True, serpapi_api_key="")

    assert settings.serpapi_use_fixtures is True


def test_settings_reject_non_positive_call_cap() -> None:
    """The daily call cap must be a positive integer (guard against 0/negative)."""
    with pytest.raises(ValidationError):
        Settings(serpapi_daily_call_cap=0)


def test_settings_require_gemini_raises_without_credentials() -> None:
    """Gemini checks happen at invocation time, not at startup (app must boot keyless)."""
    settings = Settings(gemini_api_key="", gemini_model="")

    with pytest.raises(ConfigError, match="GEMINI"):
        settings.require_gemini()


def test_settings_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fields are populated from the environment (Settings is the only reader)."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.log_level == "DEBUG"


def test_settings_parses_cors_origins_into_list() -> None:
    """cors_origins is stored as the raw env string and exposed as a clean list."""
    settings = Settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")

    assert settings.cors_origins_list == ["http://localhost:5173", "http://127.0.0.1:5173"]
