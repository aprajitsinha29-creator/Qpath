"""Shared pytest fixtures: a fresh temp database per test plus a TestClient.

Rules for this suite (AGENTS.md 3.7): no network — SerpApi tests use
``httpx.MockTransport`` or JSON files written to ``tmp_path``; never recorded
fixtures from ``tests/fixtures/serpapi/``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal, get_engine, get_sessionmaker
from app.integrations.serpapi.client import SerpApiClient


@pytest.fixture(autouse=True)
def _clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point every test at its own SQLite file and fixture mode, then reset caches.

    Runs around each test so no test can see another test's database or a
    developer's real ``backend/.env`` values.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("SERPAPI_USE_FIXTURES", "true")
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    for clear in (get_settings.cache_clear, get_engine.cache_clear, get_sessionmaker.cache_clear):
        clear()
    setup_logging("INFO")
    yield
    for clear in (get_settings.cache_clear, get_engine.cache_clear, get_sessionmaker.cache_clear):
        clear()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """TestClient with lifespan running: tables created and reference data seeded."""
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """A session on the temp test database with tables created (no seed)."""
    from app.db.session import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def _seed_reference_data(db_session: Session) -> None:
    """Seed taxonomy/careers/skills into the temp DB (opt-in via usefixtures).

    Ingestion and pulse tests need real subfield rows: postings are linked to
    subfields through a foreign key, so the FK targets must exist.
    """
    from app.db.seed import seed_reference_data

    seed_reference_data(db_session)


# ---------------------------------------------------------------------------
# Shared SerpApi test fixtures (fixture-mode client over a per-test dir).
# Used by the ingestion/pulse integration tests; keeps ONE canonical set.
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixture_settings() -> Settings:
    """Settings in fixture mode: no network, no key needed."""
    return Settings(serpapi_use_fixtures=True, serpapi_api_key="")


@pytest.fixture()
def fixture_dir(tmp_path: Path) -> Path:
    """Empty per-test fixture directory; tests add the recordings they need."""
    directory = tmp_path / "fixtures"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@pytest.fixture()
def serpapi_fixture_client(fixture_settings: Settings, fixture_dir: Path) -> SerpApiClient:
    """A real SerpApiClient in fixture mode over ``fixture_dir`` (no network).

    Named distinctly from the TestClient ``client`` fixture to avoid confusion.
    """
    from app.integrations.serpapi.client import SerpApiClient

    return SerpApiClient(fixture_settings, SessionLocal, fixture_dir=fixture_dir)


def write_serpapi_fixture(fixture_dir: Path, query: str, variant: str, payload: dict) -> None:
    """Write one Google Jobs fixture file (the only recordings Phase 1 tests need)."""
    from app.integrations.serpapi.client import fixture_file_name

    name = fixture_file_name("google_jobs", query, variant)
    (fixture_dir / name).write_text(json.dumps(payload), encoding="utf-8")
