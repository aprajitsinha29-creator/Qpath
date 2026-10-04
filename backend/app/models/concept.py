"""Concept ORM model: a learnable unit inside one subfield (plan 4.9).

``prerequisites`` is a JSON list of concept ids forming a DAG — the learning
plan (Phase 6) topologically sorts it, so the seeder rejects cycles.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Concept(Base):
    """One row per concept; ``id`` looks like ``qec.surface_code``."""

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subfield_id: Mapped[str] = mapped_column(String(32), ForeignKey("subfields.id"))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    prerequisites: Mapped[list[str]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        """Return a compact debugging representation without any payload data."""
        return f"<Concept {self.id}>"
