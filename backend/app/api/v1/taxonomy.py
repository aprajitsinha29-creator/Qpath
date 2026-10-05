"""``GET /taxonomy`` — reference taxonomy (plan 1.5).

Thin router per AGENTS.md 3.3.1: no parsing, no queries — call the service,
return the schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.taxonomy import TaxonomyResponse
from app.services import taxonomy_service

router = APIRouter(tags=["taxonomy"])


@router.get(
    "/taxonomy", response_model=TaxonomyResponse, summary="Subfields, concepts, career paths"
)
def get_taxonomy(db: Session = Depends(get_db)) -> TaxonomyResponse:
    """Return the full reference taxonomy (seeded from app/data/*.json).

    Args:
        db: request session.

    Returns:
        TaxonomyResponse — subfields (ordered), concepts and career paths.
    """
    return taxonomy_service.get_taxonomy(db)
