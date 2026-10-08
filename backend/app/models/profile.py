"""Profile and Assessment ORM models: the anonymous diagnostic aggregate (plan 4.3).

One aggregate, one module: an assessment has no meaning without its profile.
No personal data is stored — only an anonymous UUID, the user's own answers
and derived scores (AGENTS.md 3.10.4). Phase 5 fields (``chosen_path_id``,
``last_seen_at``) are created now to avoid a schema change later (migrations
are a non-goal, AGENTS.md 3.3.8).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class Profile(Base):
    """One anonymous user profile; ``id`` is a UUID string created client-side.

    ``interests`` mirrors the latest submitted diagnostic ({subfield_id: 1-5});
    history lives in ``assessments`` so retakes are kept (plan Phase 3).
    """

    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    # Phase 5 fields, created now to avoid a later schema change:
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chosen_path_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    interests: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    declared_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    completed_concepts: Mapped[list[str]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        """Return a compact debugging representation (id only, no answers)."""
        return f"<Profile {self.id}>"


class Assessment(Base):
    """One diagnostic submission: raw answers plus derived per-subfield scores.

    ``scores`` is ``{subfield_id: 0-100}`` computed by
    :mod:`app.services.scoring_service` — never by the LLM (AGENTS.md 3.3.10).
    """

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("profiles.id"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    # Raw answers as submitted: [{question_id, selected_index|null}].
    answers: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    scores: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only, no answers)."""
        return f"<Assessment {self.id} profile={self.profile_id}>"
