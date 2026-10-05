"""Schemas for the admin refresh endpoint (plan 1.5): request and run summary."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RefreshJobsRequest(BaseModel):
    """Body of ``POST /admin/refresh/jobs``.

    ``subfield_id`` is optional: when given, only that subfield's queries run
    (partial refresh); otherwise every subfield in the plan.
    """

    mode: Literal["bootstrap", "daily"]
    region: Literal["global", "india"]
    subfield_id: str | None = None


class RefreshSummary(BaseModel):
    """What one ingestion run did: counts, errors and timing (plan 1.3.5)."""

    run_id: int
    kind: str
    mode: str
    region: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    serpapi_calls: int
    postings_seen: int
    postings_new: int
    postings_deactivated: int
    queries_run: int
    errors: list[str] = Field(default_factory=list)
