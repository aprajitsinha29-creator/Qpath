"""CareerPath ORM model: exactly one path per scored subfield (plan 4.9).

The path matcher (Phase 4) ranks these six deterministically; the seeder
enforces the 1:1 mapping with scored subfields.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CareerPath(Base):
    """One row per career path; ``id`` is the stable slug used in profile picks."""

    __tablename__ = "career_paths"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    subfield_id: Mapped[str] = mapped_column(String(32), ForeignKey("subfields.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    typical_titles: Mapped[list[str]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        """Return a compact debugging representation without any payload data."""
        return f"<CareerPath {self.id}>"
