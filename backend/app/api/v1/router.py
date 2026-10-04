"""API v1 router aggregation — one ``include_router`` per feature as phases land."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
