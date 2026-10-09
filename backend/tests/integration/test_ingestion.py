"""Ingestion service integration tests against a temporary SQLite DB (plan 1.7).

SerpApi traffic is simulated with crafted fixture files in ``tmp_path`` plus the
real :class:`SerpApiClient` in fixture mode — the same code path production
uses, minus the network (AGENTS 3.7.1). Expected ``FixtureMissingError``
responses (pages beyond the recordings) are part of the scenarios, mirroring
the real committed fixture set.
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.integrations.serpapi.client import SerpApiClient
from app.models import JobPosting, JobPostingSubfield, PulseSnapshot, RefreshRun
from app.services import ingestion_service
from tests.conftest import write_serpapi_fixture as write_fixture

EMPTY_RESULT_BODY = {"error": "Google hasn't returned any results for this query."}

# Subfield rows must exist (postings link to them); _seed_reference_data
# lives in conftest.py and is applied via the pytestmark below.
pytestmark = pytest.mark.usefixtures("_seed_reference_data")


def job(
    title: str,
    company: str,
    location: str | None = "Munich, Germany",
    **extra: Any,
) -> dict[str, Any]:
    """Build a raw posting dict shaped like the real recordings."""
    payload: dict[str, Any] = {
        "title": title,
        "company_name": company,
        "location": location,
        "via": "LinkedIn",
        "extensions": ["3 days ago", "Full–time"],
        "apply_options": [{"title": "LinkedIn", "link": f"https://example.com/{company}/{title}"}],
        "job_id": f"id-{company}-{title}".replace(" ", "-"),
        "description": f"Description for {title} at {company}.",
    }
    payload.update(extra)
    return payload


# --------------------------------------------------------------------------
# Core behaviors
# --------------------------------------------------------------------------


def test_refresh_jobs_is_idempotent(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Running twice: same row counts, second run reports zero new postings.

    Re-seen postings must update last_seen_at (proving the refresh path ran)
    without duplicating rows or resetting first_seen_at (plan 1.7).
    """
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [
                job("QEC Engineer", "Riverlane"),
                job("Decoder Scientist", "Alice & Bob"),
            ]
        },
    )

    run1 = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="daily", region="global", subfield_ids=["qec"]
    )
    postings_after_first = list(db_session.scalars(select(JobPosting)))
    first_seen = {p.id: p.first_seen_at for p in postings_after_first}
    last_seen_first = {p.id: p.last_seen_at for p in postings_after_first}
    counts_first = {
        "postings": db_session.scalar(select(func.count()).select_from(JobPosting)),
        "links": db_session.scalar(select(func.count()).select_from(JobPostingSubfield)),
        "snapshots": db_session.scalar(select(func.count()).select_from(PulseSnapshot)),
    }

    time.sleep(0.01)  # guarantee the clock moved between runs
    run2 = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="daily", region="global", subfield_ids=["qec"]
    )

    counts_second = {
        "postings": db_session.scalar(select(func.count()).select_from(JobPosting)),
        "links": db_session.scalar(select(func.count()).select_from(JobPostingSubfield)),
        "snapshots": db_session.scalar(select(func.count()).select_from(PulseSnapshot)),
    }
    assert run1.details["postings_new"] == 2
    assert run2.details["postings_new"] == 0
    assert counts_first == counts_second

    for posting in db_session.scalars(select(JobPosting)):
        assert posting.first_seen_at == first_seen[posting.id]  # identity birthday kept
        assert posting.last_seen_at > last_seen_first[posting.id]  # recency moved forward
        assert posting.is_active is True


