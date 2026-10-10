"""Integration tests for the Phase 5 tracker endpoints (tests 8-25).

Temp SQLite DB; controlled timestamps via the injectable clock (no sleep, no
time library); no SerpApi/Gemini calls (AGENTS 3.7).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.models import PulseSnapshot, RefreshRun
from app.services import tracker_service

pytestmark = [pytest.mark.usefixtures("_seed_reference_data")]

SCORED = ["qec", "hardware", "software", "algorithms", "qml", "crypto_net"]


def _take_diagnostic(client: TestClient, profile_id: str) -> int:
    questions = client.get("/api/v1/quiz").json()["questions"]
    res = client.post(
        f"/api/v1/profiles/{profile_id}/assessment",
        json={
            "interests": {s: 3 for s in SCORED},
            "answers": [{"question_id": q["id"], "selected_index": None} for q in questions],
        },
    )
    assert res.status_code == 200
    return int(res.json()["assessment_id"])


def _create(client: TestClient) -> str:
    return client.post("/api/v1/profiles").json()["profile_id"]


def _seed_postings(
    db: Session,
    subfield_id: str,
    *,
    count: int = 1,
    region: str = "global",
    tier: str = "core",
    first_seen: datetime | None = None,
    internship: bool = False,
    active: bool = True,
    extracted: bool = False,
    skill_ids: list[str] | None = None,
    title_prefix: str = "Engineer",
) -> list[int]:
    """Seed postings linked to (subfield, region); returns their ids."""
    from app.models import JobPosting, JobPostingSkill, JobPostingSubfield

    seen = first_seen or utc_now()
    ids: list[int] = []
    for i in range(count):
        posting = JobPosting(
            dedupe_key=f"{subfield_id}_{region}_{tier}_{title_prefix}_{i}_{seen.isoformat()}",
            title=f"{title_prefix} {subfield_id} {i}",
            company="Quantum Corp",
            location="Remote",
            is_active=active,
            is_internship=internship,
            extraction_status="done" if extracted else "pending",
            first_seen_at=seen,
            last_seen_at=seen,
        )
        db.add(posting)
        db.flush()
        ids.append(posting.id)
        db.add(
            JobPostingSubfield(
                posting_id=posting.id,
                subfield_id=subfield_id,
                region=region,
                tier=tier,
                source_query=f"{subfield_id} query",
            )
        )
        if extracted and skill_ids:
            for sid in skill_ids:
                db.add(JobPostingSkill(posting_id=posting.id, skill_id=sid))
    db.commit()
    return ids


def _track(client: TestClient, profile_id: str, path_id: str = "qec_engineer") -> None:
    res = client.put(f"/api/v1/profiles/{profile_id}/chosen-path", json={"path_id": path_id})
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------
# Tests 20, 10, 12, 11: chosen-path and seen behavior
# ---------------------------------------------------------------------------


def test_put_chosen_path_valid_switch_unknown(client: TestClient) -> None:
    """Test 20: valid ok; switching ok; unknown path -> 422 invalid_path."""
    profile_id = _create(client)
    res_valid = client.put(
        f"/api/v1/profiles/{profile_id}/chosen-path", json={"path_id": "qec_engineer"}
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["chosen_path_id"] == "qec_engineer"

    res_switch = client.put(
        f"/api/v1/profiles/{profile_id}/chosen-path", json={"path_id": "hardware_engineer"}
    )
    assert res_switch.status_code == 200
    assert res_switch.json()["chosen_path_id"] == "hardware_engineer"

    profile = client.get(f"/api/v1/profiles/{profile_id}").json()
    assert profile["chosen_path_id"] == "hardware_engineer"

    res_unknown = client.put(
        f"/api/v1/profiles/{profile_id}/chosen-path", json={"path_id": "not_a_path"}
    )
    assert res_unknown.status_code == 422
    assert res_unknown.json()["error"]["code"] == "invalid_path"

    res_ghost_profile = client.put(
        "/api/v1/profiles/00000000-0000-0000-0000-000000000000/chosen-path",
        json={"path_id": "qec_engineer"},
    )
    assert res_ghost_profile.status_code == 404


def test_new_profile_has_last_seen_at_null(client: TestClient, db_session: Session) -> None:
    """Test 10 (prerequisite b): POST /profiles leaves last_seen_at NULL."""
    profile_id = _create(client)
    res = client.get(f"/api/v1/profiles/{profile_id}")
    body = res.json()

    from app.models import Profile

    profile = db_session.get(Profile, profile_id)
    db_session.refresh(profile)
    assert profile.last_seen_at is None
    assert "last_seen_at" not in body  # the profile projection doesn't leak it


def test_post_seen_sets_last_seen_then_no_new_items(
    client: TestClient, db_session: Session
) -> None:
    """Test 12: /seen sets last_seen_at; next GET has is_new=false everywhere
    and first_visit=false; equal timestamps are strictly not-new (test 8)."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)

    seen_at = utc_now()
    _seed_postings(db_session, "qec", first_seen=seen_at, count=2, extracted=True)

    seen_res = tracker_service.mark_seen(db_session, profile_id, now=lambda: seen_at)
    assert seen_res.last_seen_at == seen_at

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    assert feed["first_visit"] is False
    assert feed["last_seen_at"] == seen_at.isoformat()
    # first_seen == last_seen is NOT new (strict comparison, test 8).
    assert all(item["is_new"] is False for item in feed["items"])


