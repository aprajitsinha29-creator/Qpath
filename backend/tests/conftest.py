"""Shared pytest fixtures: a fresh temp database per test plus a TestClient.

Rules for this suite (AGENTS.md 3.7): no network — SerpApi tests use
``httpx.MockTransport`` or JSON files written to ``tmp_path``; never recorded
fixtures from ``tests/fixtures/serpapi/``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_engine, get_sessionmaker


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
