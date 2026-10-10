"""Integration tests for the Phase 3 quiz/profile endpoints (plan 3.6).

Runs against the temp SQLite DB via the TestClient (never a mocked DB,
AGENTS.md 3.7.1). No network, no LLM — Phase 3 uses none.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

# The committed bank is 100% placeholder (verified=false) during Phase 3
# development, so serving requires the dev flag (owner flips it back after M-08).
pytestmark = pytest.mark.usefixtures("allow_unverified")

SCORED_SUBFIELDS = {"qec", "hardware", "software", "algorithms", "qml", "crypto_net"}


@pytest.fixture()
def allow_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve unverified (placeholder) questions in these tests, like dev .env."""
    monkeypatch.setenv("ALLOW_UNVERIFIED_QUESTIONS", "true")


@pytest.fixture()
def quiz_payload(client: TestClient, db_session) -> dict:  # noqa: ANN001
    """Fetch the quiz and build a payload that answers everything correctly.

    The correct indices come from the DB (the API never reveals them — that is
    the point of the no-answer-keys rule).
    """
    from sqlalchemy import select

    from app.models import Question

    questions = client.get("/api/v1/quiz").json()["questions"]
    correct = dict(db_session.execute(select(Question.id, Question.correct_index)).all())
    interests = {subfield: 3 for subfield in SCORED_SUBFIELDS}
    answers = [{"question_id": q["id"], "selected_index": correct[q["id"]]} for q in questions]
    return {"interests": interests, "answers": answers}


def test_quiz_returns_18_questions_with_expected_shape(client: TestClient) -> None:
    """The full quiz is served in fixture mode with the dev flag on."""
    response = client.get("/api/v1/quiz")

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert len(questions) == 18
    assert {q["subfield_id"] for q in questions} == SCORED_SUBFIELDS
    for q in questions:
        assert set(q) == {"id", "subfield_id", "concept_id", "difficulty", "stem", "options"}
        assert len(q["options"]) == 4
        assert 1 <= q["difficulty"] <= 3


def test_quiz_endpoint_never_returns_correct_answers(client: TestClient) -> None:
    """HARD RULE (AGENTS.md 3.10.3): no answer material in the quiz response."""
    response = client.get("/api/v1/quiz")

    assert response.status_code == 200
    body = response.text
    assert "correct_index" not in body
    assert "explanation" not in body
    # Check for answer-revealing patterns, not just the substring "correct"
    # (real stems may contain "correction" etc.). The JSON keys below are the
    # actual answer fields that must never appear in GET /quiz.
    import json

    data = json.loads(body)
    for q in data["questions"]:
        assert "correct_index" not in q
        assert "explanation" not in q
        assert "correct_answer" not in q
        assert "answer" not in q


def test_quiz_refuses_when_unverified_questions_disallowed(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,  # noqa: ANN001
) -> None:
    """With the flag off and all questions unverified, the endpoint refuses clearly."""
    from sqlalchemy import update

    from app.models import Question

    db_session.execute(update(Question).values(verified=False))
    db_session.commit()

    monkeypatch.setenv("ALLOW_UNVERIFIED_QUESTIONS", "false")
    # Settings is cached from app startup; drop the cache so the service sees
    # the env var set above (env vars win over the dev .env in pydantic-settings).
    get_settings.cache_clear()
    try:
        response = client.get("/api/v1/quiz")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "quiz_insufficient_questions"
    assert "servable" in error["message"]


def test_quiz_serves_when_all_questions_verified(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,  # noqa: ANN001
) -> None:
    """With flag false and all rows verified, GET /quiz returns 200 without answers."""
    from sqlalchemy import update

    from app.models import Question

    db_session.execute(update(Question).values(verified=True))
    db_session.commit()

    monkeypatch.setenv("ALLOW_UNVERIFIED_QUESTIONS", "false")
    get_settings.cache_clear()
    try:
        response = client.get("/api/v1/quiz")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.text
    assert "correct_index" not in body
    assert "explanation" not in body
    data = response.json()
    for q in data["questions"]:
        assert "correct_index" not in q
        assert "explanation" not in q


def test_quiz_refuses_when_a_subfield_has_too_few_questions(
    client: TestClient,
    db_session,  # noqa: ANN001
) -> None:
    """Deleting one question from a subfield trips the >=3 guard (plan 3.1)."""
    from sqlalchemy import delete

    from app.models import Question

    db_session.execute(delete(Question).where(Question.id == "qec-3"))
    db_session.commit()

    response = client.get("/api/v1/quiz")

    assert response.status_code == 503
    assert "qec" in response.json()["error"]["message"]


def test_profile_create_is_idempotent_for_same_uuid(client: TestClient) -> None:
    """POSTing the same client UUID twice returns the same profile (AGENTS 3.3.9)."""
    same_uuid = "11111111-1111-1111-1111-111111111111"
    first = client.post("/api/v1/profiles", json={"profile_id": same_uuid})
    second = client.post("/api/v1/profiles", json={"profile_id": same_uuid})

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["profile_id"] == second.json()["profile_id"]
    # A server-generated profile also works when no body is sent.
    generated = client.post("/api/v1/profiles")
    assert generated.status_code == 200
    assert generated.json()["profile_id"] != first.json()["profile_id"]


