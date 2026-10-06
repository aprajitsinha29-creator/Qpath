"""Pulse service integration tests (plan 1.7): aggregation rules over stored data.

Ingests through the real service into a temp SQLite DB, then asserts the
card aggregation rules: core-only headline counts, extended-only extras,
internship counts, top companies, low_data, and the single-day
``new_this_week = null`` rule.

Phase 2 step 2.6 adds tests for the intelligence layer: top skills (share over
extracted postings), seniority/PhD mix, extraction coverage, and research themes.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.integrations.serpapi.client import SerpApiClient
from app.models import JobPosting, JobPostingSkill, PaperSnapshot, ResearchTheme
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


# --------------------------------------------------------------------------
# Phase 2 step 2.6: intelligence layer tests
# --------------------------------------------------------------------------


def _ingest_and_extract(
    serpapi_fixture_client: SerpApiClient,
    fixture_dir: Path,
    db_session: Session,
    *,
    region: str = "global",
) -> None:
    """Run bootstrap ingestion and mark postings as extracted with skills."""
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
    ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="bootstrap", region=region
    )

    # Mark postings as extracted with skills (simulating extraction service output)
    postings = list(db_session.scalars(select(JobPosting)))
    # Only first 3 (core-tier) are extracted; extended-only (FTQC) stays pending
    for i, p in enumerate(postings[:3]):
        p.extraction_status = "done"
        p.extraction_attempts = 0
        if i == 0:  # QEC Engineer
            p.seniority = "mid"
            p.requires_phd = False
        elif i == 1:  # QEC Intern
            p.seniority = "intern"
            p.requires_phd = False
        else:  # Decoder Scientist
            p.seniority = "senior"
            p.requires_phd = True

    # Add skills: python on all 3 extracted, qiskit on 2, stim on 1,
    # cpp on 1 (extended-only, not extracted)
    # Posting 0: python, qiskit
    # Posting 1: python, qiskit
    # Posting 2: python, stim
    # Posting 3 (extended-only FTQC): cpp (not extracted, so not counted in shares)
    for p in postings[:2]:
        db_session.add(JobPostingSkill(posting_id=p.id, skill_id="python"))
        db_session.add(JobPostingSkill(posting_id=p.id, skill_id="qiskit"))
    db_session.add(JobPostingSkill(posting_id=postings[2].id, skill_id="python"))
    db_session.add(JobPostingSkill(posting_id=postings[2].id, skill_id="stim"))
    db_session.add(JobPostingSkill(posting_id=postings[3].id, skill_id="cpp"))
    db_session.commit()
    db_session.flush()  # Ensure all changes are visible to subsequent queries


def test_top_skills_share_over_extracted_postings(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Skill share = mentions / extracted_count (NOT total postings)."""
    _ingest_and_extract(serpapi_fixture_client, fixture_dir, db_session)

    all_ids = pulse_service._all_linked_posting_ids(db_session, "qec", "global")
    top_skills = pulse_service._top_skills(db_session, all_ids, limit=10)

    # 3 extracted postings (the 3 core), 1 extended-only (not extracted)
    # python on 3/3 = 1.0, qiskit on 2/3 ≈ 0.667, stim on 1/3 ≈ 0.333
    shares = {s["skill_id"]: s["share"] for s in top_skills}
    assert shares["python"] == 1.0
    assert abs(shares["qiskit"] - 2 / 3) < 0.001
    assert abs(shares["stim"] - 1 / 3) < 0.001
    # cpp is on extended-only posting (not extracted) → not counted
    assert "cpp" not in shares

    # Sorted by share desc, name asc
    assert [s["skill_id"] for s in top_skills] == ["python", "qiskit", "stim"]


