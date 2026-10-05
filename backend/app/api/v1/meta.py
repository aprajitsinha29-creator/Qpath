"""Meta endpoints: ``GET /meta/serpapi-activity`` (plan 1.5).

``GET /meta/refresh-status`` is intentionally deferred to Phase 5 with the
scheduler; adding it now would return empty rows nobody consumes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.meta import SerpApiActivity
from app.services import meta_service

router = APIRouter(tags=["meta"])


@router.get(
    "/meta/serpapi-activity",
    response_model=SerpApiActivity,
    summary="SerpApi activity panel data",
)
def get_serpapi_activity(db: Session = Depends(get_db)) -> SerpApiActivity:
    """Return mode, today's live calls vs cap, and the last 20 logged calls.

    Args:
        db: request session.

    Returns:
        SerpApiActivity — no secrets, only engine/query/source/status rows.
    """
    return meta_service.get_serpapi_activity(db)