def test_get_opportunities_never_touches_last_seen(client: TestClient, db_session: Session) -> None:
    """Test 11: two GETs leave last_seen_at NULL/unchanged."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", count=3)

    first = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    second = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    assert first["last_seen_at"] is None
    assert second["last_seen_at"] is None
    assert first["first_visit"] is True


# ---------------------------------------------------------------------------
# Tests 8, 9: is_new semantics
# ---------------------------------------------------------------------------


def test_is_new_strict_after_last_seen(client: TestClient, db_session: Session) -> None:
    """Test 8: only postings with first_seen_at strictly after last_seen_at are new."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)

    t0 = utc_now()
    _seed_postings(db_session, "qec", count=1, first_seen=t0, title_prefix="Old")
    later = datetime(
        t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second + 10 if t0.second < 50 else 1
    )
    _seed_postings(db_session, "qec", count=1, first_seen=later, title_prefix="Fresher")

    tracker_service.mark_seen(db_session, profile_id, now=lambda: t0)
    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    by_title = {item["title"]: item for item in feed["items"]}
    assert by_title["Old qec 0"]["is_new"] is False  # equal to last_seen -> not new
    assert by_title["Fresher qec 0"]["is_new"] is True


def test_first_visit_is_new_everywhere(client: TestClient, db_session: Session) -> None:
    """Test 9: last_seen NULL -> is_new true for all + first_visit true."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", count=2)

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    assert feed["first_visit"] is True
    assert len(feed["items"]) == 2
    assert all(item["is_new"] for item in feed["items"])


# ---------------------------------------------------------------------------
# Tests 13, 14, 15, 16: filtering
# ---------------------------------------------------------------------------


def test_region_filter_isolates_rows(client: TestClient, db_session: Session) -> None:
    """Test 13: global and india rows do not leak across regions."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", region="global", title_prefix="G")
    _seed_postings(db_session, "qec", region="india", title_prefix="I")

    g = client.get(f"/api/v1/profiles/{profile_id}/opportunities?region=global").json()
    i = client.get(f"/api/v1/profiles/{profile_id}/opportunities?region=india").json()
    assert {item["title"].split()[0] for item in g["items"]} == {"G"}
    assert {item["title"].split()[0] for item in i["items"]} == {"I"}


def test_internship_filter(client: TestClient, db_session: Session) -> None:
    """Test 14: internship=true returns only internships; false only non-internships."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", count=2, title_prefix="Job")
    _seed_postings(db_session, "qec", count=1, internship=True, title_prefix="Intern")

    only_interns = client.get(f"/api/v1/profiles/{profile_id}/opportunities?internship=true").json()
    assert {item["title"].split()[0] for item in only_interns["items"]} == {"Intern"}
    only_jobs = client.get(f"/api/v1/profiles/{profile_id}/opportunities?internship=false").json()
    assert {item["title"].split()[0] for item in only_jobs["items"]} == {"Job"}


def test_inactive_and_other_subfield_excluded(client: TestClient, db_session: Session) -> None:
    """Test 15: inactive postings and other subfields never appear."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", count=1, title_prefix="Live")
    _seed_postings(db_session, "qec", count=1, active=False, title_prefix="Dead")
    _seed_postings(db_session, "hardware", count=1, title_prefix="Other")

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    titles = {item["title"].split()[0] for item in feed["items"]}
    assert titles == {"Live"}


