"""Skill ORM model: one row per entry in the controlled vocabulary (plan 4.8).

The AI may only ever emit ids from this list (``concept_ids`` stays empty until
Phase 6, when skill→concept mapping is curated).
"""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Skill(Base):
    """One row per vocabulary skill; aliases feed prompt matching and dedupe."""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    subfield_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    concept_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        """Return a compact debugging representation without any payload data."""
        return f"<Skill {self.id}>"
