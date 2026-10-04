"""SerpApiClient behavior (plan steps 0.4 and 0.8).

Fixture paths are written to ``tmp_path`` and live calls go through
``httpx.MockTransport`` — no network, no recorded fixtures, no real keys.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import FixtureMissingError, SerpApiCapExceeded, SerpApiError
from app.db.session import SessionLocal
from app.integrations.serpapi.client import (
    SerpApiClient,
    fixture_file_name,
    scrub_api_key,
    slugify_query,
)
from app.models import SerpApiCallLog

_FIXTURE_NAME = "google_jobs__quantum-error-correction__global_p1.json"


@pytest.fixture()
def session_factory(db_session: Session) -> Callable[[], Session]:
    """Session factory for the client; the db_session fixture guarantees tables exist."""
    return SessionLocal


def _fixture_settings() -> Settings:
    """Settings in fixture mode (the default dev path, keyless)."""
    return Settings(serpapi_use_fixtures=True, serpapi_api_key="")


def _live_settings(cap: int = 60) -> Settings:
    """Settings in live mode with a fake key (never sent anywhere real)."""
    return Settings(
        serpapi_use_fixtures=False,
        serpapi_api_key="test-key-123",
        serpapi_daily_call_cap=cap,
    )


def _live_client(
    handler: Callable[[httpx.Request], httpx.Response],
    session_factory: Callable[[], Session],
    fixture_dir: Path,
    cap: int = 60,
) -> SerpApiClient:
    """Build a live-mode client whose HTTP goes to a MockTransport handler."""
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return SerpApiClient(
        _live_settings(cap), session_factory, http_client=http, fixture_dir=fixture_dir
    )


def test_serpapi_client_reads_fixture(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """Fixture mode returns the recorded payload and logs a fixture/ok row."""
    payload = {"organic_results": [{"title": "stub"}]}
    (tmp_path / _FIXTURE_NAME).write_text(json.dumps(payload), encoding="utf-8")
    client = SerpApiClient(_fixture_settings(), session_factory, fixture_dir=tmp_path)

    result = client.search_jobs("quantum error correction", fixture_variant="global_p1")

    assert result == payload
    with session_factory() as session:
        row = session.scalar(select(SerpApiCallLog))
        assert row is not None
        logged = (row.engine, row.source, row.status, row.query)
    assert logged == ("google_jobs", "fixture", "ok", "quantum error correction")


def test_serpapi_client_raises_when_fixture_missing(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """A missing recording raises FixtureMissingError and is logged as 'missing'."""
    client = SerpApiClient(_fixture_settings(), session_factory, fixture_dir=tmp_path)

    with pytest.raises(FixtureMissingError, match="fixture not found"):
        client.search_jobs("no such query", fixture_variant="global_p1")

    with session_factory() as session:
        status = session.scalar(select(SerpApiCallLog.status))
    assert status == "missing"


def test_serpapi_client_enforces_daily_cap(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """With the day's live count at the cap, no HTTP request is made at all."""
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json={"ok": True})

    client = _live_client(handler, session_factory, tmp_path, cap=2)
    with session_factory() as session:
        session.add_all(
            SerpApiCallLog(engine="google_jobs", query="x", source="live", status="ok")
            for _ in range(2)
        )
        session.commit()

    with pytest.raises(SerpApiCapExceeded, match="cap reached"):
        client.search_jobs("quantum", fixture_variant="global_p1")

    assert requests_seen == []


