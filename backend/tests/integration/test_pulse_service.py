"""Pulse service integration tests (plan 1.7): aggregation rules over stored data.

Ingests through the real service into a temp SQLite DB, then asserts the
card aggregation rules: core-only headline counts, extended-only extras,
internship counts, top companies, low_data, and the single-day
``new_this_week = null`` rule.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.integrations.serpapi.client import SerpApiClient
from app.models import JobPosting
from app.services import ingestion_service, pulse_service
from tests.conftest import write_serpapi_fixture as write_fixture
from tests.integration.test_ingestion import job  # shared raw-posting builder

pytestmark = pytest.mark.usefixtures("_seed_reference_data")


def _ingest(
    serpapi_fixture_client: SerpApiClient,
    db_session: Session,
    mode: str = "bootstrap",
    region: str = "global",
) -> None:
    """Run a full bootstrap refresh over every subfield (fixture gaps are fine)."""
    ingestion_service.refresh_jobs(db_session, serpapi_fixture_client, mode=mode, region=region)


def test_pulse_cards_aggregate_counts(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Counts, internships, extras and companies aggregate as specified."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [
                job("QEC Engineer", "Riverlane"),
                job("QEC Intern", "Riverlane", extensions=["2 days ago", "Internship"]),
                job("Decoder Scientist", "Alice & Bob"),
            ]
        },
    )
    write_fixture(
        fixture_dir,
        "fault tolerant quantum computing",
        "global_p1",
        {"jobs_results": [job("FTQC Architect", "PsiQuantum")]},
    )

    _ingest(serpapi_fixture_client, db_session)
    cards = {
        card["subfield_id"]: card for card in pulse_service.get_pulse_cards(db_session, "global")
    }

    qec = cards["qec"]
    assert qec["active_postings"] == 3  # core-tier unique postings
    assert qec["extra_postings"] == 1  # extended-only posting
    assert qec["internship_postings"] == 1
    assert qec["top_companies"][0] == "Riverlane"  # 2 postings vs 1 elsewhere
    assert qec["low_data"] is True  # 3 < LOW_DATA_THRESHOLD(8)
    assert qec["tracking_since"] is not None
    # Single-day corpus → null (asserted in depth by its dedicated test below).
    assert qec["new_this_week"] is None

    # A subfield with no data at all still gets a card (six total).
    assert len(cards) == 6
    assert cards["qml"]["active_postings"] == 0
    assert cards["qml"]["low_data"] is True
    assert cards["qml"]["new_this_week"] is None
    assert cards["qml"]["top_companies"] == []
    assert cards["qml"]["tracking_since"] is None


def test_new_this_week_is_null_for_single_day_corpus(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """With one ingestion day, new_this_week must be null (plan 1.4)."""
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
    _ingest(serpapi_fixture_client, db_session)

    cards = pulse_service.get_pulse_cards(db_session, "global")
    qec = next(c for c in cards if c["subfield_id"] == "qec")
    assert qec["active_postings"] == 2
    assert qec["new_this_week"] is None
    assert qec["tracking_since"] is not None


def test_new_this_week_counts_once_corpus_spans_two_days(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backdating one posting's first_seen creates a 2-day corpus → number appears."""
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
    _ingest(serpapi_fixture_client, db_session)

    # Simulate yesterday's ingestion: one posting first seen 2 days ago.
    two_days_ago = utc_now() - timedelta(days=2)
    posting = db_session.query(JobPosting).filter_by(title="Decoder Scientist").one()
    posting.first_seen_at = two_days_ago
    db_session.commit()

    cards = pulse_service.get_pulse_cards(db_session, "global")
    qec = next(c for c in cards if c["subfield_id"] == "qec")
    assert qec["new_this_week"] == 2  # both first-seen within 7 days
    assert qec["tracking_since"] == two_days_ago.date().isoformat()


def test_core_results_equal_extended_queries_do_not_inflate_counts(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """A subfield with extra extended queries must not out-count a core-only one.

    Plan 1.7: both subfields have the same core result count; the one with
    additional extended-only postings must not show a higher active_postings.
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
    write_fixture(
        fixture_dir,
        "fault tolerant quantum computing",
        "global_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},  # re-finds one core posting
    )
    write_fixture(
        fixture_dir,
        "quantum machine learning",
        "global_p1",
        {"jobs_results": [job("QML Engineer", "Zapata"), job("QML Scientist", "SandboxAQ")]},
    )
    # qml has only its core query; qec additionally has an extended query with
    # one NEW extended-only posting.
    write_fixture(
        fixture_dir,
        "superconducting qubit",
        "global_p1",
        {"jobs_results": [job("Qubit Fabrication Engineer", "Google Quantum AI")]},
    )
    write_fixture(
        fixture_dir,
        "trapped ion quantum",
        "global_p1",
        {"jobs_results": [job("Ion Trap Engineer", "IonQ")]},
    )
    write_fixture(
        fixture_dir,
        "neutral atom quantum",
        "global_p1",
        {"jobs_results": [job("Neutral Atom Scientist", "QuEra")]},
    )

    _ingest(serpapi_fixture_client, db_session)
    cards = {c["subfield_id"]: c for c in pulse_service.get_pulse_cards(db_session, "global")}

    # qec core results = 2, qml core results = 2 → equal core counts.
    assert cards["qec"]["active_postings"] == 2
    assert cards["qml"]["active_postings"] == 2
    # The extended-only hardware-style postings ingested under hardware's
    # extended queries are extras, not headline demand for hardware either.
    assert cards["qec"]["extra_postings"] == 0  # extended found only the core posting
    # ...and fairness holds: extended tier never lifts the headline count.
    assert cards["hardware"]["active_postings"] == 0
    assert cards["hardware"]["extra_postings"] == 3


def test_list_postings_filters_and_paginates(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Posting list supports internship filter, limit/offset, and totals."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [
                job("QEC Engineer", "Riverlane"),
                job("QEC Intern", "Riverlane", extensions=["2 days ago", "Internship"]),
                job("Decoder Scientist", "Alice & Bob"),
            ]
        },
    )
    _ingest(serpapi_fixture_client, db_session)

    postings, total = pulse_service.list_postings(db_session, "qec", region="global")
    assert total == 3
    assert len(postings) == 3

    internships, intern_total = pulse_service.list_postings(
        db_session, "qec", region="global", internship=True
    )
    assert intern_total == 1
    assert internships[0].title == "QEC Intern"

    page, page_total = pulse_service.list_postings(
        db_session, "qec", region="global", limit=2, offset=0
    )
    assert page_total == 3
    assert len(page) == 2
    page2, _ = pulse_service.list_postings(db_session, "qec", region="global", limit=2, offset=2)
    assert len(page2) == 1


def test_list_postings_unknown_subfield_raises_not_found(
    db_session: Session,
) -> None:
    """Unknown subfield id → NotFoundError (router maps it to 404)."""
    from app.core.errors import NotFoundError

    with pytest.raises(NotFoundError):
        pulse_service.list_postings(db_session, "no-such-subfield")
