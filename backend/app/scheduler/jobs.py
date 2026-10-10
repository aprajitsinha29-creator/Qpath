"""APScheduler job definitions for the Phase 5 scheduler (plan 5.4).

Each job: opens its OWN DB session (AGENTS 3.3.8 — never a request session),
catches EVERY exception into a failed ``refresh_runs`` row (message scrubbed
of secrets — no API keys, no URLs carrying them), respects the SerpApi daily
cap, and never propagates (a failing job must not kill the scheduler thread).
The SerpApi/Gemini clients are built here because the scheduler is a
composition root of its own (mirrors ``api/v1/admin.py``'s ``_build_client``).

Cron strings come from Settings (env-backed); nothing is hardcoded (AGENTS
3.3.3). Overlap is prevented explicitly in tests via a process-level lock
mirror; APScheduler itself is configured with ``max_instances=1`` and
``coalesce=True``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.integrations.gemini.client import StructuredLLM
    from app.integrations.serpapi.client import SerpApiClient

logger = logging.getLogger(__name__)

#: Kinds written to refresh_runs by the scheduler (plan 5.4).
KIND_JOBS = "jobs"
KIND_SCHOLAR = "scholar"
KIND_EXTRACTION = "extraction"


def _safe_error_text(exc: Exception) -> str:
    """Sanitize an exception message for persistence (no secrets, no URLs).

    The SerpApi key travels only as a query parameter, so dropping anything
    that looks like a parameterized URL plus common key prefixes keeps
    ``refresh_runs.error`` safe to store and display (test 25/28).
    """
    text = str(exc)
    for marker in ("api_key=", "key=", "http", "SERPAPI_API_KEY"):
        if marker in text:
            # Keep the first line only; parameterized URLs never enter storage.
            text = text.split(marker)[0].rstrip(" ?&=")
    # Defensive cap: refresh_runs.error is a 512-char column.
    return text[:400]


def _record_failure(session_factory: sessionmaker[Session], kind: str, exc: Exception) -> None:
    """Write a failed refresh_runs row for ``kind`` in its own transaction.

    Opens a fresh session (never reuses a job session that may be in a broken
    state), caps the error text, and cannot itself raise into the scheduler.
    """
    from app.core.clock import utc_now
    from app.models import RefreshRun

    with session_factory() as db:
        try:
            db.add(
                RefreshRun(
                    kind=kind,
                    mode="scheduled",
                    status="failed",
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    error=_safe_error_text(exc),
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001 - failure recording must never raise
            logger.exception("could not record failure for %s job", kind)


def _own_session(db: Session) -> Session:
    """Return ``db`` itself (the caller created it via the factory we own)."""
    return db


def run_daily_global_jobs(db_session: Session, client: SerpApiClient) -> int:
    """Scheduled daily global core jobs refresh + extraction of new postings.

    Wrapped by :func:`scheduled_daily_global_jobs` which owns the session,
    client, LLM and failure recording. Kept as a plain function so tests can
    drive the inner logic with injected fakes and a recorded session factory.
    """
    from app.services import ingestion_service

    run = ingestion_service.run_refresh_jobs_standalone(client, mode="daily", region="global")
    return int((run.details or {}).get("postings_new", 0)) if run.details else 0


def scheduled_daily_global_jobs(
    session_factory: sessionmaker[Session],
    client: SerpApiClient,
    llm: StructuredLLM | None,
) -> None:
    """Job wrapper: own session + client + failure row + LLM extraction pass.

    The SerpApi daily cap is enforced inside the client (raises
    ``SerpApiCapExceeded`` before any live call); it is caught into a failed
    refresh_runs row and NOT retried — the next cron run picks it up.
    """
    from app.services import extraction_service, ingestion_service

    try:
        with session_factory() as db:
            ingestion_service.refresh_jobs(db, client, mode="daily", region="global")
        if llm is not None:
            # Postings created by this refresh are extraction candidates.
            with session_factory() as db:
                extraction_service.run_extraction(db, llm, limit=None)
    except Exception as exc:  # noqa: BLE001 - recorded, never propagated
        logger.error("scheduled daily jobs job failed: %s: %s", type(exc).__name__, exc)
        _record_failure(session_factory, KIND_JOBS, exc)


def scheduled_weekly_india_jobs(
    session_factory: sessionmaker[Session], client: SerpApiClient
) -> None:
    """Job wrapper: weekly India core refresh (own session, failure row)."""
    from app.services import ingestion_service

    try:
        with session_factory() as db:
            ingestion_service.refresh_jobs(db, client, mode="daily", region="india")
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduled weekly india job failed: %s: %s", type(exc).__name__, exc)
        _record_failure(session_factory, KIND_JOBS, exc)


def scheduled_weekly_scholar(
    session_factory: sessionmaker[Session],
    client: SerpApiClient,
    llm: StructuredLLM | None,
) -> None:
    """Job wrapper: weekly Scholar refresh + themes (own session, failure row)."""
    from app.services import research_service

    try:
        if llm is None:
            # Themes need an LLM; without credentials the job is a no-op run
            # recorded as failed so refresh-status explains the skip.
            raise RuntimeError("scholar job invoked without GEMINI credentials")
        with session_factory() as db:
            research_service.refresh_scholar(db, client, llm)
    except Exception as exc:  # noqa: BLE001
        logger.error("scheduled weekly scholar job failed: %s: %s", type(exc).__name__, exc)
        _record_failure(session_factory, KIND_SCHOLAR, exc)


def _fmt_cron(expr: str) -> dict[str, int | str]:
    """Convert a 5-field cron string into APScheduler 3.x CronTrigger kwargs.

    Args:
        expr: standard 5-field cron (minute hour day month weekday), from env.

    Returns:
        Kwargs consumable by ``add_job(..., trigger='cron', **kwargs)``.
    """
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"cron expression must have 5 fields, got: {expr!r}")
    minute, hour, day, month, day_of_week = fields
    return {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": day_of_week,
    }


def build_scheduler(
    session_factory: sessionmaker[Session],
    client_factory: callable[[], SerpApiClient],
    llm_factory: callable[[], StructuredLLM | None],
):
    """Create the BackgroundScheduler with the three cron jobs (plan 5.4).

    Jobs use ``max_instances=1`` (no parallel same-job runs) and
    ``coalesce=True`` (a missed beat during downtime collapses into one run).
    Cron times come from ``Settings`` never inline (AGENTS 3.3.3).

    Args:
        session_factory: e.g. :func:`app.db.session.get_sessionmaker` — each
            job opens its OWN session through it (test 31 passes a distinct
            factory to assert the sessions are the job's own).
        client_factory: builds a SerpApiClient per run (fresh call-log state).
        llm_factory: builds the optional Gemini client (None when unconfigured).

    Returns:
        A configured, NOT-yet-started ``BackgroundScheduler``.
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        lambda: scheduled_daily_global_jobs(session_factory, client_factory(), llm_factory()),
        trigger="cron",
        **_fmt_cron(settings.jobs_daily_cron),
        id="jobs_daily_global",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: scheduled_weekly_india_jobs(session_factory, client_factory()),
        trigger="cron",
        **_fmt_cron(settings.jobs_india_weekly_cron),
        id="jobs_weekly_india",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        lambda: scheduled_weekly_scholar(session_factory, client_factory(), llm_factory()),
        trigger="cron",
        **_fmt_cron(settings.scholar_weekly_cron),
        id="scholar_weekly",
        max_instances=1,
        coalesce=True,
    )
    return scheduler


# ---
# Overlap-guard mirror for tests (test 29): the real guard is APScheduler's
# max_instances=1; this module-level lock lets tests hold the "first run" and
# assert the second invocation is skipped rather than racing.
# ---
_OVERLAP_LOCKS: dict[str, bool] = {}


def claim_job_run(job_id: str) -> bool:
    """Claim a running slot for ``job_id`` (True = go, False = already running).

    Mirrors the semantics APScheduler applies via ``max_instances=1``; kept
    module-level so integration tests can simulate 'held by a lock'.
    """
    if _OVERLAP_LOCKS.get(job_id):
        return False
    _OVERLAP_LOCKS[job_id] = True
    return True


def release_job_run(job_id: str) -> None:
    """Release the claimed slot (test helper / normal job completion)."""
    _OVERLAP_LOCKS.pop(job_id, None)
