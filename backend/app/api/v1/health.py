"""``GET /health`` — liveness plus database probe (Phase 0).

Thin router per AGENTS.md 3.3.1: parse nothing, call one service, return a schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthResponse
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service and database status")
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Return ``{status, version, env, db}``; the ``db`` field comes from a ``SELECT 1`` probe.

    Args:
        db: request session supplied by the ``get_db`` dependency.

    Returns:
        HealthResponse — ``status``/``db`` are ``"error"`` if the probe failed.
    """
    return health_service.get_health_report(db)
