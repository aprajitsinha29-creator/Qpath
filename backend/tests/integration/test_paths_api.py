"""Integration tests for Phase 4 path matcher service and endpoints (plan 4.7).

Runs against the temporary SQLite DB using TestClient and FakeStructuredLLM
(never real network, never live Gemini or SerpApi — AGENTS.md 3.5.1 / 3.7.1).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_structured_llm_optional
from app.core.clock import utc_now
from app.core.errors import GeminiDailyQuotaExhausted, LLMOutputError
from app.integrations.gemini.client import FakeStructuredLLM
from app.integrations.gemini.schemas import PathExplanationItem, PathExplanationsBatch
from app.models import (
    JobPosting,
    JobPostingSkill,
    JobPostingSubfield,
    RefreshRun,
)

pytestmark = [
    pytest.mark.usefixtures("_seed_reference_data"),
    pytest.mark.usefixtures("allow_unverified"),
]

SCORED_SUBFIELDS = ["qec", "hardware", "software", "algorithms", "qml", "crypto_net"]


@pytest.fixture()
def allow_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve unverified (placeholder) questions in these tests, like dev .env."""
    monkeypatch.setenv("ALLOW_UNVERIFIED_QUESTIONS", "true")


def _take_diagnostic(
    client: TestClient, profile_id: str, interests: dict[str, int] | None = None
) -> int:
    """Helper: submit a valid diagnostic for profile_id and return assessment_id."""
    questions = client.get("/api/v1/quiz").json()["questions"]
    if interests is None:
        interests = {subfield: 3 for subfield in SCORED_SUBFIELDS}
    # Answer the first question correctly or "Not sure" for simplicity
    answers = [{"question_id": q["id"], "selected_index": None} for q in questions]
    res = client.post(
        f"/api/v1/profiles/{profile_id}/assessment",
        json={"interests": interests, "answers": answers},
    )
    assert res.status_code == 200
    return int(res.json()["assessment_id"])


