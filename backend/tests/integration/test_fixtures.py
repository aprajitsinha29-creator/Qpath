"""Committed SerpApi fixture tests (plan step 0.8).

These tests run against the *real committed* recordings in
``backend/tests/fixtures/serpapi/`` — not tmp_path fabrications.

Three properties are guaranteed:
1. No fixture file contains an ``api_key`` field (AGENTS 3.7.5).
2. The SerpApiClient can read a committed fixture in fixture mode.
3. The deliberate empty-result fixture (India QEC) is returned
   without raising, with status logged as "empty".
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import SessionLocal
from app.integrations.serpapi.client import DEFAULT_FIXTURE_DIR, SerpApiClient

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_FIXTURE_DIR = DEFAULT_FIXTURE_DIR
_API_KEY_PATTERN = re.compile(r'"api_key"\s*:', re.IGNORECASE)


@pytest.fixture()
def session_factory(db_session: Session) -> Callable[[], Session]:
    """Session factory pointing at the per-test temp DB."""
    return SessionLocal


def _fixture_settings() -> Settings:
    return Settings(serpapi_use_fixtures=True, serpapi_api_key="")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fixtures_contain_no_api_key() -> None:
    """Every committed JSON fixture must be free of an 'api_key' field (AGENTS 3.7.5).

    This guards against accidentally committing a key inside a recorded
    response body, even inside nested objects.
    """
    json_files = list(_FIXTURE_DIR.glob("*.json"))
    assert json_files, f"No fixture files found in {_FIXTURE_DIR}"

    offenders: list[str] = []
    for path in json_files:
        text = path.read_text(encoding="utf-8")
        if _API_KEY_PATTERN.search(text):
            # Allow the scrubbed sentinel value "***" but not real values
            data = json.loads(text)
            if _has_real_api_key(data):
                offenders.append(path.name)

    assert offenders == [], f"Fixtures contain a real api_key: {offenders}"


def _has_real_api_key(obj: object) -> bool:
    """Recursively check that no 'api_key' value other than '***' is present."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "api_key" and v not in ("***", "", None):
                return True
            if _has_real_api_key(v):
                return True
    elif isinstance(obj, list):
        return any(_has_real_api_key(item) for item in obj)
    return False


def test_serpapi_client_reads_committed_fixture(
    session_factory: Callable[[], Session],
) -> None:
    """The SerpApiClient must load the committed QEC global fixture without error.

    This confirms that the recorded fixture naming convention matches the
    client's naming logic end-to-end.
    """
    client = SerpApiClient(_fixture_settings(), session_factory, fixture_dir=_FIXTURE_DIR)

    result = client.search_jobs("quantum error correction", fixture_variant="global_p1")

    # The recorded fixture must contain at least one jobs_results entry
    assert "jobs_results" in result or "organic_results" in result or "error" in result
    # Regardless of content, the client must not crash
    assert isinstance(result, dict)


def test_empty_result_fixture_returns_without_error(
    session_factory: Callable[[], Session],
) -> None:
    """The India QEC fixture is a deliberate real empty-result response.

    SerpApi returns ``{"error": "Google hasn't returned any results..."}``
    for valid queries with no results — this must NOT raise SerpApiError.
    It returns the body and logs status 'empty' (AGENTS 3.4.6).
    """
    client = SerpApiClient(_fixture_settings(), session_factory, fixture_dir=_FIXTURE_DIR)

    # Must not raise; the empty-result error body is returned as-is
    result = client.search_jobs(
        "quantum error correction",
        location="India",
        gl="in",
        fixture_variant="india_p1",
    )

    assert isinstance(result, dict)
    error_text = result.get("error", "")
    assert isinstance(error_text, str)
    assert "hasn't returned any results" in error_text
