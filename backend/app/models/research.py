"""Scholar research aggregate: paper snapshots and AI-generated research themes.

Phase 2 step 2.1 (plan 4.3). One ``refresh_scholar`` run writes one **batch**:
a fresh ``batch_id`` groups the ``paper_snapshots`` rows fetched from Google
Scholar and the single ``research_themes`` row generated from them by Gemini.
Pulse reads the *latest* batch per subfield — older batches stay as history
(they are time-series snapshots, like ``pulse_snapshots``, not a deduplicated
corpus).

Honesty rules baked into the shape (plan 1.5 / AGENTS 3.4.9): there is **no**
``total_results`` column and no growth/count metric anywhere — Scholar data is
used only for qualitative themes over recent papers. ``cited_by`` is stored
because the plan lists it as an available field, but nothing computes trends
from it (new papers have almost no citations; see plan 1.5).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utc_now
from app.db.base import Base


def _utc_now() -> datetime:
    """Return the naive-UTC now used for all DB timestamps (see app.core.clock)."""
    return utc_now()


class PaperSnapshot(Base):
    """One Google Scholar organic result, captured during one refresh batch.

    ``year`` is parsed from ``publication_info.summary`` (last 19xx/20xx number)
    and may be None — the summary format is free text (plan 2.5.1).
    """

    __tablename__ = "paper_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subfield_id: Mapped[str] = mapped_column(String(32), ForeignKey("subfields.id"))
    # Groups the rows of one refresh run; themes reference papers via this id.
    # No FK (it is an opaque run identifier, not a table key).
    batch_id: Mapped[str] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(512))
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publication_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cited_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return f"<PaperSnapshot {self.id} batch={self.batch_id[:8]} {self.subfield_id}>"


class ResearchTheme(Base):
    """AI-generated qualitative research themes for one subfield batch.

    ``themes`` JSON shape: ``[{label, summary, paper_ids: [paper_snapshot ids]}]``.
    The LLM returns paper *indexes* into the batch listing; the research service
    validates them and stores resolved snapshot ids, so a theme can never point
    at a paper that was not supplied (plan 2.5.2). ``model`` records which
    Gemini model produced the row (from settings — never hardcoded, AGENTS 3.3.3).
    """

    __tablename__ = "research_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subfield_id: Mapped[str] = mapped_column(String(32), ForeignKey("subfields.id"))
    batch_id: Mapped[str] = mapped_column(String(32), index=True)
    themes: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    model: Mapped[str] = mapped_column(String(128))

    def __repr__(self) -> str:
        """Return a compact debugging representation (ids only)."""
        return f"<ResearchTheme {self.id} batch={self.batch_id[:8]} {self.subfield_id}>"
