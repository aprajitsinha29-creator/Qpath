"""Schemas for the pulse endpoints (plan 1.5): cards, postings, lists, detail.

Field names mirror the ORM columns where sensible, but timestamps are ISO
strings (serialized by Pydantic) and descriptions are truncated snippets —
ORM models never leave the service layer (AGENTS.md 3.3.4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SkillShare(BaseModel):
    """Skill mention share among extracted postings for a subfield+region.

    ``share`` = postings mentioning the skill / active extracted postings
    (extraction_status='done'). Reported alongside ``extraction_coverage``
    so the UI can caveat when coverage < 100%.
    """

    skill_id: str
    name: str
    share: float


class PaperRef(BaseModel):
    """Minimal paper reference used by research themes."""

    id: int
    title: str
    link: str | None


class ThemeOut(BaseModel):
    """One research theme with its supporting papers."""

    label: str
    summary: str
    papers: list[PaperRef]


class SeniorityMix(BaseModel):
    """Seniority distribution and PhD share for a subfield's postings."""

    seniority: dict[str, int]
    phd_share: float | None


class PulseCard(BaseModel):
    """One Market Pulse card: demand counts for a subfield in one region.

    ``active_postings`` counts core-tier postings only; ``extra_postings``
    counts postings found exclusively via extended queries (shown in the
    posting list, excluded from headline demand — plan 4.6 fairness note).
    ``new_this_week`` is null until tracking spans >= 2 ingestion days; the UI
    renders "tracking since <date>" from ``tracking_since`` instead.

    Phase 2 additive fields (optional with defaults so Phase 1 clients/tests
    stay valid):
    - ``top_skills``: top 5 skills by share among extracted postings.
    - ``themes``: top 3 research themes with papers.
    """

    subfield_id: str
    name: str
    description: str
    active_postings: int
    extra_postings: int
    internship_postings: int
    new_this_week: int | None
    tracking_since: str | None
    top_companies: list[str]
    low_data: bool
    top_skills: list[SkillShare] = []
    themes: list[ThemeOut] = []


class PostingOut(BaseModel):
    """One posting in a list view: identity, best apply link and a snippet.

    ``snippet`` is the first ~240 characters of the description (plan 1.5) —
    the full description stays in the database and feeds Phase 2 extraction.
    """

    id: int
    title: str
    company: str
    location: str | None
    via: str | None
    apply_url: str | None
    is_internship: bool
    first_seen_at: datetime
    snippet: str | None


class TrendPoint(BaseModel):
    """One day of snapshot data in a subfield's trend series (plan 5.4)."""

    date: str  # ISO YYYY-MM-DD
    active: int
    new: int
    internships: int


class PostingListResponse(BaseModel):
    """Page of postings plus the unpaginated total for pagination UI."""

    total: int
    limit: int
    offset: int
    items: list[PostingOut]


class SubfieldDetail(BaseModel):
    """Full detail for one subfield: card fields plus intelligence layers."""

    subfield_id: str
    name: str
    description: str
    active_postings: int
    extra_postings: int
    internship_postings: int
    new_this_week: int | None
    tracking_since: str | None
    top_companies: list[str]
    low_data: bool
    top_skills: list[SkillShare]
    seniority_mix: dict[str, int]
    phd_share: float | None
    extraction_coverage: float
    themes: list[ThemeOut]
    postings: list[PostingOut]
