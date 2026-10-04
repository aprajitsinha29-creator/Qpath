"""Subfield ORM model: the six scored quantum subfields plus the `foundations` pseudo-subfield.

Seeded from ``app/data/taxonomy.json``. ``foundations`` carries ``is_scored=False`` —
it exists only to hold shared prerequisite concepts (plan 4.9).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Subfield(Base):
    """One row per subfield; ``id`` is the stable slug used across API and data files."""

    __tablename__ = "subfields"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_scored: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        """Return a compact debugging representation without any payload data."""
        return f"<Subfield {self.id}>"