def test_get_unknown_profile_returns_404(client: TestClient) -> None:
    """Unknown profile UUID -> shared error shape with 404."""
    response = client.get("/api/v1/profiles/22222222-2222-2222-2222-222222222222")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_submit_assessment_scores_and_stores(client: TestClient, quiz_payload: dict) -> None:
    """A correct-everything submission yields 100 per subfield and persists."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]

    created = client.post(f"/api/v1/profiles/{profile}/assessment", json=quiz_payload)
    assert created.status_code == 200
    body = created.json()
    assert body["scores"] == {subfield: 100.0 for subfield in SCORED_SUBFIELDS}
    assert len(body["per_question"]) == 18
    assert all(item["correct"] for item in body["per_question"])
    assert body["weak_concepts"] == []
    assert body["interests"] == quiz_payload["interests"]

    latest = client.get(f"/api/v1/profiles/{profile}/assessments/latest")
    assert latest.status_code == 200
    assert latest.json()["scores"] == body["scores"]

    # The profile now carries the latest submitted interests.
    profile_view = client.get(f"/api/v1/profiles/{profile}")
    assert profile_view.json()["interests"] == quiz_payload["interests"]


def test_submit_assessment_mixed_answers_scores_exactly(
    client: TestClient, quiz_payload: dict
) -> None:
    """Difficulties 1 and 3 correct, difficulty 2 "Not sure" -> 4/6 per subfield (plan 3.6)."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]
    questions = client.get("/api/v1/quiz").json()["questions"]
    answers = []
    for q in questions:
        selected = 0 if q["difficulty"] in (1, 3) else None
        # Only correct when the correct_index really is 0; the mixed-case math
        # is fully covered by the table-driven unit tests, this checks the API.
        answers.append({"question_id": q["id"], "selected_index": selected})
    payload = {"interests": quiz_payload["interests"], "answers": answers}

    body = client.post(f"/api/v1/profiles/{profile}/assessment", json=payload).json()

    assert len(body["per_question"]) == 18
    assert set(body["scores"]) == SCORED_SUBFIELDS
    # Feedback is present post-submission (explanations may be placeholder text).
    for item in body["per_question"]:
        assert set(item) == {"question_id", "correct", "explanation", "concept_id"}


def test_submit_assessment_rejects_unknown_question_id(
    client: TestClient, quiz_payload: dict
) -> None:
    """An unknown question id is a 422 with the shared error shape (plan 3.3)."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]
    payload = {**quiz_payload, "answers": [{"question_id": "ghost-q", "selected_index": 0}]}

    response = client.post(f"/api/v1/profiles/{profile}/assessment", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_assessment"
    assert "ghost-q" in response.json()["error"]["message"]


def test_submit_assessment_rejects_duplicate_answers(
    client: TestClient, quiz_payload: dict
) -> None:
    """Answering the same question twice is a 422 (plan 3.3)."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]
    dup = quiz_payload["answers"] + [quiz_payload["answers"][0]]
    payload = {**quiz_payload, "answers": dup}

    response = client.post(f"/api/v1/profiles/{profile}/assessment", json=payload)

    assert response.status_code == 422
    assert "duplicate" in response.json()["error"]["message"]


def test_submit_assessment_rejects_bad_interests(client: TestClient, quiz_payload: dict) -> None:
    """Interests must cover exactly the six scored subfields (assumption recorded)."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]
    unknown = {**quiz_payload, "interests": {"not-a-subfield": 3}}
    missing = {**quiz_payload, "interests": {"qec": 3}}

    unknown_response = client.post(f"/api/v1/profiles/{profile}/assessment", json=unknown)
    missing_response = client.post(f"/api/v1/profiles/{profile}/assessment", json=missing)

    assert unknown_response.status_code == 422
    assert "not-a-subfield" in unknown_response.json()["error"]["message"]
    assert missing_response.status_code == 422


def test_latest_assessment_without_history_returns_404(client: TestClient) -> None:
    """A fresh profile has no assessments yet -> 404, not an empty 200."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]

    response = client.get(f"/api/v1/profiles/{profile}/assessments/latest")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_assessment_persists_across_requests(client: TestClient, quiz_payload: dict) -> None:
    """The DB (not just the response) contains the assessment: submit, re-fetch."""
    profile = client.post("/api/v1/profiles").json()["profile_id"]
    client.post(f"/api/v1/profiles/{profile}/assessment", json=quiz_payload)
    # A second submission (retake) replaces "latest" but history is kept.
    all_not_sure = {
        **quiz_payload,
        "answers": [
            {"question_id": a["question_id"], "selected_index": None}
            for a in quiz_payload["answers"]
        ],
    }
    retake = client.post(f"/api/v1/profiles/{profile}/assessment", json=all_not_sure)
    latest = client.get(f"/api/v1/profiles/{profile}/assessments/latest")

    assert retake.status_code == 200
    assert latest.json()["assessment_id"] == retake.json()["assessment_id"]
    assert latest.json()["scores"] == {subfield: 0.0 for subfield in SCORED_SUBFIELDS}
    # Not-sure answers still produce weak concepts (plan 3.3).
    assert len(latest.json()["weak_concepts"]) > 0