def test_extended_tier_appears(client: TestClient, db_session: Session) -> None:
    """Test 16: extended-tier-only postings are IN the feed."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", tier="extended", title_prefix="Ext")

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    assert {item["title"].split()[0] for item in feed["items"]} == {"Ext"}


# ---------------------------------------------------------------------------
# Tests 17, 18, 19: ordering, pagination, guards
# ---------------------------------------------------------------------------


def test_ordering_match_desc_nulls_last(client: TestClient, db_session: Session) -> None:
    """Test 17: match desc -> nulls last -> first_seen desc -> id (deterministic)."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    assert (
        client.put(
            f"/api/v1/profiles/{profile_id}/skills", json={"skill_ids": ["python"]}
        ).status_code
        == 200
    )

    # readiness for qec = 0 (all "not sure"), match = 60*overlap:
    # P100 overlap 1.0 -> 60; P20 overlap 0.2 -> 12.
    t0 = utc_now()
    _seed_postings(
        db_session, "qec", first_seen=t0, extracted=True, skill_ids=["python"], title_prefix="P100"
    )
    _seed_postings(
        db_session,
        "qec",
        first_seen=t0,
        extracted=True,
        skill_ids=["python", "qiskit", "stim", "rust", "cirq"],
        title_prefix="P20",
    )
    _seed_postings(
        db_session, "qec", title_prefix="Unextracted"
    )  # pending -> match None (nulls last)

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    ordered = [item["title"].split()[0] for item in feed["items"]]
    matches = [item["match"] for item in feed["items"]]
    assert ordered[:2] == ["P100", "P20"]  # 60 > 12 match
    assert matches[:2] == [60.0, 12.0]
    assert all(m is None for m in matches[2:])  # nulls last


def test_pagination_disjoint_and_complete(client: TestClient, db_session: Session) -> None:
    """Test 18: total independent of paging; pages disjoint, cover everything."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)
    _seed_postings(db_session, "qec", count=5)

    page1 = client.get(f"/api/v1/profiles/{profile_id}/opportunities?limit=2&offset=0").json()
    page2 = client.get(f"/api/v1/profiles/{profile_id}/opportunities?limit=2&offset=2").json()
    page3 = client.get(f"/api/v1/profiles/{profile_id}/opportunities?limit=2&offset=4").json()
    assert page1["total"] == 5
    ids_p1 = {i["posting_id"] for i in page1["items"]}
    ids_p2 = {i["posting_id"] for i in page2["items"]}
    ids_p3 = {i["posting_id"] for i in page3["items"]}
    assert not (ids_p1 & ids_p2) and not (ids_p2 & ids_p3)
    assert len(ids_p1 | ids_p2 | ids_p3) == 5


def test_opportunity_guards_409(client: TestClient, db_session: Session) -> None:
    """Test 19: 409 path_required without a path; 409 assessment_required without diagnostic."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)

    res_no_path = client.get(f"/api/v1/profiles/{profile_id}/opportunities")
    assert res_no_path.status_code == 409
    assert res_no_path.json()["error"]["code"] == "path_required"

    _track(client, profile_id)
    other = _create(client)
    other_track = client.put(
        f"/api/v1/profiles/{other}/chosen-path", json={"path_id": "qec_engineer"}
    )
    assert other_track.status_code == 200
    res_no_assessment = client.get(f"/api/v1/profiles/{other}/opportunities")
    assert res_no_assessment.status_code == 409
    assert res_no_assessment.json()["error"]["code"] == "assessment_required"


def test_match_and_matched_skills_flow(db_session: Session, client: TestClient) -> None:
    """End-to-end: declared skills drive match and matched_skills names."""
    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    # Declare python; readiness qec = 0 (all not-sure answers) -> match=60.
    put = client.put(f"/api/v1/profiles/{profile_id}/skills", json={"skill_ids": ["python"]})
    assert put.status_code == 200
    _track(client, profile_id)
    _seed_postings(
        db_session,
        "qec",
        extracted=True,
        skill_ids=["python", "qiskit"],
        title_prefix="Matched",
    )

    feed = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    item = feed["items"][0]
    assert item["match"] == pytest.approx(30.0)  # overlap 0.5 * 60 + ready 0
    assert item["matched_skills"] == ["Python"]


# ---------------------------------------------------------------------------
# Tests 22-25 (snapshot/trend/refresh-status via tracker service)
# ---------------------------------------------------------------------------


def test_trend_series_ordered_and_filtered(client: TestClient, db_session: Session) -> None:
    """Test 24: ordered ascending, region-filtered, 404 unknown, [] when none."""
    from datetime import date

    tracker_service.upsert_day_snapshot_for_testing(
        db_session, "qec", "global", date(2026, 10, 1), active=5, new=2, internships=1
    )
    tracker_service.upsert_day_snapshot_for_testing(
        db_session, "qec", "global", date(2026, 10, 2), active=7, new=3, internships=1
    )
    tracker_service.upsert_day_snapshot_for_testing(
        db_session, "qec", "india", date(2026, 10, 2), active=2, new=0, internships=0
    )

    series = client.get("/api/v1/pulse/qec/trend?region=global").json()
    assert [p["date"] for p in series] == ["2026-10-01", "2026-10-02"]
    assert series[0] == {"date": "2026-10-01", "active": 5, "new": 2, "internships": 1}

    india = client.get("/api/v1/pulse/qec/trend?region=india").json()
    assert [p["date"] for p in india] == ["2026-10-02"]

    res_unknown = client.get("/api/v1/pulse/not_a_subfield/trend")
    assert res_unknown.status_code == 404

    empty = (
        client.get("/api/v1/pulse/arduino/trend").json()
        if False
        else client.get("/api/v1/pulse/algorithms/trend").json()
    )
    assert empty == []


