"""Read-only vocabulary endpoint (carry-over from Phase 4 scope).

Thin router per AGENTS.md 3.3.1: call the service, return the schema. No
SerpApi or Gemini is involved — this serves the seeded controlled vocabulary
the frontend skills picker needs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.skills import SkillsListResponse
from app.services import skills_service

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=SkillsListResponse, summary="Full skills vocabulary")
def get_skills(db: Session = Depends(get_db)) -> SkillsListResponse:
    """Return the entire seeded skills vocabulary sorted by name.

    Args:
        db: request session.

    Returns:
        SkillsListResponse with every skill: id, name, aliases, subfield_ids.
    """
    return SkillsListResponse(skills=skills_service.list_skills(db))
