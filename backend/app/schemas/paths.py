"""Schemas for the path-matcher endpoints (plan 4.3 / 4.5).

API-facing projections only: the services build these from ORM rows and pure
scoring output (AGENTS 3.3.4 — ORM models never reach the router). The
evidence block mirrors what the UI's EvidencePanel renders, and the grounded
JSON sent to Gemini is derived from these exact values, so anything the model
is allowed to cite is on screen (design decision 2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pulse import PostingOut


class SkillVocabOut(BaseModel):
    """One entry of the controlled skill vocabulary (drives the SkillPicker)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    aliases: list[str]
    subfield_ids: list[str]


class PathSkillShare(BaseModel):
    """A top skill shown in a path's evidence panel (share of extracted postings)."""

    skill_id: str
    name: str
    share: float = Field(ge=0, le=1)
    #: Percent rendering of ``share`` (1 decimal) — what the UI shows and what
    #: the explanation may cite (design decision 2).
    share_pct: float = Field(ge=0, le=100)


class PathEvidence(BaseModel):
    """Live Pulse evidence assembled for one path (plan 4.3).

    ``sample_postings`` are the newest active postings of the path's subfield
    (max 3) so the recommendation is grounded in real, linkable listings.
    """

    active_postings: int
    internship_postings: int
    top_skills: list[PathSkillShare]
    #: Share of postings with a stated PhD requirement (None when unknown).
    phd_share: float | None = Field(default=None, ge=0, le=1)
    #: Percent rendering of ``phd_share`` (1 decimal) or None.
    phd_share_pct: float | None = Field(default=None, ge=0, le=100)
    sample_postings: list[PostingOut]


class ScoreBreakdown(BaseModel):
    """Transparent score breakdown — all values are DISPLAY percents.

    ``interest``/``demand``/``readiness`` are 0-100 with 1 decimal, and
    ``weights`` are the same 40/30/30 as percents, so a reviewer can recompute
    ``score`` by hand: (i·40 + d·30 + r·30) / 100 (plan 4.8 check).
    """

    interest: float
    demand: float
    readiness: float
    weights: dict[str, float]


class PathExplanationOut(BaseModel):
    """One grounded explanation; ``generated_by`` lets the UI label honestly."""

    headline: str
    reasons: list[str]
    caveat: str
    next_step: str
    generated_by: Literal["llm", "template"]
    #: Gemini model for llm rows, None for templates.
    model: str | None = None
    generated_at: datetime | None = None


class PathResult(BaseModel):
    """One ranked career path with breakdown, evidence and cached explanation."""

    path_id: str
    title: str
    subfield_id: str
    rank: int
    score: float
    breakdown: ScoreBreakdown
    is_top3: bool
    #: active_postings < 8 → demand evidence is thin (plan 4.5).
    low_data: bool
    #: The subfield's core query hit the page cap in the latest bootstrap.
    saturated: bool
    evidence: PathEvidence
    #: Null until an explanation has been generated (or cached) for it.
    explanation: PathExplanationOut | None = None


class PathsOut(BaseModel):
    """``GET /profiles/{id}/paths`` response: ranked paths + context."""

    profile_id: str
    assessment_id: int
    region: str
    #: Present when >= 4 of 6 subfields hit the page cap (plan 4.5).
    saturation_note: str | None = None
    paths: list[PathResult]


class DeclaredSkillsIn(BaseModel):
    """``PUT /profiles/{id}/skills`` body: full replacement of declared skills."""

    skill_ids: list[str]


class SkillsOut(BaseModel):
    """The declared skills echoed with the profile id after a save."""

    profile_id: str
    skill_ids: list[str]
