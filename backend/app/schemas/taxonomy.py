"""Schemas for ``GET /taxonomy`` (plan 1.5): subfields + concepts + career paths.

Phase 1 serves it so the frontend can label pulse cards and (later) power the
diagnostic and path-matcher from one source of truth.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ConceptOut(BaseModel):
    """One learnable concept with its prerequisite chain (ids only)."""

    model_config = ConfigDict(from_attributes=True)  # build from ORM rows

    id: str
    subfield_id: str
    name: str
    description: str
    prerequisites: list[str]


class CareerPathOut(BaseModel):
    """One career path (1:1 with a scored subfield)."""

    model_config = ConfigDict(from_attributes=True)  # build from ORM rows

    id: str
    title: str
    subfield_id: str
    description: str
    typical_titles: list[str]


class SubfieldOut(BaseModel):
    """One subfield with its ``is_scored`` flag (``foundations`` is not scored)."""

    model_config = ConfigDict(from_attributes=True)  # build from ORM rows

    id: str
    name: str
    description: str
    sort_order: int
    is_scored: bool


class TaxonomyResponse(BaseModel):
    """The full reference taxonomy in one payload."""

    subfields: list[SubfieldOut]
    concepts: list[ConceptOut]
    career_paths: list[CareerPathOut]
