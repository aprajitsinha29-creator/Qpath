"""Endpoint tests with TestClient against a temp DB (plan 1.5/1.7).

Covers the Phase 1 API surface: taxonomy, pulse cards, posting lists, SerpApi
activity, and the admin refresh endpoint (token enforcement + fixture-mode
refresh twice → zero new postings the second time). Admin refreshes run in
fixture mode with per-test fixture dirs — never the live API (hard rule).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
