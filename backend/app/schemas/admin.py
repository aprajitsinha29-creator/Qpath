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


class ExtractionSummary(BaseModel):
    """Result of ``POST /admin/extract`` (plan 2.4.4).

    ``skipped`` counts eligible postings left unattempted because ``limit``
    cut the run short; postings at the 3-attempt cap are not reported here
    (they are excluded from the pool entirely, plan 4.7).
    """

    done: int
    failed: int
    skipped: int


class ScholarRefreshSummary(BaseModel):
    """Result of ``POST /admin/refresh/scholar`` (plan 2.5.3).

    ``papers_stored`` is the number of snapshots written (≈ queries × ≤20);
    ``subfields_refreshed``/``subfields_with_themes`` report per-subfield
    outcomes. A subfield with zero results or a theme-generation failure is
    recorded in ``errors``, never raised (plan 2.5 / task notes).
    """

    run_id: int
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    serpapi_calls: int
    papers_stored: int
    subfields_refreshed: int
    subfields_with_themes: int
    errors: list[str] = Field(default_factory=list)
