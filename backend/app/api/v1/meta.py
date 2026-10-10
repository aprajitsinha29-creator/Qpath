"""Meta endpoints: ``GET /meta/serpapi-activity`` (plan 1.5).

``GET /meta/refresh-status`` is intentionally deferred to Phase 5 with the
scheduler; adding it now would return empty rows nobody consumes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.meta import RefreshStatus, SerpApiActivity
from app.services import meta_service, tracker_service

router = APIRouter(tags=["meta"])


@router.get(
    "/meta/refresh-status",
    response_model=RefreshStatus,
    summary="Latest run per refresh kind",
)
def get_refresh_status(db: Session = Depends(get_db)) -> RefreshStatus:
    """Return the latest jobs/scholar/extraction run summaries (plan 5.4).

    Args:
        db: request session.

    Returns:
        RefreshStatus; kinds that never ran are null (stable UI shape).
    """
    latest = tracker_service.latest_refresh_per_kind(db)
    return RefreshStatus(
        jobs=latest.get("jobs"),  # type: ignore[arg-type]
        scholar=latest.get("scholar"),  # type: ignore[arg-type]
        extraction=latest.get("extraction"),  # type: ignore[arg-type]
    )


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
