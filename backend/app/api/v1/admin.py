"""Admin endpoints: ``POST /admin/refresh/jobs`` (plan 1.5).

Guarded by the ``X-Admin-Token`` dependency (AGENTS 3.10.1). The router is
thin: validate body → build the SerpApi client (composition-root duty) → run
the ingestion service → map the run row to the summary schema. Scholar and
extraction admin routes arrive with Phase 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin_token
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_db
from app.integrations.serpapi.client import SerpApiClient
from app.models import RefreshRun
from app.schemas.admin import RefreshJobsRequest, RefreshSummary
from app.services import ingestion_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


def _build_client(settings: Settings) -> SerpApiClient:
    """Create the SerpApiClient for one request-scoped ingestion run.

    Args:
        settings: cached settings (fixture/live mode, cap, optional fixture dir).

    Returns:
        A client whose call-log writes go through their own sessions
        (``SessionLocal``), never the request session (AGENTS 3.3.8). The
        fixture dir override keeps endpoint tests off the committed recordings.
    """
    from pathlib import Path

    fixture_dir = Path(settings.serpapi_fixture_dir) if settings.serpapi_fixture_dir else None
    return SerpApiClient(settings, SessionLocal, fixture_dir=fixture_dir)


def _to_summary(run: RefreshRun) -> RefreshSummary:
    """Map a persisted RefreshRun row onto the public summary schema.

    Args:
        run: the row returned by :func:`ingestion_service.refresh_jobs`.

    Returns:
        RefreshSummary with counts unpacked from ``details`` (the JSON blob
        keeps the schema stable while phases add counters).
    """
    details = run.details or {}
    return RefreshSummary(
        run_id=run.id,
        kind=run.kind,
        mode=run.mode,
        region=str(details.get("region", "")),
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        serpapi_calls=run.serpapi_calls,
        postings_seen=int(details.get("postings_seen", 0)),
        postings_new=int(details.get("postings_new", 0)),
        postings_deactivated=int(details.get("postings_deactivated", 0)),
        queries_run=int(details.get("queries_run", 0)),
        errors=list(details.get("errors", [])),
    )


@router.post(
    "/refresh/jobs",
    response_model=RefreshSummary,
    summary="Run a jobs ingestion (bootstrap or daily) for a region",
)
def refresh_jobs(
    request: RefreshJobsRequest,
    db: Session = Depends(get_db),
) -> RefreshSummary:
    """Trigger a jobs refresh and return the run summary.

    Args:
        request: ``{mode, region, subfield_id?}`` — ``bootstrap`` walks all
            query tiers with pagination (bounded by SERPAPI_JOBS_MAX_PAGES);
            ``daily`` runs the core queries once. ``subfield_id`` restricts
            the run to one subfield when given.
        db: request session.

    Returns:
        RefreshSummary with counts and per-query errors: one failed query
        never fails the request — the run reports ``status=partial`` instead
        (plan 1.3.3).

    Raises:
        ValidationError (422): unknown mode/region values (Pydantic Literal).
    """
    client = _build_client(get_settings())
    try:
        subfield_ids = [request.subfield_id] if request.subfield_id else None
        run = ingestion_service.refresh_jobs(
            db,
            client,
            mode=request.mode,
            region=request.region,
            subfield_ids=subfield_ids,
        )
    finally:
        # The default http client is owned by the client instance; always
        # release it so a request thread never leaks sockets.
        client.close()
    return _to_summary(run)
