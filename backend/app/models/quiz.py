"""Question ORM model: one quiz question in the diagnostic bank (plan 4.3).

Seeded from ``app/data/quiz_questions.json``. ``verified`` is owner-controlled
sign-off (manual task M-08 / BUILD_PLAN Section 6): only the owner may set it
to true. Whether unverified questions are *served* is decided at request time
by ``ALLOW_UNVERIFIED_QUESTIONS`` — the flag lives in the DB row so flipping
the env var takes effect without a reseed (deviation from plan 3.1 recorded in
ARCHITECTURE.md).
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Question(Base):
    """One row per quiz question; ``id`` looks like ``qec-1``.

    ``correct_index`` and ``explanation`` live here but NEVER leave the service
    layer in a client-facing payload (AGENTS.md 3.10.3): scoring is server-side.
    """

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subfield_id: Mapped[str] = mapped_column(String(32), ForeignKey("subfields.id"))
    concept_id: Mapped[str] = mapped_column(String(64), ForeignKey("concepts.id"))
    # Difficulty 1-3 doubles as the point value of a correct answer (plan 4.5).
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text)
    # Exactly 4 option strings; enforced by the seeder's validation.
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="")
    source_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only, no answers)."""
        return f"<Question {self.id} verified={self.verified}>"
