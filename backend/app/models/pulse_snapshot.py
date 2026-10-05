"""PulseSnapshot ORM model: per-subfield/per-region daily counts (plan 4.3).

One row per (subfield, snapshot date, region), upserted after every jobs
ingestion. Phase 1 only computes today's snapshot; the ``/pulse/{id}/trend``
endpoint (Phase 5) reads the accumulated series.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class PulseSnapshot(Base):
    """Counts of postings per subfield for one day and region.

    Unique on (subfield, date, region): re-running ingestion on the same day
    refreshes the row instead of duplicating it (AGENTS 3.3.9).
    """

    __tablename__ = "pulse_snapshots"
    __table_args__ = (
        UniqueConstraint("subfield_id", "snapshot_date", "region", name="uq_snapshot_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subfield_id: Mapped[str] = mapped_column(String(32))
    # Plain Date (no FK): snapshots must survive even if reference data is re-seeded
    # with different ids; orphans are simply never queried again.
    snapshot_date: Mapped[date] = mapped_column(Date)
    region: Mapped[str] = mapped_column(String(8))
    active_postings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_postings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    internship_postings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return f"<PulseSnapshot {self.subfield_id} {self.snapshot_date} {self.region}>"
