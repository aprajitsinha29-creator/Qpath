"""Endpoint tests with TestClient against a temp DB (plan 1.5/1.7).

Covers the Phase 1 API surface: taxonomy, pulse cards, posting lists, SerpApi
activity, and the admin refresh endpoint (token enforcement + fixture-mode
refresh twice → zero new postings the second time). Admin refreshes run in
fixture mode with per-test fixture dirs — never the live API (hard rule).

Phase 2 step 2.6 adds the GET /pulse/{subfield_id} detail endpoint tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.models import JobPosting, JobPostingSkill, PaperSnapshot, ResearchTheme
from tests.conftest import write_serpapi_fixture
from tests.integration.test_ingestion import job

pytestmark = pytest.mark.usefixtures("_seed_reference_data")

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


@pytest.fixture()
def api_client(
    client: TestClient, fixture_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """TestClient whose settings carry a known admin token and the fixture dir.

    Settings are cached per process; values are injected via env before any
    request builds a client (the _clean_env autouse fixture handles cache
    clearing around each test).
    """
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    # The admin endpoint builds its SerpApiClient from cached Settings, so
    # the per-test fixture dir must flow through config (not client kwargs).
    monkeypatch.setenv("SERPAPI_FIXTURE_DIR", str(fixture_dir))
    from app.core.config import get_settings

    get_settings.cache_clear()
    return client


def _seed_qec_fixture(fixture_dir: Path) -> None:
    """Record one global page-1 QEC fixture with two postings."""
    write_serpapi_fixture(
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


# ------------------------------------------------------------------------ reads


def test_taxonomy_returns_subfields_concepts_paths(api_client: TestClient) -> None:
    """GET /taxonomy returns the seeded reference data with expected counts."""
    response = api_client.get("/api/v1/taxonomy")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["subfields"]) == 7  # 6 scored + foundations
    assert len(payload["career_paths"]) == 6
    assert payload["subfields"][0]["id"] == "foundations"
    assert payload["subfields"][0]["is_scored"] is False


def test_get_pulse_returns_six_cards(api_client: TestClient) -> None:
    """GET /pulse returns exactly six cards (one per scored subfield)."""
    response = api_client.get("/api/v1/pulse")

    assert response.status_code == 200
    cards = response.json()
    assert len(cards) == 6
    assert {c["subfield_id"] for c in cards} == {
        "qec",
        "hardware",
        "software",
        "algorithms",
        "qml",
        "crypto_net",
    }
    for card in cards:
        assert card["active_postings"] == 0  # nothing ingested yet
        assert card["new_this_week"] is None
        assert card["low_data"] is True


def test_get_pulse_region_validation(api_client: TestClient) -> None:
    """Unknown regions are rejected with 422 by the query-param pattern."""
    assert api_client.get("/api/v1/pulse", params={"region": "global"}).status_code == 200
    assert api_client.get("/api/v1/pulse", params={"region": "india"}).status_code == 200
    assert api_client.get("/api/v1/pulse", params={"region": "mars"}).status_code == 422


def test_list_postings_endpoint_includes_snippet_and_pagination(
    api_client: TestClient, fixture_dir: Path
) -> None:
    """GET /pulse/{id}/postings returns items with snippets and a total."""
    _seed_qec_fixture(fixture_dir)
    refresh = api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "daily", "region": "global", "subfield_id": "qec"},
    )
    assert refresh.status_code == 200

    response = api_client.get("/api/v1/pulse/qec/postings", params={"limit": 1, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["title"] in {"QEC Engineer", "Decoder Scientist"}
    assert item["snippet"] is not None and len(item["snippet"]) <= 240
    assert item["apply_url"] is not None

    # Internship filter endpoint contract: none of the seeded jobs is one.
    internships = api_client.get("/api/v1/pulse/qec/postings", params={"internship": "true"})
    assert internships.status_code == 200
    assert internships.json()["total"] == 0


def test_list_postings_unknown_subfield_returns_404(api_client: TestClient) -> None:
    """Unknown subfield id maps to the shared error shape with 404."""
    response = api_client.get("/api/v1/pulse/nope/postings")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"


# ------------------------------------------------------------------------ meta


def test_serpapi_activity_lists_fixture_calls(api_client: TestClient, fixture_dir: Path) -> None:
    """GET /meta/serpapi-activity reflects mode and logged calls."""
    _seed_qec_fixture(fixture_dir)
    api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "daily", "region": "global", "subfield_id": "qec"},
    )

    response = api_client.get("/api/v1/meta/serpapi-activity")

    assert response.status_code == 200
    activity = response.json()
    assert activity["mode"] == "fixtures"
    assert activity["live_calls_today"] == 0
    assert activity["daily_cap"] > 0
    statuses = [call["status"] for call in activity["recent_calls"]]
    assert "ok" in statuses
    assert all(call["source"] == "fixture" for call in activity["recent_calls"])


# ----------------------------------------------------------------------- admin


def test_admin_refresh_rejects_missing_token(api_client: TestClient) -> None:
    """POST /admin/refresh/jobs without the header is 401 with the error shape."""
    response = api_client.post(
        "/api/v1/admin/refresh/jobs",
        json={"mode": "daily", "region": "global"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_admin_refresh_rejects_wrong_token(api_client: TestClient) -> None:
    """A wrong token is equally rejected (constant-time comparison)."""
    response = api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers={"X-Admin-Token": "wrong-token"},
        json={"mode": "daily", "region": "global"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_admin_refresh_bootstrap_twice_second_run_zero_new(
    api_client: TestClient, fixture_dir: Path
) -> None:
    """Plan acceptance check: refresh twice → second run reports zero new."""
    _seed_qec_fixture(fixture_dir)
    body = {"mode": "bootstrap", "region": "global"}

    first = api_client.post("/api/v1/admin/refresh/jobs", headers=ADMIN_HEADERS, json=body).json()
    second = api_client.post("/api/v1/admin/refresh/jobs", headers=ADMIN_HEADERS, json=body).json()

    assert first["postings_new"] == 2
    assert first["status"] == "done"
    # No extended/page-2 fixtures exist for this test's dir: the run ends
    # cleanly on FixtureMissingError (status done, no errors).
    assert second["postings_new"] == 0
    assert second["errors"] == []
    # Idempotency: total postings unchanged after the second run.
    pulse = api_client.get("/api/v1/pulse").json()
    qec = next(c for c in pulse if c["subfield_id"] == "qec")
    assert qec["active_postings"] == 2


def test_admin_refresh_rejects_invalid_body(api_client: TestClient) -> None:
    """Unknown mode/region values are rejected by the schema (422)."""
    response = api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "hourly", "region": "global"},
    )
    assert response.status_code == 422

    response = api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "daily", "region": "mars"},
    )
    assert response.status_code == 422


# ------------------------------------------------------------------------ Phase 2: detail endpoint


def _seed_and_extract_qec(
    api_client: TestClient, fixture_dir: Path, db_session: Session, serpapi_fixture_client
) -> None:
    """Bootstrap ingest + mark extracted with skills + add research themes."""
    write_serpapi_fixture(
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
    write_serpapi_fixture(
        fixture_dir,
        "fault tolerant quantum computing",
        "global_p1",
        {"jobs_results": [job("FTQC Architect", "PsiQuantum")]},
    )
    api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "bootstrap", "region": "global"},
    )

    # Mark extracted with skills (simulate extraction service)
    postings = list(db_session.scalars(select(JobPosting)))
    for i, p in enumerate(postings[:3]):
        p.extraction_status = "done"
        p.extraction_attempts = 0
        if i == 0:
            p.seniority = "mid"
            p.requires_phd = False
        elif i == 1:
            p.seniority = "intern"
            p.requires_phd = False
        else:
            p.seniority = "senior"
            p.requires_phd = True

    for p in postings[:2]:
        db_session.add(JobPostingSkill(posting_id=p.id, skill_id="python"))
        db_session.add(JobPostingSkill(posting_id=p.id, skill_id="qiskit"))
    db_session.add(JobPostingSkill(posting_id=postings[2].id, skill_id="python"))
    db_session.add(JobPostingSkill(posting_id=postings[2].id, skill_id="stim"))
    db_session.add(JobPostingSkill(posting_id=postings[3].id, skill_id="cpp"))
    db_session.commit()

    # Add research theme batch
    now = utc_now()
    batch_id = "api-test-batch"
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


def test_get_subfield_detail_returns_full_payload(
    api_client: TestClient, fixture_dir: Path, db_session: Session, serpapi_fixture_client
) -> None:
    """GET /pulse/{id} returns card + skills + mix + coverage + themes + postings."""
    _seed_and_extract_qec(api_client, fixture_dir, db_session, serpapi_fixture_client)

    response = api_client.get("/api/v1/pulse/qec", params={"region": "global"})
    assert response.status_code == 200
    detail = response.json()

    # Card fields present
    assert detail["subfield_id"] == "qec"
    assert detail["active_postings"] == 3
    assert detail["extra_postings"] == 1
    assert detail["internship_postings"] == 1
    assert detail["low_data"] is True

    # Intelligence fields
    assert len(detail["top_skills"]) == 3
    shares = {s["skill_id"]: s["share"] for s in detail["top_skills"]}
    assert shares["python"] == 1.0
    assert abs(shares["qiskit"] - 2 / 3) < 0.001
    assert abs(shares["stim"] - 1 / 3) < 0.001

    assert detail["seniority_mix"]["mid"] == 1
    assert detail["seniority_mix"]["intern"] == 1
    assert detail["seniority_mix"]["senior"] == 1
    assert detail["seniority_mix"]["unknown"] == 1
    assert detail["phd_share"] == 1 / 3

    assert abs(detail["extraction_coverage"] - 0.75) < 0.001

    assert len(detail["themes"]) == 1
    assert detail["themes"][0]["label"] == "Test Theme"
    assert len(detail["themes"][0]["papers"]) == 1

    # Postings list
    assert len(detail["postings"]) == 4


def test_get_subfield_detail_unknown_returns_404(api_client: TestClient) -> None:
    """Unknown subfield id → 404 with error shape."""
    response = api_client.get("/api/v1/pulse/nope", params={"region": "global"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_subfield_detail_region_validation(api_client: TestClient) -> None:
    """Invalid region rejected by query-param pattern (422)."""
    assert api_client.get("/api/v1/pulse/qec", params={"region": "global"}).status_code == 200
    assert api_client.get("/api/v1/pulse/qec", params={"region": "india"}).status_code == 200
    assert api_client.get("/api/v1/pulse/qec", params={"region": "mars"}).status_code == 422


def test_pulse_cards_include_top_skills_and_themes(
    api_client: TestClient, fixture_dir: Path, db_session: Session, serpapi_fixture_client
) -> None:
    """Phase 2: pulse cards include additive top_skills[:5] and themes[:3]."""
    _seed_and_extract_qec(api_client, fixture_dir, db_session, serpapi_fixture_client)

    response = api_client.get("/api/v1/pulse", params={"region": "global"})
    assert response.status_code == 200
    cards = {c["subfield_id"]: c for c in response.json()}

    qec = cards["qec"]
    # Additive fields with defaults (Phase 1 compatibility)
    assert "top_skills" in qec
    assert "themes" in qec
    assert len(qec["top_skills"]) == 3  # python, qiskit, stim
    assert len(qec["themes"]) == 1


def test_pulse_cards_empty_skills_themes_when_no_extraction(
    api_client: TestClient, fixture_dir: Path, serpapi_fixture_client
) -> None:
    """No extraction → empty lists (valid empty state, never error)."""
    write_serpapi_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {"jobs_results": [job("QEC Engineer", "Riverlane")]},
    )
    api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "bootstrap", "region": "global", "subfield_id": "qec"},
    )

    response = api_client.get("/api/v1/pulse", params={"region": "global"})
    cards = {c["subfield_id"]: c for c in response.json()}
    qec = cards["qec"]
    assert qec["top_skills"] == []
    assert qec["themes"] == []


def test_end_to_end_pulse_detail_pipeline(
    api_client: TestClient, fixture_dir: Path, db_session: Session, serpapi_fixture_client
) -> None:
    """End-to-end fixture test through jobs -> extraction -> scholar -> GET /pulse/{id}."""
    from app.api.deps import get_structured_llm
    from app.integrations.gemini.client import FakeStructuredLLM
    from app.integrations.gemini.schemas import (
        ExtractionBatch,
        PostingExtraction,
        Theme,
        ThemeSet,
    )
    from tests.integration.test_research import _scholar_payload, _write_scholar_fixture

    # 1. Write job fixtures
    write_serpapi_fixture(
        fixture_dir,
        "quantum error correction",
        "global_p1",
        {
            "jobs_results": [
                # "Senior" in the title backs the extraction batch's seniority
                # claim below (M-10 fix: claims persist only with text evidence).
                job(
                    "Senior QEC Engineer",
                    "Riverlane",
                    # "PhD required" backs the extraction batch's requires_phd
                    # claim below (M-10 fix: flags persist only with text evidence).
                    description="QEC role using Python and Qiskit. PhD required.",
                ),
            ]
        },
    )

    # 2. Write scholar fixture
    _write_scholar_fixture(fixture_dir, "quantum error correction", _scholar_payload(3))

    # 3. Ingest jobs via admin endpoint
    res_jobs = api_client.post(
        "/api/v1/admin/refresh/jobs",
        headers=ADMIN_HEADERS,
        json={"mode": "bootstrap", "region": "global", "subfield_id": "qec"},
    )
    assert res_jobs.status_code == 200

    # 4. Extract skills via admin endpoint with FakeStructuredLLM
    postings = list(db_session.scalars(select(JobPosting)))
    extraction_batch = ExtractionBatch(
        items=[
            PostingExtraction(
                posting_ref=str(p.id),
                skill_ids=["python", "qiskit"],
                unmapped_skills=[],
                seniority="senior",
                requires_phd=True,
                is_internship=False,
                primary_subfield_id="qec",
            )
            for p in postings
        ]
    )
    theme_set = ThemeSet(
        themes=[
            Theme(
                label="Surface Codes",
                summary="Surface codes and fault tolerance.",
                paper_indexes=[1],
            )
        ]
    )
    fake_llm = FakeStructuredLLM([extraction_batch, theme_set])
    api_client.app.dependency_overrides[get_structured_llm] = lambda: fake_llm

    try:
        res_extract = api_client.post(
            "/api/v1/admin/extract?limit=10",
            headers=ADMIN_HEADERS,
        )
        assert res_extract.status_code == 200
        assert res_extract.json()["done"] >= 1

        res_scholar = api_client.post(
            "/api/v1/admin/refresh/scholar",
            headers=ADMIN_HEADERS,
        )
        assert res_scholar.status_code == 200
        assert res_scholar.json()["subfields_with_themes"] >= 1
    finally:
        api_client.app.dependency_overrides.pop(get_structured_llm, None)

    # 5. Query subfield detail endpoint
    res_detail = api_client.get("/api/v1/pulse/qec", params={"region": "global"})
    assert res_detail.status_code == 200
    detail = res_detail.json()

    assert detail["subfield_id"] == "qec"
    assert detail["active_postings"] >= 1
    assert detail["extraction_coverage"] == 1.0
    assert len(detail["top_skills"]) == 2
    assert {s["skill_id"] for s in detail["top_skills"]} == {"python", "qiskit"}
    assert detail["seniority_mix"]["senior"] == 1
    assert detail["phd_share"] == 1.0
    assert len(detail["themes"]) == 1
    assert detail["themes"][0]["label"] == "Surface Codes"
    assert len(detail["themes"][0]["papers"]) == 1
    assert len(detail["postings"]) >= 1
