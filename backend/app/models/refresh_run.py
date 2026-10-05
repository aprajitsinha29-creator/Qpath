"""RefreshRun ORM model: one row per ingestion/extraction run (plan 4.3).

Written by the ingestion services (Phase 1 jobs; Phase 2 scholar/extraction)
so the UI's refresh-status views and tests can see what ran, when, how many
SerpApi calls it made, and any per-query errors. Per-query failures never
abort a run — they are collected in ``details`` (plan 1.3.3).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class RefreshRun(Base):
    """One ingestion run: kind (jobs/scholar/extraction), mode, counts, errors."""

    __tablename__ = "refresh_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # jobs | scholar | extraction
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # bootstrap | daily
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    serpapi_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Free-form summary: {"postings_seen": ..., "postings_new": ..., "errors": [...]}.
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return f"<RefreshRun {self.id} {self.kind}/{self.mode}/{self.status}>"