def _seed_postings(
    db: Session,
    subfield_id: str,
    count: int,
    *,
    region: str = "global",
    tier: str = "core",
    requires_phd: bool = False,
    skill_ids: list[str] | None = None,
) -> None:
    """Seed test postings linked to a subfield."""
    now = utc_now()
    for i in range(count):
        posting = JobPosting(
            dedupe_key=f"posting_{subfield_id}_{tier}_{i}",
            title=f"{subfield_id.capitalize()} Engineer {i}",
            company="Quantum Corp",
            location="Remote",
            is_active=True,
            is_internship=(i == 0),
            requires_phd=requires_phd,
            extraction_status="done" if skill_ids else "pending",
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(posting)
        db.flush()

        link = JobPostingSubfield(
            posting_id=posting.id,
            subfield_id=subfield_id,
            region=region,
            tier=tier,
            source_query=f"{subfield_id} query",
        )
        db.add(link)

        if skill_ids:
            for sid in skill_ids:
                db.add(JobPostingSkill(posting_id=posting.id, skill_id=sid))
    db.commit()


# ---------------------------------------------------------------------------
# Step 4.3 tests: paths_service and GET /profiles/{id}/paths
# ---------------------------------------------------------------------------


def test_ranked_paths_requires_assessment_409(client: TestClient) -> None:
    """GET /paths and POST /paths/explanations both raise 409 if no assessment exists."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]

    res_get = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert res_get.status_code == 409
    assert res_get.json()["error"]["code"] == "assessment_required"

    res_post = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
    assert res_post.status_code == 409
    assert res_post.json()["error"]["code"] == "assessment_required"


def test_ranked_paths_unknown_profile_404(client: TestClient) -> None:
    """Unknown profile UUID returns 404."""
    ghost = "00000000-0000-0000-0000-000000000000"
    res = client.get(f"/api/v1/profiles/{ghost}/paths")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_ranked_paths_returns_six_ranked_paths_with_breakdown(
    client: TestClient, db_session: Session
) -> None:
    """GET /paths returns 6 paths, top 3 flagged, breakdown matching math."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _seed_postings(db_session, "qec", 10, skill_ids=["stim"])
    _take_diagnostic(
        client, profile_id, interests={s: 5 if s == "qec" else 1 for s in SCORED_SUBFIELDS}
    )

    res = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert res.status_code == 200
    data = res.json()
    assert data["profile_id"] == profile_id
    paths = data["paths"]
    assert len(paths) == 6

    # Verify ranks are 1..6 and sorted by score descending
    ranks = [p["rank"] for p in paths]
    scores = [p["score"] for p in paths]
    assert ranks == [1, 2, 3, 4, 5, 6]
    assert scores == sorted(scores, reverse=True)

    # Top 3 boolean flag
    assert [p["is_top3"] for p in paths] == [True, True, True, False, False, False]

    # QEC had high interest and postings -> should be rank 1
    top = paths[0]
    assert top["subfield_id"] == "qec"
    assert top["path_id"] == "qec_engineer"
    assert top["breakdown"]["interest"] == 100.0
    assert top["breakdown"]["weights"] == {"interest": 40.0, "demand": 30.0, "readiness": 30.0}
    assert top["low_data"] is False
    assert top["evidence"]["active_postings"] == 10
    assert top["evidence"]["internship_postings"] == 1
    assert len(top["evidence"]["top_skills"]) == 1
    assert top["evidence"]["top_skills"][0]["skill_id"] == "stim"
    assert top["explanation"] is None  # GET returns null explanation when uncached


def test_paths_evidence_assembly_core_postings_only(
    client: TestClient, db_session: Session
) -> None:
    """Demand evidence counts core postings only, not extended queries."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    # Seed 5 core and 15 extended postings for hardware
    _seed_postings(db_session, "hardware", 5, tier="core")
    _seed_postings(db_session, "hardware", 15, tier="extended")
    _take_diagnostic(client, profile_id)

    res = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert res.status_code == 200
    hw_path = next(p for p in res.json()["paths"] if p["subfield_id"] == "hardware")
    # active_postings is 5 (core only)
    assert hw_path["evidence"]["active_postings"] == 5
    assert hw_path["low_data"] is True  # 5 < 8


def test_paths_saturation_flag_and_note(client: TestClient, db_session: Session) -> None:
    """Bootstrap page-cap subfields set saturated flags and saturation_note."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    # Add a bootstrap refresh run with 4 page-capped subfields
    capped = ["qec", "hardware", "software", "qml"]
    run = RefreshRun(
        kind="jobs",
        mode="bootstrap",
        status="completed",
        details={"region": "global", "page_cap_subfields": capped},
    )
    db_session.add(run)
    db_session.commit()

    res = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert res.status_code == 200
    data = res.json()
    assert data["saturation_note"] is not None
    assert "4 of 6 subfields" in data["saturation_note"]
    for path in data["paths"]:
        if path["subfield_id"] in capped:
            assert path["saturated"] is True
        else:
            assert path["saturated"] is False


# ---------------------------------------------------------------------------
# Step 4.4 & 4.5 tests: explanation_service and POST /explanations
# ---------------------------------------------------------------------------


def _valid_batch_for_paths(paths: list[dict]) -> PathExplanationsBatch:
    """Build a valid LLM batch echoing exact numbers from the path evidence."""
    items = []
    for p in paths:
        # Use exact numbers: rank, active_postings, interest
        active = p["evidence"]["active_postings"]
        rank = p["rank"]
        interest = p["breakdown"]["interest"]
        items.append(
            PathExplanationItem(
                path_id=p["path_id"],
                headline=f"Rank {rank} career path {p['title']}",
                reasons=[
                    f"Your interest is {interest}% from diagnostic.",
                    f"Subfield has {active} active job listings.",
                    "Demand weight is 30% in overall score.",
                ],
                caveat="Counts reflect live sampled job postings.",
                next_step="Review the required skills.",
            )
        )
    return PathExplanationsBatch(explanations=items)


def test_post_explanations_batched_generates_and_caches(client: TestClient) -> None:
    """POST /paths/explanations makes ONE batched call; subsequent GET/POST hit cache."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    # Fetch initial paths to know path_ids
    paths_data = client.get(f"/api/v1/profiles/{profile_id}/paths").json()["paths"]
    batch_resp = _valid_batch_for_paths(paths_data)

    fake_llm = FakeStructuredLLM([batch_resp])
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        # First call: calls LLM
        res_post = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res_post.status_code == 200
        post_paths = res_post.json()["paths"]
        assert len(post_paths) == 6
        for p in post_paths:
            assert p["explanation"] is not None
            assert p["explanation"]["generated_by"] == "llm"
        assert fake_llm.call_count == 1

        # Second call to POST /paths/explanations: hits cache, no second LLM call!
        res_post2 = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res_post2.status_code == 200
        assert fake_llm.call_count == 1  # Still 1!

        # GET /paths now returns cached explanations
        res_get = client.get(f"/api/v1/profiles/{profile_id}/paths")
        assert res_get.status_code == 200
        for p in res_get.json()["paths"]:
            assert p["explanation"] is not None
            assert p["explanation"]["generated_by"] == "llm"
        assert fake_llm.call_count == 1
    finally:
        client.app.dependency_overrides.clear()


def test_post_single_path_explanation_endpoint(client: TestClient) -> None:
    """POST /profiles/{id}/paths/{path_id}/explanation generates batch and returns single item."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    paths_data = client.get(f"/api/v1/profiles/{profile_id}/paths").json()["paths"]
    batch_resp = _valid_batch_for_paths(paths_data)
    fake_llm = FakeStructuredLLM([batch_resp])
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        res = client.post(f"/api/v1/profiles/{profile_id}/paths/qec_engineer/explanation")
        assert res.status_code == 200
        exp = res.json()
        assert exp["headline"].startswith("Rank")
        assert exp["generated_by"] == "llm"
        assert len(exp["reasons"]) == 3
        assert fake_llm.call_count == 1

        # Asking for another path uses the cache from the same batch
        res2 = client.post(f"/api/v1/profiles/{profile_id}/paths/hardware_engineer/explanation")
        assert res2.status_code == 200
        assert res2.json()["generated_by"] == "llm"
        assert fake_llm.call_count == 1
    finally:
        client.app.dependency_overrides.clear()


def test_cache_invalidation_when_assessment_changes(client: TestClient) -> None:
    """When a new diagnostic is submitted, evidence changes and cache invalidates."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id, interests={s: 1 for s in SCORED_SUBFIELDS})

    paths1 = client.get(f"/api/v1/profiles/{profile_id}/paths").json()["paths"]
    batch1 = _valid_batch_for_paths(paths1)

    fake_llm = FakeStructuredLLM([batch1, batch1])  # two responses ready
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        # Generate explanations for first assessment
        client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert fake_llm.call_count == 1

        # Retake diagnostic with different interests
        _take_diagnostic(client, profile_id, interests={s: 5 for s in SCORED_SUBFIELDS})

        paths2 = client.get(f"/api/v1/profiles/{profile_id}/paths").json()["paths"]
        batch2 = _valid_batch_for_paths(paths2)
        fake_llm.canned = [batch2]

        # GET /paths for the new assessment should have explanation: None initially
        res_get_new = client.get(f"/api/v1/profiles/{profile_id}/paths")
        assert all(p["explanation"] is None for p in res_get_new.json()["paths"])

        # POST /explanations generates fresh explanations for the new assessment
        client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert fake_llm.call_count == 2
    finally:
        client.app.dependency_overrides.clear()


def test_template_fallback_on_llm_error(client: TestClient) -> None:
    """On LLMOutputError or exception, service falls back to templates without error."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    fake_llm = FakeStructuredLLM([LLMOutputError("Gemini 500 error")])
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        res = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res.status_code == 200
        for p in res.json()["paths"]:
            exp = p["explanation"]
            assert exp is not None
            assert exp["generated_by"] == "template"
            assert exp["model"] is None
    finally:
        client.app.dependency_overrides.clear()


def test_template_fallback_on_quota_exhausted_no_retry(client: TestClient) -> None:
    """On GeminiDailyQuotaExhausted, immediately degrades to templates."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    fake_llm = FakeStructuredLLM([GeminiDailyQuotaExhausted("Rate limit exceeded")])
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        res = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res.status_code == 200
        for p in res.json()["paths"]:
            assert p["explanation"]["generated_by"] == "template"
    finally:
        client.app.dependency_overrides.clear()


def test_number_validator_rejection_falls_back_to_template(client: TestClient) -> None:
    """An item citing a hallucinated number (not in evidence) is rejected & templated."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    paths_data = client.get(f"/api/v1/profiles/{profile_id}/paths").json()["paths"]
    batch = _valid_batch_for_paths(paths_data)

    # Poison qec_engineer with an ungrounded salary / number: 99999
    for item in batch.explanations:
        if item.path_id == "qec_engineer":
            item.reasons[0] = "Average salary is 99999 USD per year."

    fake_llm = FakeStructuredLLM([batch])
    client.app.dependency_overrides[get_structured_llm_optional] = lambda: fake_llm

    try:
        res = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res.status_code == 200
        paths = {p["path_id"]: p for p in res.json()["paths"]}

        # qec_engineer should be downgraded to template
        assert paths["qec_engineer"]["explanation"]["generated_by"] == "template"
        # Others with valid numbers should remain "llm"
        assert paths["hardware_engineer"]["explanation"]["generated_by"] == "llm"
    finally:
        client.app.dependency_overrides.clear()


def test_unconfigured_llm_returns_template_cleanly(client: TestClient) -> None:
    """When get_structured_llm_optional returns None, templates are returned."""
    profile_id = client.post("/api/v1/profiles").json()["profile_id"]
    _take_diagnostic(client, profile_id)

    client.app.dependency_overrides[get_structured_llm_optional] = lambda: None

    try:
        res = client.post(f"/api/v1/profiles/{profile_id}/paths/explanations")
        assert res.status_code == 200
        for p in res.json()["paths"]:
            assert p["explanation"]["generated_by"] == "template"
    finally:
        client.app.dependency_overrides.clear()
