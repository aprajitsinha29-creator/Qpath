"""SerpApiCallLog ORM model: one row per SerpApi call, live or fixture (plan 4.3).

Two consumers: the daily live-call cap (``source='live'`` rows counted for the
current UTC day) and the UI's "SerpApi activity" panel. The API key is never
stored here — only engine, query, source and status.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class SerpApiCallLog(Base):
    """One row per SerpApi call attempt.

    ``source`` is ``live`` or ``fixture``; ``status`` is ``ok``, ``error`` or
    ``missing`` (fixture file not found).
    """

    __tablename__ = "serpapi_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engine: Mapped[str] = mapped_column(String(32))
    query: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    def __repr__(self) -> str:
        """Return a compact debugging representation (no payload beyond identifiers)."""
        return f"<SerpApiCallLog {self.id} {self.engine}/{self.source}/{self.status}>"