def test_dedupe_across_queries_keeps_core_tier(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """The same posting found by two queries of one subfield creates ONE row.

    The core-tier link must survive (never downgraded) and the extended link
    is recorded separately; active_postings counts unique core postings.
    """
    # Same person/posting appears in the core QEC query AND the extended one.
    shared = job("QEC Engineer", "Riverlane")
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {"jobs_results": [shared, job("Decoder Scientist", "Alice & Bob")]},
    )
    write_fixture(
        fixture_dir,
        "fault tolerant quantum computing",
        "global_p1",
        {"jobs_results": [shared]},
    )

    run = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="bootstrap", region="global", subfield_ids=["qec"]
    )

    # shared + decoder = 2 unique postings even though 3 raw results were seen
    assert run.details["postings_seen"] == 3
    assert run.details["postings_new"] == 2

    postings = list(db_session.scalars(select(JobPosting)))
    assert len(postings) == 2

    links = list(db_session.scalars(select(JobPostingSubfield)))
    # Plan 4.3: one link row per (posting, subfield, region) — the shared
    # posting keeps its single core link (never downgraded/duplicated by the
    # extended re-discovery), plus one core link for the second posting.
    assert len(links) == 2
    by_title = {}
    for link in links:
        posting = db_session.get(JobPosting, link.posting_id)
        by_title[posting.title] = link
    shared_link = by_title["QEC Engineer"]
    assert shared_link.tier == "core"
    # Regression guard: re-discovery via the extended query must NOT rewrite
    # the retained core link's source_query (provenance tracks the tier kept).
    assert shared_link.source_query == "quantum error correction"
    assert by_title["Decoder Scientist"].tier == "core"

    snapshot = db_session.scalar(select(PulseSnapshot))
    assert snapshot is not None
    assert snapshot.active_postings == 2  # core-tier unique postings only
    assert snapshot.new_postings == 2


def test_pagination_stops_when_fixture_missing(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Bootstrap follows next_page_token until a fixture is missing — then stops.

    The missing page is the normal end of pagination in fixture mode: the run
    finishes successfully with no recorded errors (task brief; AGENTS 3.4.3).
    """
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [job("QEC Engineer", "Riverlane")],
            "serpapi_pagination": {"next_page_token": "token-page-2"},
        },
    )
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p2",
        {
            "jobs_results": [job("Decoder Scientist", "Alice & Bob")],
            "serpapi_pagination": {"next_page_token": "token-page-3"},
        },
    )
    # No global_p3 fixture and no extended-query fixture on purpose.

    run = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="bootstrap", region="global", subfield_ids=["qec"]
    )

    assert run.status == "done"
    assert run.details["errors"] == []
    assert run.serpapi_calls == 2  # pages 1-2 succeeded, page 3 missing
    assert db_session.scalar(select(func.count()).select_from(JobPosting)) == 2


def test_empty_result_fixture_is_zero_postings_not_an_error(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """The India QEC fixture (the real 'no results' body) ingests as zero.

    India runs use location=India/gl=in params; the empty body has no
    jobs_results key — zero postings, run still 'done'.
    """
    write_fixture(fixture_dir, "quantum error correction", "india_p1", EMPTY_RESULT_BODY)

    run = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="daily", region="india", subfield_ids=["qec"]
    )

    assert run.status == "done"
    assert run.details["postings_seen"] == 0
    assert db_session.scalar(select(func.count()).select_from(JobPosting)) == 0
    snapshot = db_session.scalar(select(PulseSnapshot))
    assert snapshot is not None
    assert snapshot.active_postings == 0
    assert snapshot.region == "india"


def test_query_failure_is_recorded_and_run_continues(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """A broken fixture (non-object JSON) fails one query; the other still ingests."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "india_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},
    )
    # A JSON *list* is valid JSON but not a JSON object → SerpApiError (not missing).
    (fixture_dir / "google_jobs__quantum-software-engineer__india_p1.json").write_text(
        "[1, 2, 3]", encoding="utf-8"
    )

    run = ingestion_service.refresh_jobs(
        db_session,
        serpapi_fixture_client,
        mode="daily",
        region="india",
        subfield_ids=["qec", "software"],
    )

    assert run.status == "partial"
    errors = run.details["errors"]
    assert len(errors) == 1
    assert "quantum software engineer" in errors[0]
    # The healthy query still ingested its posting.
    assert db_session.scalar(select(func.count()).select_from(JobPosting)) == 1
    assert run.details["postings_new"] == 1


def test_refresh_jobs_rejects_unknown_mode_and_region(
    serpapi_fixture_client: SerpApiClient, db_session: Session
) -> None:
    """Unknown mode/region is a caller contract bug and raises immediately."""
    with pytest.raises(ValueError, match="unknown mode"):
        ingestion_service.refresh_jobs(
            db_session, serpapi_fixture_client, mode="hourly", region="global"
        )
    with pytest.raises(ValueError, match="unknown region"):
        ingestion_service.refresh_jobs(
            db_session, serpapi_fixture_client, mode="daily", region="mars"
        )


