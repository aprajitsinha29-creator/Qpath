"""Meta endpoints: ``GET /meta/serpapi-activity`` (plan 1.5),
``GET /meta/refresh-status`` (plan 5.4) and ``GET /meta/method`` (plan 7).

Thin routers: parse nothing, delegate to a service, return schemas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.meta import MethodStats, RefreshStatus, SerpApiActivity
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
    "/meta/method",
    response_model=MethodStats,
    summary="Method-page live numbers",
)
def get_method_stats(db: Session = Depends(get_db)) -> MethodStats:
    """Return honest corpus/usage stats for the Method page (plan 7).

    Args:
        db: request session.

    Returns:
        MethodStats — SerpApi calls by engine (live vs recorded), posting
        totals, extraction count, theme count and last refresh timestamps.
    """
    return meta_service.get_method_stats(db)


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
