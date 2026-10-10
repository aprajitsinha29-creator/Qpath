"""Integration tests for declared skills and the skills vocabulary (carry-over).

Cut from Phase 4 and implemented per the task spec. Runs against the
temporary SQLite DB via TestClient — no DB mocks, no network (AGENTS.md 3.7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assessment, Profile

pytestmark = [pytest.mark.usefixtures("_seed_reference_data")]

VOCAB_FILE = Path(__file__).resolve().parents[2] / "app" / "data" / "skills_vocab.json"


def _create_profile(client: TestClient) -> str:
    """Helper: create a profile and return its id."""
    return client.post("/api/v1/profiles").json()["profile_id"]


def _put_skills(client: TestClient, profile_id: str, skill_ids: list[str]):
    """Helper: PUT declared skills; returns the response."""
    return client.put(f"/api/v1/profiles/{profile_id}/skills", json={"skill_ids": skill_ids})


def _profile_skill_ids(client: TestClient, profile_id: str) -> list[str]:
    """Helper: read declared_skills from GET /profiles/{id}."""
    profile = client.get(f"/api/v1/profiles/{profile_id}").json()
    return list(profile["declared_skills"])


# ---------------------------------------------------------------------------
# PUT /profiles/{id}/skills
# ---------------------------------------------------------------------------


def test_put_skills_replaces_existing_list(client: TestClient) -> None:
    """A second PUT replaces the first list entirely (no merging/union)."""
    profile_id = _create_profile(client)
    assert _put_skills(client, profile_id, ["python", "qiskit"]).status_code == 200
    assert _put_skills(client, profile_id, ["rust", "stim"]).status_code == 200
    assert _profile_skill_ids(client, profile_id) == ["rust", "stim"]


def test_put_skills_dedupes_keeping_first_seen_order(client: TestClient) -> None:
    """Duplicates are removed; the first occurrence fixes the position."""
    profile_id = _create_profile(client)
    res = _put_skills(client, profile_id, ["python", "qiskit", "python"])
    assert res.status_code == 200
    assert res.json()["declared_skills"] == ["python", "qiskit"]


def test_put_skills_empty_list_clears(client: TestClient) -> None:
    """An empty list is valid and clears previously declared skills."""
    profile_id = _create_profile(client)
    _put_skills(client, profile_id, ["python"])
    res = _put_skills(client, profile_id, [])
    assert res.status_code == 200
    assert res.json()["declared_skills"] == []


def test_put_skills_unknown_id_returns_422_and_writes_nothing(client: TestClient) -> None:
    """Unknown ids -> 422 invalid_skills with the ids named; list unchanged after."""
    profile_id = _create_profile(client)
    _put_skills(client, profile_id, ["python"])

    res = _put_skills(client, profile_id, ["python", "not_a_skill", "also_fake"])
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "invalid_skills"
    assert "not_a_skill" in body["error"]["message"]
    assert "also_fake" in body["error"]["message"]
    # Nothing was written — the previous list survives intact.
    assert _profile_skill_ids(client, profile_id) == ["python"]


def test_put_skills_unknown_profile_returns_not_found(client: TestClient) -> None:
    """The existing profile-not-found error is reused for the skills route."""
    res = _put_skills(client, "00000000-0000-0000-0000-000000000000", ["python"])
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_put_skills_rejects_missing_or_non_string_items(client: TestClient) -> None:
    """Malformed payloads fail closed at the boundary with the shared error shape."""
    profile_id = _create_profile(client)

    res_missing = client.put(
        f"/api/v1/profiles/{profile_id}/skills", json={"wrong_key": ["python"]}
    )
    assert res_missing.status_code == 422
    assert res_missing.json()["error"]["code"] == "validation_error"

    res_non_string = client.put(
        f"/api/v1/profiles/{profile_id}/skills", json={"skill_ids": ["python", 42]}
    )
    assert res_non_string.status_code == 422
    assert res_non_string.json()["error"]["code"] == "validation_error"

    res_not_list = client.put(f"/api/v1/profiles/{profile_id}/skills", json={"skill_ids": "python"})
    assert res_not_list.status_code == 422
    # Nothing was written by any of the rejected attempts.
    assert _profile_skill_ids(client, profile_id) == []


def test_put_skills_leaves_other_profile_fields_untouched(
    client: TestClient, db_session: Session
) -> None:
    """Only declared_skills changes: interests, timestamps, path, concepts, assessments."""
    profile_id = _create_profile(client)
    # Give the profile state that must survive the skills PUT untouched.
    profile = db_session.get(Profile, profile_id)
    profile.interests = {
        "qec": 4,
        "hardware": 2,
        "software": 3,
        "algorithms": 1,
        "qml": 2,
        "crypto_net": 5,
    }
    profile.chosen_path_id = "qec_engineer"
    profile.completed_concepts = ["superposition"]
    profile.declared_skills = ["stim"]
    old_last_seen = profile.last_seen_at
    db_session.add(Assessment(profile_id=profile_id, answers=[], scores={"qec": 60.0}))
    db_session.commit()
    still_there = db_session.scalars(select(Assessment).where(Assessment.profile_id == profile_id))
    assessment_count = len(list(still_there))
    interests_before = dict(profile.interests)

    res = _put_skills(client, profile_id, ["python", "qiskit"])
    assert res.status_code == 200

    fresh = db_session.get(Profile, profile_id)
    db_session.refresh(fresh)
    assert fresh.declared_skills == ["python", "qiskit"]
    assert fresh.interests == interests_before
    assert fresh.last_seen_at == old_last_seen
    assert fresh.chosen_path_id == "qec_engineer"
    assert fresh.completed_concepts == ["superposition"]
    kept = db_session.scalars(select(Assessment).where(Assessment.profile_id == profile_id))
    assert len(list(kept)) == assessment_count


# ---------------------------------------------------------------------------
# GET profile / GET skills
# ---------------------------------------------------------------------------


def test_get_profile_includes_declared_skills(client: TestClient) -> None:
    """The profile projection exposes declared_skills once they are set."""
    profile_id = _create_profile(client)
    before = client.get(f"/api/v1/profiles/{profile_id}").json()
    assert before["declared_skills"] == []  # additive field present from creation

    _put_skills(client, profile_id, ["python", "openqasm"])
    after = client.get(f"/api/v1/profiles/{profile_id}").json()
    assert after["declared_skills"] == ["python", "openqasm"]


def test_get_skills_returns_full_vocabulary(client: TestClient) -> None:
    """Every vocab row is served with the right fields, sorted by name."""
    expected_count = len(json.loads(VOCAB_FILE.read_text(encoding="utf-8")))
    res = client.get("/api/v1/skills")
    assert res.status_code == 200
    skills = res.json()  # bare list: [{id, name, aliases, subfield_ids}]
    assert len(skills) == expected_count

    names = [s["name"] for s in skills]
    assert names == sorted(names)
    for skill in skills:
        assert set(skill) == {"id", "name", "aliases", "subfield_ids"}
        assert isinstance(skill["aliases"], list)
        assert isinstance(skill["subfield_ids"], list)

    # Alias spot-check: the picker's alias search depends on this.
    pymatching = next(s for s in skills if s["id"] == "pymatching")
    assert "MWPM" in pymatching["aliases"]


# ---------------------------------------------------------------------------
# Ranking isolation
# ---------------------------------------------------------------------------


def test_declared_skills_do_not_change_ranked_paths(client: TestClient) -> None:
    """GET /paths is byte-identical before and after declaring skills."""
    profile_id = _create_profile(client)
    questions = client.get("/api/v1/quiz").json()["questions"]
    interests = {
        "qec": 3,
        "hardware": 3,
        "software": 3,
        "algorithms": 3,
        "qml": 3,
        "crypto_net": 3,
    }
    res_assessment = client.post(
        f"/api/v1/profiles/{profile_id}/assessment",
        json={
            "interests": interests,
            "answers": [{"question_id": q["id"], "selected_index": None} for q in questions],
        },
    )
    assert res_assessment.status_code == 200

    before = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert before.status_code == 200

    assert _put_skills(client, profile_id, ["python", "pymatching", "stim"]).status_code == 200

    after = client.get(f"/api/v1/profiles/{profile_id}/paths")
    assert after.status_code == 200
    assert after.json() == before.json()
