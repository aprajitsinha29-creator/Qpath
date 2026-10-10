"""Schemas for the skills vocabulary and declared-skills endpoints (carry-over).

These were cut from Phase 4 and are implemented now. Payloads are validated
strictly: unknown or malformed skill ids must fail closed at the boundary so
the vocabulary stays the contract for every downstream computation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillOut(BaseModel):
    """One vocabulary entry as exposed by ``GET /skills`` (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    aliases: list[str]
    subfield_ids: list[str]


class DeclaredSkillsIn(BaseModel):
    """``PUT /profiles/{id}/skills`` body: the complete replacement list."""

    skill_ids: list[str] = Field(
        description="Skill ids from the vocabulary; replaces the whole list"
    )
