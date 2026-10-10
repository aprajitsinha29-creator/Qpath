"""Schemas for the Phase 5 opportunity-tracker endpoints (plan 5.1–5.3).

Request/response projections only — ORM rows never reach the router
(AGENTS 3.3.4). ``ProfileOut`` is extended on :class:`app.schemas.quiz.ProfileOut`
(additive), so only the tracker-specific shapes live here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChosenPathIn(BaseModel):
    """``PUT /profiles/{id}/chosen-path`` body."""

    path_id: str = Field(min_length=1, description="Career path id from the seeded taxonomy")


class ChosenPathOut(BaseModel):
    """Response for the chosen-path PUT: the profile's tracked path."""

    profile_id: str
    chosen_path_id: str | None


class SeenOut(BaseModel):
    """``POST /profiles/{id}/seen`` response."""

    profile_id: str
    last_seen_at: datetime | None


class OpportunityItem(BaseModel):
    """One matched posting in the tracker feed (plan 5.3 item shape)."""

    posting_id: int
    title: str
    company: str
    location: str | None
    via: str | None
    apply_url: str | None
    is_internship: bool
    first_seen_at: datetime
    #: Strict comparison against the profile's last_seen_at (equal is NOT new).
    is_new: bool
    #: Match score 0-100, or None = "not enough information".
    match: float | None = Field(default=None, ge=0, le=100)
    #: Canonical names of the skills the posting shares with the profile.
    matched_skills: list[str] = Field(default_factory=list)


class OpportunitiesOut(BaseModel):
    """``GET /profiles/{id}/opportunities`` response (plan 5.3)."""

    profile_id: str
    path_id: str
    region: str
    first_visit: bool
    #: Total matched items independent of paging.
    total: int
    last_seen_at: datetime | None
    #: Latest SUCCESSFUL jobs refresh finish time, or None ("never refreshed").
    last_refreshed_at: datetime | None
    items: list[OpportunityItem]
