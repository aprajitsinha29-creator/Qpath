"""Query plan invariants (plan 4.6): core coverage, scholar coverage, fixture plan."""

from __future__ import annotations

from app.integrations.serpapi.queries import (
    FIXTURE_PLAN,
    JOB_QUERY_PLAN,
    SCHOLAR_QUERY_PLAN,
    estimate_fixture_calls,
)

SCORED_SUBFIELDS = {"qec", "hardware", "software", "algorithms", "qml", "crypto_net"}


def test_job_plan_has_exactly_one_core_query_per_scored_subfield() -> None:
    """Daily (core) mode runs exactly one query per scored subfield."""
    core = [spec for spec in JOB_QUERY_PLAN if spec.tier == "core"]

    assert {spec.subfield_id for spec in core} == SCORED_SUBFIELDS
    assert len(core) == 6


def test_scholar_plan_covers_every_scored_subfield() -> None:
    """Weekly Scholar refresh queries all six scored subfields, once each."""
    assert {spec.subfield_id for spec in SCHOLAR_QUERY_PLAN} == SCORED_SUBFIELDS
    assert len(SCHOLAR_QUERY_PLAN) == 6


def test_fixture_plan_matches_recording_plan() -> None:
    """6 global core jobs + 2 India jobs + 6 Scholar + one page-2 follow-up (plan 4.6)."""
    jobs = [spec for spec in FIXTURE_PLAN if spec.engine == "google_jobs"]
    scholar = [spec for spec in FIXTURE_PLAN if spec.engine == "google_scholar"]
    india = [spec for spec in FIXTURE_PLAN if spec.variant == "india_p1"]
    follow_ups = [spec for spec in FIXTURE_PLAN if spec.follow_next_page]

    assert len(jobs) == 8  # 6 global + 2 India
    assert len(scholar) == 6
    assert len(FIXTURE_PLAN) == 14
    assert estimate_fixture_calls() == 15  # +1 via next_page_token follow-up

    assert len(india) == 2
    assert all(spec.location == "India" and spec.gl == "in" for spec in india)

    assert len(follow_ups) == 1
    assert follow_ups[0].query == "quantum error correction"
    assert follow_ups[0].next_page_variant == "global_p2"
    assert all(spec.variant == "recent" for spec in scholar)
