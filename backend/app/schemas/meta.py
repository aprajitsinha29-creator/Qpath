"""Schemas for ``GET /meta/serpapi-activity`` (plan 1.5).

Feeds the UI's "SerpApi activity" panel: today's live-call budget and the last
calls (both fixture and live) so SerpApi's role stays visible — a hackathon
judging criterion (meaningful SerpApi usage).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RefreshStatusEntry(BaseModel):
    """Summary of the latest run of one kind (jobs/scholar/extraction, plan 5.4)."""

    time: datetime | None = None
    status: str | None = None
    serpapi_calls: int | None = None
    counts: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class RefreshStatus(BaseModel):
    """``GET /meta/refresh-status`` response: latest run per kind (plan 5.4).

    Kinds never run are null, so the shape is stable for the UI.
    """

    jobs: RefreshStatusEntry | None = None
    scholar: RefreshStatusEntry | None = None
    extraction: RefreshStatusEntry | None = None


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


class EngineCallCounts(BaseModel):
    """Per-engine SerpApi call split for the Method page's honest-usage block."""

    live: int = 0
    fixture: int = 0


class MethodStats(BaseModel):
    """``GET /meta/method`` response (plan 7 Method page numbers).

    Every field is a fact straight from a table count/timestamp — no derived
    or invented numbers (AGENTS.md 3.11: never fabricate).
    """

    #: {engine: {live, fixture}} call totals over all time from serpapi_call_log.
    serpapi_calls: dict[str, EngineCallCounts] = Field(default_factory=dict)
    postings_total: int
    postings_active: int
    extraction_done: int
    #: Total themes across all subfield batches (research_themes rows).
    themes_count: int
    #: Latest successful jobs refresh finish time, or None if never run.
    last_jobs_refresh: datetime | None = None
    #: Latest successful scholar refresh finish time, or None if never run.
    last_scholar_refresh: datetime | None = None
