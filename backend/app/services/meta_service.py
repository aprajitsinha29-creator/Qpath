"""Meta service: SerpApi activity panel data (plan 1.5) and Method stats (plan 7).

Reads the ``serpapi_call_log`` (written by the client for every call, fixture
or live) and the settings' cap. No secrets are returned: only engine, query,
source and status. :func:`get_method_stats` aggregates honest usage/corpus
numbers for the Method page — every value is a table count or timestamp.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import JobPosting, RefreshRun, ResearchTheme, SerpApiCallLog
from app.schemas.meta import EngineCallCounts, MethodStats, SerpApiActivity, SerpApiCallOut

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


def get_method_stats(db: Session) -> MethodStats:
    """Aggregate the Method page's live numbers from the corpus tables.

    All counts run in SQL against the request session; no business logic, no
    derivation — the UI must show facts, not opinions about the data.

    Args:
        db: request session.

    Returns:
        MethodStats: SerpApi calls split by engine and source (live/fixture,
        all time), posting totals, extraction-done count, theme count, and
        the latest SUCCESSFUL jobs/scholar refresh timestamps (``None`` for
        kinds never run).
    """
    # One grouped query per dimension instead of N: per engine × source.
    call_rows = db.execute(
        select(
            SerpApiCallLog.engine,
            SerpApiCallLog.source,
            func.count(),
        ).group_by(SerpApiCallLog.engine, SerpApiCallLog.source)
    ).all()
    serpapi_calls: dict[str, EngineCallCounts] = {}
    for engine, source, count in call_rows:
        counts = serpapi_calls.setdefault(engine, EngineCallCounts())
        if source == "live":
            counts.live = int(count)
        elif source == "fixture":
            counts.fixture = int(count)

    postings_total = int(db.scalar(select(func.count()).select_from(JobPosting)) or 0)
    postings_active = int(
        db.scalar(
            select(func.count()).select_from(JobPosting).where(JobPosting.is_active.is_(True))
        )
        or 0
    )
    extraction_done = int(
        db.scalar(
            select(func.count())
            .select_from(JobPosting)
            .where(JobPosting.extraction_status == "done")
        )
        or 0
    )
    themes_count = int(db.scalar(select(func.count()).select_from(ResearchTheme)) or 0)

    def _latest_refresh(kind: str) -> object | None:
        # Successful runs only: a failed run should not advertise freshness.
        row = db.scalars(
            select(RefreshRun)
            .where(RefreshRun.kind == kind, RefreshRun.status.in_(["done", "partial"]))
            .order_by(RefreshRun.finished_at.desc().nullslast(), RefreshRun.id.desc())
            .limit(1)
        ).first()
        return row.finished_at if row is not None else None

    return MethodStats(
        serpapi_calls=serpapi_calls,
        postings_total=postings_total,
        postings_active=postings_active,
        extraction_done=extraction_done,
        themes_count=themes_count,
        last_jobs_refresh=_latest_refresh("jobs"),  # type: ignore[arg-type]
        last_scholar_refresh=_latest_refresh("scholar"),  # type: ignore[arg-type]
    )
