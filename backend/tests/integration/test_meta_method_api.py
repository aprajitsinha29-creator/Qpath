"""Integration tests for GET /meta/method (Phase 7 Method-page numbers).

Shape and empty-database behavior against a temporary SQLite DB — no mocks,
no network (AGENTS.md 3.7). The empty case must return zeros and nulls, not
an error: the Method page works from a fresh clone.
"""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobPosting, RefreshRun, ResearchTheme, SerpApiCallLog


def test_meta_method_empty_database_returns_zeroes_and_nulls(client: TestClient) -> None:
    """A fresh DB still answers: zero counts, no engines, null timestamps."""
    response = client.get("/api/v1/meta/method")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "serpapi_calls": {},
        "postings_total": 0,
        "postings_active": 0,
        "extraction_done": 0,
        "themes_count": 0,
        "last_jobs_refresh": None,
        "last_scholar_refresh": None,
    }


def test_meta_method_shape_carries_all_fields(client: TestClient, db_session: Session) -> None:
    """Every declared field is present with the declared type."""
    body = client.get("/api/v1/meta/method").json()
    assert set(body) == {
        "serpapi_calls",
        "postings_total",
        "postings_active",
        "extraction_done",
        "themes_count",
        "last_jobs_refresh",
        "last_scholar_refresh",
    }
    assert isinstance(body["serpapi_calls"], dict)
    for field in ("postings_total", "postings_active", "extraction_done", "themes_count"):
        assert isinstance(body[field], int)
    for field in ("last_jobs_refresh", "last_scholar_refresh"):
        assert body[field] is None or isinstance(body[field], str)


def test_meta_method_counts_serpapi_calls_by_engine_and_source(
    client: TestClient, db_session: Session
) -> None:
    """Call-log rows aggregate into {engine: {live, fixture}} buckets."""
    db_session.add_all(
        [
            SerpApiCallLog(engine="google_jobs", query="q1", source="live", status="ok"),
            SerpApiCallLog(engine="google_jobs", query="q2", source="fixture", status="ok"),
            SerpApiCallLog(engine="google_jobs", query="q3", source="fixture", status="ok"),
            SerpApiCallLog(engine="google_scholar", query="q4", source="fixture", status="ok"),
        ]
    )
    db_session.commit()

    body = client.get("/api/v1/meta/method").json()
    assert body["serpapi_calls"] == {
        "google_jobs": {"live": 1, "fixture": 2},
        "google_scholar": {"live": 0, "fixture": 1},
    }


def test_meta_method_counts_postings_and_themes(client: TestClient, db_session: Session) -> None:
    """Posting totals split by active; extraction counts only 'done' rows;
    themes counted across all rows."""
    db_session.add_all(
        [
            JobPosting(
                dedupe_key="k1",
                title="T1",
                company="C1",
                is_active=True,
                extraction_status="done",
            ),
            JobPosting(
                dedupe_key="k2",
                title="T2",
                company="C2",
                is_active=False,
                extraction_status="done",
            ),
            JobPosting(
                dedupe_key="k3",
                title="T3",
                company="C3",
                is_active=True,
                extraction_status="pending",
            ),
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            ResearchTheme(subfield_id="qec", batch_id="b1", themes=[], model="m"),
            ResearchTheme(subfield_id="qec", batch_id="b1", themes=[], model="m"),
        ]
    )
    db_session.commit()

    body = client.get("/api/v1/meta/method").json()
    assert body["postings_total"] == 3
    assert body["postings_active"] == 2
    assert body["extraction_done"] == 2
    assert body["themes_count"] == 2


def test_meta_method_last_refresh_uses_latest_successful_run(
    client: TestClient, db_session: Session
) -> None:
    """Only done/partial runs set the timestamps — failed runs are skipped."""
    db_session.add_all(
        [
            RefreshRun(
                kind="jobs",
                mode="daily",
                status="failed",
                started_at=datetime(2026, 10, 9, 3, 0, 0),
            ),
            RefreshRun(
                kind="jobs",
                mode="daily",
                status="done",
                started_at=datetime(2026, 10, 9, 3, 0, 0),
                finished_at=datetime(2026, 10, 9, 3, 5, 0),
            ),
            RefreshRun(
                kind="scholar",
                mode="weekly",
                status="partial",
                started_at=datetime(2026, 10, 6, 5, 0, 0),
                finished_at=datetime(2026, 10, 6, 5, 2, 0),
            ),
        ]
    )
    db_session.commit()

    body = client.get("/api/v1/meta/method").json()
    assert body["last_jobs_refresh"] is not None
    assert "2026-10-09" in body["last_jobs_refresh"]
    assert body["last_scholar_refresh"] is not None
    assert "2026-10-06" in body["last_scholar_refresh"]
