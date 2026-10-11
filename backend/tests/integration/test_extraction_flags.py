"""Extraction flag-persistence integration tests (M-10 regression suite).

Runs :func:`extraction_service.run_extraction` against a temporary SQLite DB
with :class:`FakeStructuredLLM` only (no network ever — AGENTS 3.5.1/3.7.1),
asserting that what reaches ``job_postings`` obeys the evidence-derived flag
rules even when the model claims something else, and that re-extraction
replaces (not appends) skill link rows.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.integrations.gemini.client import FakeStructuredLLM
from app.integrations.gemini.schemas import ExtractionBatch, PostingExtraction
from app.models import JobPosting, JobPostingSkill
from app.services import extraction_service

pytestmark = pytest.mark.usefixtures("_seed_reference_data")


def _seed_posting(db: Session, **job_extra: Any) -> JobPosting:
    """Insert one pending posting with explicit field overrides."""
    posting = JobPosting(
        dedupe_key=f"key-{job_extra.get('title', 't')}-{len(job_extra)}",
        title=str(job_extra.get("title", "Quantum Engineer")),
        company="TestCo",
        description=job_extra.get("description"),
        extensions=list(job_extra.get("extensions", [])),
        is_internship=False,
    )
    posting.extraction_status = "pending"
    db.add(posting)
    db.commit()
    return posting


def _batch_for(posting: JobPosting, **item_overrides: Any) -> FakeStructuredLLM:
    """Build a one-posting FakeStructuredLLM with the seniority claim inside."""
    item = PostingExtraction(
        posting_ref=str(posting.id),
        skill_ids=list(item_overrides.get("skill_ids", ["python"])),
        **{k: v for k, v in item_overrides.items() if k != "skill_ids"},
    )
    return FakeStructuredLLM([ExtractionBatch(items=[item])])


# ---------------------------------------------------------- seniority gating


def test_run_extraction_stores_unbacked_seniority_as_null(db_session: Session) -> None:
    """Regression: unlabelled "senior" claim + generic title → NULL seniority."""
    posting = _seed_posting(db_session, title="Quantum Scientist")
    fake = _batch_for(posting, seniority="senior")

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.seniority is None


def test_run_extraction_kepts_backed_seniority(db_session: Session) -> None:
    """Claim + matching title keyword survives persistence."""
    posting = _seed_posting(db_session, title="Senior Quantum Scientist")
    fake = _batch_for(posting, seniority="senior")

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.seniority == "senior"


def test_run_extraction_persists_faculty_seniority(db_session: Session) -> None:
    """New faculty bucket: professor keyword + faculty claim → 'faculty'."""
    posting = _seed_posting(db_session, title="Assistant Professor of Quantum Information")
    fake = _batch_for(posting, seniority="faculty")

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.seniority == "faculty"


def test_run_extraction_seniority_keyword_in_description_window(db_session: Session) -> None:
    """Keyword in the first 3000 description chars supports the claim."""
    description = "x" * 2500 + "a mid-level position in our algorithms group"
    posting = _seed_posting(db_session, title="Engineer", description=description)
    fake = _batch_for(posting, seniority="mid")

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.seniority == "mid"


# ----------------------------------------------------------- PhD persistence


def test_run_extraction_requires_phd_true_from_text(db_session: Session) -> None:
    """'PhD required' in the description → requires_phd=True regardless of claim."""
    posting = _seed_posting(
        db_session, title="Quantum Researcher", description="We require a PhD in physics."
    )
    fake = _batch_for(posting, requires_phd=None)

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.requires_phd is True


def test_run_extraction_requires_phd_false_only_when_stated(db_session: Session) -> None:
    """'No PhD required' → False; silence stays NULL even with model True."""
    posting = _seed_posting(
        db_session, title="Engineer", description="Great team; no PhD required."
    )
    fake = _batch_for(posting, requires_phd=None)

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.requires_phd is False

    silent = _seed_posting(db_session, title="Another Engineer", description="Build stuff.")
    extraction_service.run_extraction(db_session, _batch_for(silent))
    db_session.refresh(silent)
    assert silent.requires_phd is None


def test_run_extraction_requires_phd_preferred_stays_null(db_session: Session) -> None:
    """'PhD preferred' must NOT become True or False."""
    posting = _seed_posting(
        db_session, title="Researcher", description="A PhD is preferred but not required."
    )
    fake = _batch_for(posting, requires_phd=None)

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.requires_phd is None


def test_run_extraction_postdoc_role_gives_phd_true(db_session: Session) -> None:
    """A postdoc title implies a PhD requirement."""
    posting = _seed_posting(db_session, title="Postdoctoral Researcher in QEC")
    # The claim comes from the model; the role keyword in the title backs it.
    fake = _batch_for(posting, requires_phd=None, seniority="postdoc")

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.requires_phd is True
    assert posting.seniority == "postdoc"  # role keyword also backs the claim


# ------------------------------------------------------------- internship


def test_run_extraction_internship_from_title_implies_intern_seniority(
    db_session: Session,
) -> None:
    """Internship regex on title → is_internship=True AND seniority='intern'."""
    posting = _seed_posting(db_session, title="Research Intern — QEC")
    fake = _batch_for(posting, seniority="senior")  # contradicts; evidence wins

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.is_internship is True
    assert posting.seniority == "intern"


def test_run_extraction_model_internship_claim_is_ignored(db_session: Session) -> None:
    """Regression: a non-intern title never becomes an internship, model or not."""
    posting = _seed_posting(db_session, title="Senior Quantum Scientist")
    fake = _batch_for(posting, seniority="senior", is_internship=True)

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.is_internship is False


def test_run_extraction_extension_internship_overrides_title_seniority(
    db_session: Session,
) -> None:
    """Extensions count as internship evidence even with a plain title."""
    posting = _seed_posting(
        db_session, title="Quantum Developer", extensions=["Internship", "Full–time"]
    )
    fake = _batch_for(posting, is_internship=False)  # contradicting claim ignored

    extraction_service.run_extraction(db_session, fake)

    db_session.refresh(posting)
    assert posting.is_internship is True
    assert posting.seniority == "intern"


# ----------------------------------------------------- replace-not-append


def test_run_extraction_replaces_skill_links_not_appends(db_session: Session) -> None:
    """Re-extraction replaces a posting's skill links (never appends)."""
    posting = _seed_posting(db_session, title="Senior Quantum Scientist")

    first = _batch_for(posting, skill_ids=["python", "qiskit"])
    extraction_service.run_extraction(db_session, first)
    rows = db_session.query(JobPostingSkill).filter(JobPostingSkill.posting_id == posting.id).all()
    assert {r.skill_id for r in rows} == {"python", "qiskit"}

    # Posting is done; force it back into the pool to simulate a re-run.
    posting.extraction_status = "pending"
    db_session.commit()

    # Postings come out oldest-first: both runs select the same row.
    second = _batch_for(posting, skill_ids=["cpp"])
    extraction_service.run_extraction(db_session, second)

    rows = db_session.query(JobPostingSkill).filter(JobPostingSkill.posting_id == posting.id).all()
    assert {r.skill_id for r in rows} == {"cpp"}  # replaced, not {python,qiskit,cpp}
