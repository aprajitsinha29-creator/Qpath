"""Health service: database probe + settings-backed status assembly for ``GET /health``.

Lives in ``services`` (not the router) because AGENTS.md 3.3.1 forbids DB queries
in routers — even a ``SELECT 1``.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def get_health_report(db: Session) -> HealthResponse:
    """Build the health payload for the current process.

    Args:
        db: request-scoped session (used only for the ``SELECT 1`` probe).

    Returns:
        HealthResponse with ``status``/``db`` set to ``"error"`` when the probe
        fails. The probe failure is logged and converted, never raised, so the
        health endpoint can always answer.
    """
    db_ok = _probe_database(db)
    return HealthResponse(
        status="ok" if db_ok else "error",
        version=__version__,
        env=get_settings().app_env,
        db="ok" if db_ok else "error",
    )


def _probe_database(db: Session) -> bool:
    """Run ``SELECT 1``; return True on success, False (with an ERROR log) on failure."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        logger.exception("health check: database probe failed")
        return False
