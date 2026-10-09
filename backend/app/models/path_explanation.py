"""PathExplanation ORM model: cached per-path explanations (plan 4.1/4.4).

One row per (profile, assessment, career path) keyed by ``evidence_hash`` —
the sha256 of the grounded evidence JSON the explanation was generated from
(see ``services/explanation_service.py``). When the evidence changes (new
assessment, refreshed posting counts) the hash no longer matches and the
service regenerates, so a stale explanation can never be served.

``generated_by`` is ``llm`` or ``template``: the UI labels template fallbacks
honestly (plan 4.4; design decision 1 — the endpoint must never error just
because Gemini is unavailable).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class PathExplanation(Base):
    """One cached explanation payload for one path of one assessment."""

    __tablename__ = "path_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("profiles.id"))
    assessment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assessments.id"))
    path_id: Mapped[str] = mapped_column(String(48), ForeignKey("career_paths.id"))
    #: sha256 (hex) of the canonical evidence JSON this payload was built from.
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: {headline, reasons[3], caveat, next_step} — the plan 4.7 fields only.
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    #: "llm" or "template" (design decision 1: never fail the UI, label instead).
    generated_by: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Gemini model name for llm rows; None for template rows.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    __table_args__ = (
        # The cache lookup in explanation_service always filters on these three.
        Index("ix_path_explanations_cache", "profile_id", "assessment_id", "path_id"),
    )

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only, no payload text)."""
        return f"<PathExplanation {self.profile_id}/{self.assessment_id}/{self.path_id}>"
