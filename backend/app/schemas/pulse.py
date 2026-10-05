"""Schemas for the pulse endpoints (plan 1.5): cards, postings, lists.

Field names mirror the ORM columns where sensible, but timestamps are ISO
strings (serialized by Pydantic) and descriptions are truncated snippets —
ORM models never leave the service layer (AGENTS.md 3.3.4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PulseCard(BaseModel):
    """One Market Pulse card: demand counts for a subfield in one region.

    ``active_postings`` counts core-tier postings only; ``extra_postings``
    counts postings found exclusively via extended queries (shown in the
    posting list, excluded from headline demand — plan 4.6 fairness note).
    ``new_this_week`` is null until tracking spans ≥ 2 ingestion days; the UI
    renders "tracking since <date>" from ``tracking_since`` instead.
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


class PostingListResponse(BaseModel):
    """Page of postings plus the unpaginated total for pagination UI."""

    total: int
    limit: int
    offset: int
    items: list[PostingOut]
