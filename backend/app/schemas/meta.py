"""Schemas for ``GET /meta/serpapi-activity`` (plan 1.5).

Feeds the UI's "SerpApi activity" panel: today's live-call budget and the last
calls (both fixture and live) so SerpApi's role stays visible — a hackathon
judging criterion (meaningful SerpApi usage).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SerpApiCallOut(BaseModel):
    """One logged SerpApi call (no secrets: engine, query, source, status only)."""

    model_config = ConfigDict(from_attributes=True)  # validated from ORM rows

    id: int
    engine: str
    query: str
    source: str
    status: str
    created_at: datetime


class SerpApiActivity(BaseModel):
    """Activity-panel payload: mode, today's live usage vs cap, recent calls."""

    mode: str  # "fixtures" | "live" — mirrors SERPAPI_USE_FIXTURES
    live_calls_today: int
    daily_cap: int
    recent_calls: list[SerpApiCallOut]
