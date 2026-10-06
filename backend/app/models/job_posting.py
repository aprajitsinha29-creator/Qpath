"""JobPosting ORM model: one row per unique posting, plus its per-subfield links.

Phase 1 aggregate. ``dedupe_key`` is the stable identity of a posting — the
SerpApi ``job_id`` may change between fetches, so identity comes from the
normalized ``title + company + location`` triple (plan 1.1 / 4.3) computed by
``integrations.serpapi.parsers.make_dedupe_key``.

``job_posting_subfields`` lives in this file (not a separate module) because a
link row has no meaning without a posting: one aggregate, one module
(AGENTS.md 3.1 "models: one file per aggregate").

Extraction fields (``seniority``, ``requires_phd``, ``extraction_status`` ...)
are created here but only *written* by Phase 2 — defining them now avoids a
schema change later (migrations are a non-goal, AGENTS.md 3.3.8).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class JobPosting(Base):
    """One unique quantum job posting, seen across ingestion runs.

    ``is_active`` is the recency filter: postings not re-seen for 14 days are
    deactivated by :mod:`app.services.ingestion_service` rather than deleted,
    so history (first_seen_at) is preserved for trend snapshots.
    """

    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Unique: upsert-by-dedupe-key is the idempotency mechanism (AGENTS 3.3.9).
    dedupe_key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    serp_job_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256), nullable=True)
    via: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Normalized to a list[str] by the parser (list items are usually strings
    # like "3 days ago" or "Full–time", but SerpApi does not guarantee that).
    extensions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_internship: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Phase 2 fields (extraction), created now, populated later ---
    # seniority/requires_phd are nullable because "unknown" must be
    # distinguishable from "extracted but negative" (plan 4.7).
    seniority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    requires_phd: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(8), default="pending", nullable=False)
    extraction_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only, no payload)."""
        return f"<JobPosting {self.id} {self.dedupe_key[:8]}>"


class JobPostingSkill(Base):
    """Link row: which vocabulary skills were extracted from a posting (Phase 2).

    Only ids from the seeded ``skills`` vocabulary may appear here — the
    extraction service filters model output before persisting, so an id in
    this table is by construction a real skill (plan 4.7 post-validation).
    Rows are written only for postings with ``extraction_status='done'``.
    """

    __tablename__ = "job_posting_skills"
    __table_args__ = (
        # Extract-once semantics (AGENTS 3.3.9): re-running extraction for the
        # same posting replaces its rows instead of duplicating them.
        UniqueConstraint("posting_id", "skill_id", name="uq_posting_skill"),
    )

    posting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_postings.id"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(String(64), ForeignKey("skills.id"), primary_key=True)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return f"<JobPostingSkill posting={self.posting_id} skill={self.skill_id}>"


class JobPostingSubfield(Base):
    """Link row: which subfield(s) a posting was found for, by which query.

    The primary key includes ``region`` because the same posting may be
    ingested for global and India runs separately, and demand is reported
    per region (plan 1.4). ``tier`` records whether the discovery query was a
    core (daily) or extended (bootstrap-only) query — only core-tier links
    count toward headline ``active_postings`` (see ARCHITECTURE.md decision
    "Demand fairness via core-tier query counting").
    """

    __tablename__ = "job_posting_subfields"
    __table_args__ = (
        # One link row per (posting, subfield, region); repeated discoveries
        # refresh the existing row instead of duplicating it (AGENTS 3.3.9).
        UniqueConstraint("posting_id", "subfield_id", "region", name="uq_posting_subfield_region"),
    )

    posting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_postings.id"), primary_key=True
    )
    subfield_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("subfields.id"), primary_key=True
    )
    region: Mapped[str] = mapped_column(String(8), primary_key=True)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)  # "core" | "extended"
    source_query: Mapped[str] = mapped_column(String(256), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return (
            f"<JobPostingSubfield posting={self.posting_id} "
            f"subfield={self.subfield_id} {self.region}>"
        )
