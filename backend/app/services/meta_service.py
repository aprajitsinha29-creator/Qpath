"""Meta service: SerpApi activity panel data (plan 1.5).

Reads the ``serpapi_call_log`` (written by the client for every call, fixture
or live) and the settings' cap. No secrets are returned: only engine, query,
source and status.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SerpApiCallLog
from app.schemas.meta import SerpApiActivity, SerpApiCallOut

#: How many recent calls the activity panel shows (plan 1.5: "last 20 calls").
RECENT_CALLS_LIMIT = 20


def get_serpapi_activity(db: Session) -> SerpApiActivity:
    """Assemble today's live-call budget and the most recent calls.

    Args:
        db: request session.

    Returns:
        SerpApiActivity with ``mode`` ("fixtures"/"live"), today's live call
        count against the configured cap, and up to 20 recent calls, newest
        first.
    """
    from app.core.clock import utc_day_start

    settings = get_settings()
    day_start = utc_day_start()

    live_calls_today = int(
        db.scalar(
            select(func.count())
            .select_from(SerpApiCallLog)
            .where(
                SerpApiCallLog.source == "live",
                SerpApiCallLog.created_at >= day_start,
            )
        )
        or 0
    )

    recent = list(
        db.scalars(
            select(SerpApiCallLog).order_by(SerpApiCallLog.id.desc()).limit(RECENT_CALLS_LIMIT)
        )
    )

    return SerpApiActivity(
        mode="fixtures" if settings.serpapi_use_fixtures else "live",
        live_calls_today=live_calls_today,
        daily_cap=settings.serpapi_daily_call_cap,
        recent_calls=[SerpApiCallOut.model_validate(row) for row in recent],
    )
