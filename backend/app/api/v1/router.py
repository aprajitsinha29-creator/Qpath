"""API v1 router aggregation — one ``include_router`` per feature as phases land.

Phase 1 adds taxonomy, pulse, meta and admin; quiz/profiles/paths arrive with
their phases (a route that exists before its feature would be a lie in the
OpenAPI schema).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, health, meta, pulse, taxonomy

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(taxonomy.router)
api_router.include_router(pulse.router)
api_router.include_router(meta.router)
api_router.include_router(admin.router)