def test_extended_only_postings_do_not_count_as_active(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """A posting found ONLY via an extended query is linked but not 'active' demand."""
    write_fixture(
        fixture_dir,
        "fault tolerant quantum computing",
        "global_p1",
        {"jobs_results": [job("FTQC Architect", "PsiQuantum")]},
    )

    run = ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="bootstrap", region="global", subfield_ids=["qec"]
    )

    assert run.details["postings_new"] == 1
    link = db_session.scalar(select(JobPostingSubfield))
    assert link is not None
    assert link.tier == "extended"
    snapshot = db_session.scalar(select(PulseSnapshot))
    assert snapshot is not None
    assert snapshot.active_postings == 0  # extended-only → not headline demand


def test_stale_postings_are_deactivated_after_window(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postings not re-seen for 14 days become inactive; re-seen ones revive."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [
                job("QEC Engineer", "Riverlane"),
                job("Decoder Scientist", "Alice & Bob"),
            ]
        },
    )
    ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="daily", region="global", subfield_ids=["qec"]
    )

    # Simulate both postings being old enough to be stale...
    for posting in db_session.scalars(select(JobPosting)):
        posting.last_seen_at = posting.last_seen_at - timedelta(
            days=ingestion_service.STALE_AFTER_DAYS + 1
        )
    db_session.commit()

    # ...but the fresh run re-sees one of them (its fixture still returns it).
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},
    )
    ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="daily", region="global", subfield_ids=["qec"]
    )

    statuses = {p.title: p.is_active for p in db_session.scalars(select(JobPosting))}
    assert statuses == {"QEC Engineer": True, "Decoder Scientist": False}


def test_standalone_refresh_uses_its_own_session(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path
) -> None:
    """The standalone wrapper (scheduler entry point) persists via SessionLocal."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},
    )

    run = ingestion_service.run_refresh_jobs_standalone(
        serpapi_fixture_client, mode="daily", region="global", subfield_ids=["qec"]
    )

    assert run.details["postings_new"] == 1
    with SessionLocal() as check:
        assert check.scalar(select(func.count()).select_from(JobPosting)) == 1
        runs = list(check.scalars(select(RefreshRun)))
    assert len(runs) == 1


# --------------------------------------------------------------------------
# Page-cap recording (Phase 4 step 4.2: feeds the saturation flag)
# --------------------------------------------------------------------------


def _bootstrap_with_page_cap(
    fixture_dir: Path,
    db_session: Session,
    client: SerpApiClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    max_pages: str,
    has_next_page: bool,
    mode: str = "bootstrap",
) -> RefreshRun:
    """Run one QEC refresh whose page 1 may advertise a pending page 2."""
    payload: dict[str, Any] = {"jobs_results": [job("QEC Engineer", "Riverlane")]}
    if has_next_page:
        payload["serpapi_pagination"] = {"next_page_token": "page-2-token"}
    write_fixture(fixture_dir, "quantum error correction", "global_p1", payload)

    from app.core.config import get_settings

    # refresh_jobs reads the page cap from the cached Settings at call time.
    monkeypatch.setenv("SERPAPI_JOBS_MAX_PAGES", max_pages)
    get_settings.cache_clear()
    try:
        return ingestion_service.refresh_jobs(
            db_session, client, mode=mode, region="global", subfield_ids=["qec"]
        )
    finally:
        get_settings.cache_clear()


def test_refresh_bootstrap_records_page_cap_subfield(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A core query truncated by SERPAPI_JOBS_MAX_PAGES is recorded as capped."""
    run = _bootstrap_with_page_cap(
        fixture_dir,
        db_session,
        serpapi_fixture_client,
        monkeypatch,
        max_pages="1",
        has_next_page=True,
    )

    assert run.mode == "bootstrap"
    assert run.details["page_cap_subfields"] == ["qec"]


def test_refresh_bootstrap_without_pending_page_is_not_capped(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ending because the results ran out is end-of-data, not saturation."""
    run = _bootstrap_with_page_cap(
        fixture_dir,
        db_session,
        serpapi_fixture_client,
        monkeypatch,
        max_pages="1",
        has_next_page=False,
    )

    assert run.details["page_cap_subfields"] == []


def test_refresh_daily_never_records_page_cap(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daily runs fetch exactly one page by design — never a cap hit."""
    run = _bootstrap_with_page_cap(
        fixture_dir,
        db_session,
        serpapi_fixture_client,
        monkeypatch,
        max_pages="1",
        has_next_page=True,
        mode="daily",
    )

    assert run.details["page_cap_subfields"] == []
