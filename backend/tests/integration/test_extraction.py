"""Extraction service and endpoint tests (plan 2.4 / 2.8) — FakeStructuredLLM only.

Every test here runs against a temporary SQLite DB with the seeded vocabulary;
the LLM is always the offline :class:`FakeStructuredLLM` (no network, ever —
AGENTS 3.5.1/3.7.1). The endpoint tests exercise the real router with a
dependency override, so the wiring (admin token, limits, summary schema) is
verified end to end.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.integrations.gemini.client import FakeStructuredLLM
from app.integrations.gemini.schemas import ExtractionBatch, PostingExtraction
from app.models import JobPosting, JobPostingSkill
from app.services import extraction_service

pytestmark = pytest.mark.usefixtures("_seed_reference_data")

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


# ------------------------------------------------------------------ helpers


def _seed_postings(db: Session, n: int, **job_extra: Any) -> list[JobPosting]:
    """Insert ``n`` postings directly (bypassing ingestion) and return them."""
    postings: list[JobPosting] = []
    for i in range(n):
        posting = JobPosting(
            dedupe_key=f"key-{i}-{job_extra.get('title', 't')}",
            title=str(job_extra.get("title", f"Quantum Engineer {i}")),
            company="TestCo",
            description=f"Description {i} mentioning Qiskit and Python.",
            extensions=list(job_extra.get("extensions", [])),
            is_internship=False,
        )
        db.add(posting)
        postings.append(posting)
    db.commit()
    return postings


def _item(ref: str, skills: list[str], **overrides: Any) -> PostingExtraction:
    """Build one model output item with sensible defaults."""
    return PostingExtraction(posting_ref=ref, skill_ids=skills, **overrides)


def _batch(items: list[PostingExtraction]) -> ExtractionBatch:
    return ExtractionBatch(items=items)


# ---------------------------------------------------------------- selection


def test_select_pending_postings_returns_pending_and_failed_under_cap(
    db_session: Session,
) -> None:
    """Pending and failed postings are eligible; done and 3x-failed are not."""
    pending, done_row, failed_twice, capped = _seed_postings(db_session, 4)
    done_row.extraction_status = "done"
    failed_twice.extraction_status = "failed"
    failed_twice.extraction_attempts = 2
    capped.extraction_status = "failed"
    capped.extraction_attempts = 3
    db_session.commit()

    selected = extraction_service.select_pending_postings(db_session)

    ids = {p.id for p in selected}
    assert pending.id in ids
    assert failed_twice.id in ids  # still has one attempt left
    assert done_row.id not in ids
    assert capped.id not in ids


def test_select_pending_postings_respects_limit(db_session: Session) -> None:
    """A limit caps the candidate list (oldest ids first)."""
    _seed_postings(db_session, 5)
    selected = extraction_service.select_pending_postings(db_session, limit=2)
    assert len(selected) == 2
    assert [p.id for p in selected] == sorted(p.id for p in selected)


# ------------------------------------------------------------ post-validation


def test_post_validate_drops_unknown_skill_ids_to_unmapped(db_session: Session) -> None:
    """Vocabulary ids are kept; invented ones move to unmapped_skills (plan 4.7)."""
    batch = _batch(
        [_item("1", ["python", "made_up_skill", "qiskit"], unmapped_skills=["DWave Ocean"])]
    )
    corrected = extraction_service._post_validate_batch(
        batch,
        expected_refs=["1"],
        valid_skill_ids={"python", "qiskit"},
        valid_subfield_ids={"qec"},
    )

    assert corrected is not None
    assert corrected[0].skill_ids == ["python", "qiskit"]
    assert corrected[0].unmapped_skills == ["DWave Ocean", "made_up_skill"]


def test_post_validate_nulls_invalid_primary_subfield(db_session: Session) -> None:
    """A primary_subfield_id outside the taxonomy becomes None."""
    batch = _batch([_item("1", ["python"], primary_subfield_id="cooking")])
    corrected = extraction_service._post_validate_batch(
        batch,
        expected_refs=["1"],
        valid_skill_ids={"python"},
        valid_subfield_ids={"qec", "software"},
    )

    assert corrected is not None
    assert corrected[0].primary_subfield_id is None


def test_post_validate_rejects_wrong_item_count(db_session: Session) -> None:
    """Fewer items than postings invalidates the whole batch (plan 4.7)."""
    batch = _batch([_item("1", ["python"])])
    assert (
        extraction_service._post_validate_batch(
            batch,
            expected_refs=["1", "2"],
            valid_skill_ids={"python"},
            valid_subfield_ids=set(),
        )
        is None
    )


def test_post_validate_rejects_ref_mismatch(db_session: Session) -> None:
    """Refs out of order (or wrong) invalidate the batch (plan 4.7)."""
    batch = _batch([_item("2", ["python"]), _item("1", ["qiskit"])])
    assert (
        extraction_service._post_validate_batch(
            batch,
            expected_refs=["1", "2"],
            valid_skill_ids={"python", "qiskit"},
            valid_subfield_ids=set(),
        )
        is None
    )


def test_post_validate_deduplicates_repeated_skill_ids(db_session: Session) -> None:
    """The model may repeat an id; persistence must not duplicate link rows."""
    batch = _batch([_item("1", ["python", "python"])])
    corrected = extraction_service._post_validate_batch(
        batch,
        expected_refs=["1"],
        valid_skill_ids={"python"},
        valid_subfield_ids=set(),
    )

    assert corrected is not None
    assert corrected[0].skill_ids == ["python"]


# ---------------------------------------------------------------- run behavior


def test_run_extraction_persists_skills_and_marks_done(db_session: Session) -> None:
    """A valid batch writes skill rows, seniority, PhD flag and status=done."""
    # "Senior" in the title is required evidence now: a seniority claim is
    # persisted only when the text corroborates it (M-10 fix, flag_rules).
    postings = _seed_postings(db_session, 2, title="Senior Quantum Engineer")
    fake = FakeStructuredLLM(
        [
            _batch(
                [
                    _item(
                        str(postings[0].id),
                        ["python", "qiskit"],
                        seniority="senior",
                        requires_phd=False,
                        is_internship=False,
                        primary_subfield_id="software",
                    ),
                    _item(str(postings[1].id), ["cpp"], seniority="unknown", requires_phd=None),
                ]
            )
        ]
    )

    counts = extraction_service.run_extraction(db_session, fake)

    assert counts == {"done": 2, "failed": 0, "skipped": 0}
    assert fake.call_count == 1  # two postings fit in one batch of 5
    for posting in postings:
        db_session.refresh(posting)
    assert postings[0].extraction_status == "done"
    assert postings[0].seniority == "senior"
    # Model False for an unlabelled posting is not evidence: stays NULL (spec:
    # requires_phd is False only when the text says no PhD is needed).
    assert postings[0].requires_phd is None
    assert postings[1].seniority is None  # "unknown" stored as NULL
    skill_ids = {row.skill_id for row in db_session.query(JobPostingSkill).all()}
    assert skill_ids == {"python", "qiskit", "cpp"}


def test_run_extraction_batches_five_and_never_reextracts_done(db_session: Session) -> None:
    """5-posting batching (plan 3.5.5) and done-posting skip (plan 2.4.3)."""
    postings = _seed_postings(db_session, 7)
    fake = FakeStructuredLLM(
        [
            _batch([_item(str(p.id), ["python"]) for p in postings[:5]]),
            _batch([_item(str(p.id), ["python"]) for p in postings[5:]]),
        ]
    )

    first = extraction_service.run_extraction(db_session, fake)
    assert first == {"done": 7, "failed": 0, "skipped": 0}
    assert fake.call_count == 2  # 5 + 2

    # A second run must find nothing to do (idempotency, plan 2.4.3).
    second = extraction_service.run_extraction(db_session, fake)
    assert second == {"done": 0, "failed": 0, "skipped": 0}
    assert fake.call_count == 2


def test_run_extraction_marks_batch_failed_after_retry(db_session: Session) -> None:
    """Count mismatch → retry once → both attempts exhausted → failed + attempts=1."""
    postings = _seed_postings(db_session, 1)
    fake = FakeStructuredLLM(
        [
            _batch([]),  # wrong item count
            _batch([_item("999", ["python"])]),  # wrong ref on retry
        ]
    )

    counts = extraction_service.run_extraction(db_session, fake)

    assert counts["failed"] == 1
    assert fake.call_count == 2
    db_session.refresh(postings[0])
    assert postings[0].extraction_status == "failed"
    assert postings[0].extraction_attempts == 1


def test_run_extraction_stops_postings_after_three_attempts(db_session: Session) -> None:
    """Each failed run bumps attempts; the pool excludes them at 3 (plan 4.7)."""
    (posting,) = _seed_postings(db_session, 1)
    fake = FakeStructuredLLM([])  # every call raises "out of responses" → batch fails

    for _ in range(3):
        fake._responses = []  # reset the queue; every attempt still fails
        extraction_service.run_extraction(db_session, fake)
        db_session.refresh(posting)
    assert posting.extraction_attempts == 3
    assert posting.extraction_status == "failed"

    # A 4th run selects nothing: the posting is permanently out of the pool.
    final = extraction_service.run_extraction(db_session, fake)
    assert final["failed"] == 0
    assert final["done"] == 0


def test_run_extraction_recovers_after_failed_attempt(db_session: Session) -> None:
    """A failed run can be followed by a successful one (attempts < 3)."""
    (posting,) = _seed_postings(db_session, 1)
    bad = FakeStructuredLLM([])
    extraction_service.run_extraction(db_session, bad)
    db_session.refresh(posting)
    assert posting.extraction_status == "failed"

    good = FakeStructuredLLM([_batch([_item(str(posting.id), ["python"])])])
    counts = extraction_service.run_extraction(db_session, good)

    assert counts["done"] == 1
    db_session.refresh(posting)
    assert posting.extraction_status == "done"


def test_run_extraction_model_cannot_undo_rule_based_internship(db_session: Session) -> None:
    """Rule-detected internships survive a model is_internship=false (plan 4.7)."""
    (posting,) = _seed_postings(
        db_session, 1, title="Quantum Research Intern", extensions=["Internship"]
    )
    from app.integrations.serpapi.parsers import detect_internship

    posting.is_internship = detect_internship(posting.title, posting.extensions)
    db_session.commit()
    assert posting.is_internship is True

    fake = FakeStructuredLLM([_batch([_item(str(posting.id), ["python"], is_internship=False)])])
    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.is_internship is True  # OR-ed, never downgraded


def test_run_extraction_respects_limit_and_reports_skipped(db_session: Session) -> None:
    """limit=3 over 7 candidates processes 3 and reports 4 skipped."""
    _seed_postings(db_session, 7)
    fake = FakeStructuredLLM(
        [
            _batch([_item(str(i), ["python"]) for i in range(1, 4)]),
        ]
    )

    counts = extraction_service.run_extraction(db_session, fake, limit=3)

    assert counts == {"done": 3, "failed": 0, "skipped": 4}


def test_run_extraction_prompt_contains_vocabulary_and_batch(db_session: Session) -> None:
    """The prompt carries the vocabulary, subfields and truncated postings."""
    postings = _seed_postings(db_session, 1)
    fake = FakeStructuredLLM([_batch([_item(str(postings[0].id), ["python"])])])

    extraction_service.run_extraction(db_session, fake)

    prompt = fake.calls[0][0]
    assert "python: Python" in prompt  # vocabulary line
    assert "qec:" in prompt  # subfield lines
    assert "posting_ref:" in prompt  # posting block
    assert "Never invent ids" in prompt  # plan 4.7 rules are present


def test_run_extraction_truncates_long_descriptions(db_session: Session) -> None:
    """Descriptions are cut to ~3000 chars in the prompt (plan 4.7)."""
    (posting,) = _seed_postings(db_session, 1)
    posting.description = "x" * 9000
    db_session.commit()
    fake = FakeStructuredLLM([_batch([_item(str(posting.id), ["python"])])])

    extraction_service.run_extraction(db_session, fake)

    prompt = fake.calls[0][0]
    assert "x" * 3000 in prompt
    assert "x" * 3001 not in prompt


# ------------------------------------------------------------------- endpoint


def test_admin_extract_endpoint_runs_with_fake_llm(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /admin/extract with the LLM dependency overridden returns counts."""
    postings = _seed_postings(db_session, 2)
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.api.deps import get_structured_llm

    fake = FakeStructuredLLM([_batch([_item(str(p.id), ["python"]) for p in postings])])
    client.app.dependency_overrides[get_structured_llm] = lambda: fake
    try:
        response = client.post(
            "/api/v1/admin/extract?limit=50",
            headers=ADMIN_HEADERS,
        )
    finally:
        client.app.dependency_overrides.pop(get_structured_llm, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"done": 2, "failed": 0, "skipped": 0}
    assert fake.call_count == 1


def test_admin_extract_without_gemini_config_returns_config_error(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Gemini feature invoked without credentials surfaces a clear 500."""
    _seed_postings(db_session, 1)
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMINI_MODEL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    response = client.post("/api/v1/admin/extract", headers=ADMIN_HEADERS)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "config_error"


def test_admin_extract_rejects_missing_token(client: TestClient) -> None:
    """The endpoint is admin-guarded like the other admin routes."""
    response = client.post("/api/v1/admin/extract?limit=5")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_admin_extract_rejects_bad_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """limit must be a positive integer (query validation)."""
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = client.post("/api/v1/admin/extract?limit=0", headers=ADMIN_HEADERS)
    assert response.status_code == 422