def test_top_skills_empty_when_no_extracted_postings(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Zero extracted postings → empty skill list (not an error)."""
    write_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},
    )
    ingestion_service.refresh_jobs(
        db_session, serpapi_fixture_client, mode="bootstrap", region="global"
    )

    all_ids = pulse_service._all_linked_posting_ids(db_session, "qec", "global")
    top_skills = pulse_service._top_skills(db_session, all_ids, limit=10)
    assert top_skills == []


def test_seniority_mix_includes_unknown_bucket(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Seniority NULL → 'unknown' bucket; phd_share over known only."""
    _ingest_and_extract(serpapi_fixture_client, fixture_dir, db_session)

    all_ids = pulse_service._all_linked_posting_ids(db_session, "qec", "global")
    mix = pulse_service._seniority_mix(db_session, all_ids)

    # 4 postings total: mid, intern, senior, NULL (extended-only has no seniority)
    assert mix["seniority"]["mid"] == 1
    assert mix["seniority"]["intern"] == 1
    assert mix["seniority"]["senior"] == 1
    assert mix["seniority"]["unknown"] == 1

    # phd_share: 1 of 3 with known requires_phd (extended-only has None)
    assert mix["phd_share"] == 1 / 3


def test_seniority_mix_empty_postings_returns_none_phd(
    db_session: Session,
) -> None:
    """Empty posting set → empty seniority, phd_share=None."""
    mix = pulse_service._seniority_mix(db_session, set())
    assert mix["seniority"] == {}
    assert mix["phd_share"] is None


def test_extraction_coverage_calculated_correctly(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Coverage = done / total (both tiers); 0.0 when empty."""
    _ingest_and_extract(serpapi_fixture_client, fixture_dir, db_session)

    all_ids = pulse_service._all_linked_posting_ids(db_session, "qec", "global")
    coverage = pulse_service._extraction_coverage(db_session, all_ids)
    # 3 done out of 4 total
    assert abs(coverage - 0.75) < 0.001

    # Empty case
    assert pulse_service._extraction_coverage(db_session, set()) == 0.0


def test_themes_with_papers_resolves_links(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Themes from newest batch with paper refs; missing ids skipped."""
    from app.core.clock import utc_now

    _ingest_and_extract(serpapi_fixture_client, fixture_dir, db_session)

    # Create a research theme batch with papers
    now = utc_now()
    batch_id = "test-batch-123"
    p1 = PaperSnapshot(
        subfield_id="qec",
        batch_id=batch_id,
        query="quantum error correction",
        title="Paper One",
        snippet="snippet 1",
        link="https://example.com/p1",
        publication_summary="2024",
        year=2024,
        cited_by=10,
        fetched_at=now,
    )
    p2 = PaperSnapshot(
        subfield_id="qec",
        batch_id=batch_id,
        query="quantum error correction",
        title="Paper Two",
        snippet="snippet 2",
        link="https://example.com/p2",
        publication_summary="2024",
        year=2024,
        cited_by=5,
        fetched_at=now,
    )
    db_session.add_all([p1, p2])
    db_session.flush()

    db_session.add(
        ResearchTheme(
            subfield_id="qec",
            batch_id=batch_id,
            themes=[
                {
                    "label": "Surface codes",
                    "summary": "Focus on surface codes.",
                    "paper_ids": [p1.id, p2.id],
                },
                {
                    "label": "Decoders",
                    "summary": "MWPM and union-find.",
                    "paper_ids": [p2.id, 99999],  # 99999 missing
                },
            ],
            generated_at=now,
            model="gemini-test",
        )
    )
    db_session.commit()

    themes = pulse_service._themes_with_papers(db_session, "qec")
    assert len(themes) == 2
    assert themes[0]["label"] == "Surface codes"
    assert len(themes[0]["papers"]) == 2
    assert themes[1]["label"] == "Decoders"
    assert len(themes[1]["papers"]) == 1  # missing id skipped
    assert themes[1]["papers"][0]["title"] == "Paper Two"


def test_themes_empty_when_no_batch(
    db_session: Session,
) -> None:
    """No research themes batch → empty list (valid empty state)."""
    themes = pulse_service._themes_with_papers(db_session, "qec")
    assert themes == []


def test_get_subfield_detail_returns_full_payload(
    serpapi_fixture_client: SerpApiClient, fixture_dir: Path, db_session: Session
) -> None:
    """Detail endpoint aggregates all intelligence fields + postings list."""
    from app.core.errors import NotFoundError

    _ingest_and_extract(serpapi_fixture_client, fixture_dir, db_session)

    # Add a research theme batch
    from app.core.clock import utc_now

    now = utc_now()
    batch_id = "detail-test-batch"
    p1 = PaperSnapshot(
        subfield_id="qec",
        batch_id=batch_id,
        query="quantum error correction",
        title="Theme Paper",
        snippet="theme snippet",
        link="https://example.com/theme",
        publication_summary="2024",
        year=2024,
        cited_by=0,
        fetched_at=now,
    )
    db_session.add(p1)
    db_session.flush()
    db_session.add(
        ResearchTheme(
            subfield_id="qec",
            batch_id=batch_id,
            themes=[{"label": "Test Theme", "summary": "A test theme.", "paper_ids": [p1.id]}],
            generated_at=now,
            model="gemini-test",
        )
    )
    db_session.commit()

    detail = pulse_service.get_subfield_detail(db_session, "qec", "global")

    # Card fields
    assert detail["subfield_id"] == "qec"
    assert detail["active_postings"] == 3
    assert detail["extra_postings"] == 1
    assert detail["internship_postings"] == 1
    assert detail["low_data"] is True

    # Intelligence fields
    assert len(detail["top_skills"]) == 3  # python, qiskit, stim (cpp on extended-only)
    assert detail["seniority_mix"]["mid"] == 1
    assert detail["seniority_mix"]["intern"] == 1
    assert detail["seniority_mix"]["senior"] == 1
    assert detail["seniority_mix"]["unknown"] == 1
    assert detail["phd_share"] == 1 / 3
    assert abs(detail["extraction_coverage"] - 0.75) < 0.001
    assert len(detail["themes"]) == 1
    assert detail["themes"][0]["label"] == "Test Theme"
    assert len(detail["themes"][0]["papers"]) == 1

    # Postings list (newest first, limit 20)
    assert len(detail["postings"]) == 4
    # Ordered by last_seen_at desc, then id asc - all have same last_seen_at from
    # bootstrap, so by id
    assert detail["postings"][0]["title"] == "QEC Engineer"
    assert detail["postings"][3]["title"] == "FTQC Architect"

    # Unknown subfield → 404
    with pytest.raises(NotFoundError):
        pulse_service.get_subfield_detail(db_session, "no-such-subfield", "global")
