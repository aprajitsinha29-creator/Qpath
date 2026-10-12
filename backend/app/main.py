"""Application factory: settings, logging, CORS, error handlers, router mounting, lifespan.

Lifespan creates tables at startup (migrations are a non-goal, AGENTS.md 3.3.8).
The APScheduler hook is deliberately left as a stub until Phase 5.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.db.seed import seed_quiz_questions, seed_reference_data
from app.db.session import SessionLocal, get_sessionmaker, init_db

logger = logging.getLogger(__name__)

#: Started only when SCHEDULER_ENABLED=true (plan 5.4: OFF by default).
_scheduler: object | None = None


@asynccontextmanager
async def lifespan(current_app: FastAPI) -> AsyncIterator[None]:
    """Startup: tables, seed, and (optionally) the APScheduler; shutdown: all closed.

    Seeding is idempotent (merge by primary key), so restarts never duplicate rows.
    The scheduler lives only while SCHEDULER_ENABLED is true and is shut down
    cleanly with the app (test 32: TestClient context manager exit stops it).

    Args:
        current_app: the app being served (unused; required by the lifespan signature).

    Yields:
        None while the application is serving.
    """
    global _scheduler
    init_db()
    with SessionLocal() as db:
        seed_reference_data(db)
        seed_quiz_questions(db)
    logger.info("database ready (create_all + reference seed)")

    if get_settings().scheduler_enabled:
        from app.api.deps import get_structured_llm_optional
        from app.integrations.serpapi.client import SerpApiClient
        from app.scheduler import jobs as scheduler_jobs

        def _client() -> SerpApiClient:
            from pathlib import Path

            settings = get_settings()
            fixture_dir = (
                Path(settings.serpapi_fixture_dir) if settings.serpapi_fixture_dir else None
            )
            return SerpApiClient(settings, SessionLocal, fixture_dir=fixture_dir)

        _scheduler = scheduler_jobs.build_scheduler(
            get_sessionmaker(),
            _client,
            get_structured_llm_optional,
        )
        _scheduler.start()  # type: ignore[attr-defined]
        logger.info("scheduler started (3 cron jobs)")
    yield
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)  # type: ignore[attr-defined]
            logger.info("scheduler stopped cleanly")
        finally:
            _scheduler = None


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Reads Settings once (fail-fast for invalid live-mode config), configures
    logging, installs CORS + central error handlers, and mounts the v1 router
    under ``/api/v1``.

    Returns:
        The configured FastAPI instance.
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    application = FastAPI(
        title="QPath API",
        version=__version__,
        description="Live-data career navigator for quantum computing.",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(application)
    application.include_router(api_router, prefix="/api/v1")
    return application


# Uvicorn entry point (`make dev-backend`): built at import so a broken
# configuration fails fast before the server accepts traffic.
app = create_app()
