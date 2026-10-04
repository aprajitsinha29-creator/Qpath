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
from app.db.seed import seed_reference_data
from app.db.session import SessionLocal, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(current_app: FastAPI) -> AsyncIterator[None]:
    """Startup: create tables and seed reference data; shutdown: nothing yet.

    Seeding is idempotent (merge by primary key), so restarts never duplicate rows.
    The APScheduler hook is deliberately left as a stub until Phase 5.

    Args:
        current_app: the app being served (unused; required by the lifespan signature).

    Yields:
        None while the application is serving.

    TODO(phase-5): start APScheduler here when SCHEDULER_ENABLED is true, and
    shut it down on exit.
    """
    init_db()
    with SessionLocal() as db:
        seed_reference_data(db)
    logger.info("database ready (create_all + reference seed)")
    yield


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
        title="Quantum Pathfinder API",
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