def test_serpapi_client_raises_on_error_body(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """A body containing 'error' becomes SerpApiError and logs status=error."""
    client = _live_client(
        lambda request: httpx.Response(200, json={"error": "Invalid API key provided."}),
        session_factory,
        tmp_path,
    )

    with pytest.raises(SerpApiError, match="Invalid API key"):
        client.search_jobs("quantum", fixture_variant="global_p1")

    with session_factory() as session:
        status = session.scalar(select(SerpApiCallLog.status))
    assert status == "error"


def test_serpapi_client_treats_no_results_error_as_empty_result(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """A 'no results' error body returns without raising and logs status=empty."""
    empty_body = {"error": "Google hasn't returned any results for this query."}
    client = _live_client(
        lambda request: httpx.Response(200, json=empty_body),
        session_factory,
        tmp_path,
    )

    result = client.search_jobs("quantum", fixture_variant="global_p1")

    assert result == empty_body
    with session_factory() as session:
        status = session.scalar(select(SerpApiCallLog.status))
    assert status == "empty"


def test_serpapi_client_retries_once_on_5xx(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """A 5xx is retried exactly once; the completed call logs a single ok row."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json={"search_metadata": {"status": "Success"}})

    client = _live_client(handler, session_factory, tmp_path)

    result = client.search_jobs("quantum", fixture_variant="global_p1")

    assert result["search_metadata"]["status"] == "Success"
    assert attempts == 2
    with session_factory() as session:
        rows = list(session.scalars(select(SerpApiCallLog)))
        logged = [(row.source, row.status) for row in rows]
    assert logged == [("live", "ok")]


def test_serpapi_client_never_retries_4xx(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """4xx means the request is wrong — exactly one attempt, then SerpApiError."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"error": "not found"})

    client = _live_client(handler, session_factory, tmp_path)

    with pytest.raises(SerpApiError, match="404"):
        client.search_jobs("quantum", fixture_variant="global_p1")

    assert attempts == 1


def test_serpapi_client_sends_key_only_at_call_time(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """The key is a query param on the wire but never appears in logs or messages."""
    key = "super-secret-serpapi-key"
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["api_key"] == key
        if calls == 1:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"error": f"Invalid key {key} provided"})

    settings = Settings(serpapi_use_fixtures=False, serpapi_api_key=key)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = SerpApiClient(settings, session_factory, http_client=http, fixture_dir=tmp_path)

    client.search_jobs("quantum", fixture_variant="global_p1")  # success path first
    with pytest.raises(SerpApiError) as excinfo:
        client.search_jobs("quantum", fixture_variant="global_p1")  # error path second

    assert key not in str(excinfo.value)
    assert "***" in str(excinfo.value)
    with session_factory() as session:
        queries = list(session.scalars(select(SerpApiCallLog.query)))
    assert all(key not in query for query in queries)


def test_serpapi_client_never_logs_api_key(
    tmp_path: Path, session_factory: Callable[[], Session], caplog: pytest.LogCaptureFixture
) -> None:
    """DEBUG-level logs from a live call must not contain the key (AGENTS 3.4.5)."""
    key = "another-secret-key-456"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == key
        return httpx.Response(200, json={"ok": True})

    settings = Settings(serpapi_use_fixtures=False, serpapi_api_key=key)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = SerpApiClient(settings, session_factory, http_client=http, fixture_dir=tmp_path)

    with caplog.at_level(logging.DEBUG):
        client.search_jobs("quantum", fixture_variant="global_p1")

    assert key not in caplog.text


def test_search_jobs_sends_location_and_pagination(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """Jobs helper sends hl, location/gl and next_page_token (never 'start')."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"jobs_results": []})

    client = _live_client(handler, session_factory, tmp_path)

    client.search_jobs(
        "quantum error correction",
        location="India",
        gl="in",
        next_page_token="tok123",
        fixture_variant="india_p1",
    )

    assert seen["engine"] == "google_jobs"
    assert seen["hl"] == "en"
    assert seen["location"] == "India"
    assert seen["gl"] == "in"
    assert seen["next_page_token"] == "tok123"
    assert "start" not in seen


def test_search_scholar_sends_recent_params(
    tmp_path: Path, session_factory: Callable[[], Session]
) -> None:
    """Scholar helper sends hl, num=20 and scisbd=1 for recent-only searches."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"organic_results": []})

    client = _live_client(handler, session_factory, tmp_path)

    client.search_scholar("quantum algorithms", fixture_variant="recent")

    assert seen["engine"] == "google_scholar"
    assert seen["hl"] == "en"
    assert seen["num"] == "20"
    assert seen["scisbd"] == "1"


def test_slugify_query_handles_symbols() -> None:
    """Slugs stay filesystem-safe and stable for compound queries."""
    assert (
        slugify_query("quantum key distribution OR post-quantum cryptography")
        == "quantum-key-distribution-or-post-quantum-cryptography"
    )


def test_fixture_file_name_matches_recording_convention() -> None:
    """Client and recorder share the same <engine>__<slug>__<variant>.json name."""
    assert (
        fixture_file_name("google_jobs", "quantum error correction", "global_p1") == _FIXTURE_NAME
    )


def test_scrub_api_key_removes_nested_keys() -> None:
    """Scrubbing walks dicts and lists so recordings can never carry credentials."""
    payload = {
        "search_parameters": {"api_key": "abc123", "q": "x"},
        "items": [{"api_key": "abc123"}],
    }

    scrubbed = scrub_api_key(payload)

    assert scrubbed["search_parameters"]["api_key"] == "***"
    assert scrubbed["items"][0]["api_key"] == "***"
    assert scrubbed["search_parameters"]["q"] == "x"
    assert payload["search_parameters"]["api_key"] == "abc123"  # input untouched