def test_snapshot_unique_re_run_updates(client: TestClient, db_session: Session) -> None:
    """Test 22: one row per (subfield, region, date); re-run updates not duplicates."""
    from datetime import date

    tracker_service.upsert_day_snapshot_for_testing(
        db_session, "qec", "global", date(2026, 10, 1), active=3, new=1, internships=0
    )
    tracker_service.upsert_day_snapshot_for_testing(
        db_session, "qec", "global", date(2026, 10, 1), active=9, new=2, internships=1
    )
    rows = list(db_session.query(PulseSnapshot).filter_by(subfield_id="qec", region="global"))
    assert len(rows) == 1
    assert rows[0].active_postings == 9


def test_new_postings_counts_only_that_day(client: TestClient, db_session: Session) -> None:
    """Test 23: new_postings counts postings whose first_seen falls on the date."""
    from datetime import timedelta

    yesterday = utc_now() - timedelta(days=2)
    _seed_postings(db_session, "qec", count=1, first_seen=yesterday, title_prefix="Old")
    _seed_postings(db_session, "qec", count=1, title_prefix="Fresh")

    from app.services import ingestion_service

    ingestion_service._upsert_pulse_snapshot(db_session, "qec", "global", utc_now(), utc_now())
    # In production refresh_jobs commits right after this helper; mirror that
    # (the session is configured autoflush=False, matching the real setup).
    db_session.commit()
    rows = db_session.scalars(
        select(PulseSnapshot).where(
            PulseSnapshot.subfield_id == "qec", PulseSnapshot.region == "global"
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.snapshot_date == utc_now().date()
    assert row.new_postings == 1  # only "Fresh" was first seen today
    assert row.active_postings == 2


def test_refresh_status_latest_per_kind(client: TestClient, db_session: Session) -> None:
    """Test 25: latest run per kind; null kinds; error text carries no secrets."""
    from datetime import datetime

    db_session.add(
        RefreshRun(
            kind="jobs",
            mode="daily",
            status="done",
            serpapi_calls=3,
            finished_at=datetime(2026, 10, 1, 3, 0, 0),
            details={"region": "global", "postings_new": 4},
        )
    )
    db_session.add(
        RefreshRun(
            kind="jobs",
            mode="bootstrap",
            status="failed",
            serpapi_calls=1,
            finished_at=datetime(2026, 10, 2, 3, 0, 0),
            error="serpapi returned 500 for query qec",
            details={"region": "global"},
        )
    )
    db_session.add(
        RefreshRun(
            kind="scholar",
            mode="weekly",
            status="done",
            serpapi_calls=6,
            finished_at=datetime(2026, 10, 2, 5, 0, 0),
        )
    )
    db_session.commit()

    body = client.get("/api/v1/meta/refresh-status").json()
    assert body["jobs"]["status"] == "failed"  # latest by started time
    assert body["jobs"]["serpapi_calls"] == 1
    assert "serpapi 500" in body["jobs"]["error"] or "500" in body["jobs"]["error"]
    assert body["scholar"]["status"] == "done"
    assert body["extraction"] is None  # never ran
    # No key/token material in any error text.
    for kind in ("jobs", "scholar", "extraction"):
        entry = body[kind]
        if entry and entry.get("error"):
            assert "SERPAPI_API_KEY" not in entry["error"]
            assert "sk-" not in entry["error"]


def test_last_refreshed_at_in_feed(client: TestClient, db_session: Session) -> None:
    """last_refreshed_at comes from the region's latest successful jobs run."""
    from datetime import datetime

    profile_id = _create(client)
    _take_diagnostic(client, profile_id)
    _track(client, profile_id)

    assert (
        client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()["last_refreshed_at"]
        is None
    )
    db_session.add(
        RefreshRun(
            kind="jobs",
            mode="daily",
            status="done",
            serpapi_calls=2,
            finished_at=datetime(2026, 10, 3, 3, 0, 0),
            details={"region": "global"},
        )
    )
    db_session.commit()
    body = client.get(f"/api/v1/profiles/{profile_id}/opportunities").json()
    assert body["last_refreshed_at"] is not None
