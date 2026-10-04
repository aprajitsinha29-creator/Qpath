"""Response schema for ``GET /api/v1/health`` (Phase 0)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health payload: overall status, build version, runtime env, database probe.

    ``db`` comes from a trivial ``SELECT 1``; ``status`` mirrors it so a caller
    can treat ``status == "ok"`` as "API and database both healthy".
    """

    status: Literal["ok", "error"]
    version: str
    env: str
    db: Literal["ok", "error"]
