"""Admin endpoints: jobs refresh (plan 1.5), extraction and Scholar (plan 2.4/2.5).

Guarded by the ``X-Admin-Token`` dependency (AGENTS 3.10.1). The router is
thin: validate input → build integration clients (composition-root duty) →
call one service → map rows to summary schemas. The structured LLM arrives
via the ``get_structured_llm`` dependency so tests can inject a fake.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_structured_llm, require_admin_token
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, get_db
from app.integrations.gemini.client import StructuredLLM
from app.integrations.serpapi.client import SerpApiClient
from app.models import RefreshRun
from app.schemas.admin import (
    ExtractionSummary,
    RefreshJobsRequest,
    RefreshSummary,
    ScholarRefreshSummary,
)
from app.services import extraction_service, ingestion_service, research_service

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


@router.post(
    "/extract",
    response_model=ExtractionSummary,
    summary="Run Gemini skill extraction on pending postings",
)
def extract_postings(
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    llm: StructuredLLM = Depends(get_structured_llm),
) -> ExtractionSummary:
    """Extract skills/seniority/PhD flags from postings not yet extracted.

    Args:
        limit: optional cap on postings processed this run (all pending when
            omitted).
        db: request session.
        llm: injected StructuredLLM (real Gemini client or a test fake).

    Returns:
        Counts of postings marked done, failed and skipped (plan 2.4.4).
        Individual batch failures never abort the run — postings whose batch
        fails twice are marked ``failed`` (up to 3 attempts, plan 4.7).

    Raises:
        ConfigError (500): Gemini key/model not configured — surfaced before
            any LLM call is attempted.
    """
    counts = extraction_service.run_extraction(db, llm, limit=limit)
    return ExtractionSummary(**counts)


@router.post(
    "/refresh/scholar",
    response_model=ScholarRefreshSummary,
    summary="Fetch recent Scholar papers and generate research themes",
)
def refresh_scholar(
    db: Session = Depends(get_db),
    llm: StructuredLLM = Depends(get_structured_llm),
) -> ScholarRefreshSummary:
    """Run one Scholar refresh: papers per subfield + Gemini research themes.

    Args:
        db: request session.
        llm: injected StructuredLLM for theme generation.

    Returns:
        ScholarRefreshSummary. A subfield with zero results (or a failed
        theme call) is reported in ``errors``/counts — never a raised HTTP
        error (plan 2.5; empty Scholar results are valid).
    """
    client = _build_client(get_settings())
    try:
        run = research_service.refresh_scholar(db, client, llm)
    finally:
        client.close()
    details = run.details or {}
    return ScholarRefreshSummary(
        run_id=run.id,
        kind=run.kind,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        serpapi_calls=run.serpapi_calls,
        papers_stored=int(details.get("papers_stored", 0)),
        subfields_refreshed=int(details.get("subfields_refreshed", 0)),
        subfields_with_themes=int(details.get("subfields_with_themes", 0)),
        errors=list(details.get("errors", [])),
    )
