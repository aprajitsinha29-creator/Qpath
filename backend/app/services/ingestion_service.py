"""Jobs ingestion service: run SerpApi Google Jobs queries and upsert postings.

Phase 1 step 1.3. Sits between the API/scheduler and the integration layer:
takes a :class:`SerpApiClient`, walks the job query plan (plan 4.6) for the
requested mode/region, parses each response and upserts the results. After the
run it deactivates stale postings (not re-seen for 14 days) and upserts today's
pulse snapshot per subfield/region, then records everything in one
``refresh_runs`` row.

Timestamps: all DB datetimes are naive UTC — see ``app.core.clock`` for why.

Failure policy (plan 1.3.3): a per-query failure — including
:class:`FixtureMissingError`, which simply means "no more recorded pages" in
fixture mode — never aborts the run. Errors are collected into
``refresh_runs.details`` and the run still finishes with a summary.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import utc_day_start, utc_now
from app.core.config import get_settings
from app.core.errors import AppError, FixtureMissingError
from app.integrations.serpapi.client import SerpApiClient
from app.integrations.serpapi.parsers import (
    detect_internship,
    iter_job_results,
    make_dedupe_key,
    parse_next_page_token,
)
from app.integrations.serpapi.queries import (
    JOB_QUERY_PLAN,
    REGION_PARAMS,
    QuerySpec,
    job_fixture_variant,
)
from app.models import JobPosting, JobPostingSubfield, PulseSnapshot, RefreshRun

logger = logging.getLogger(__name__)

#: Postings not re-seen within this window are marked inactive (plan 1.3.4).
#: Why 14 days: SerpApi sampling is noisy — a posting can vanish from page 1
#: without disappearing from the market; two weeks is a conservative decay.
STALE_AFTER_DAYS = 14

#: Number of result pages fetched per query in bootstrap mode, bounded by
#: SERPAPI_JOBS_MAX_PAGES (settings are the only source — AGENTS 3.3.3).
_DAILY_PAGES = 1

REGIONS = ("global", "india")


def _region_params(region: str) -> tuple[str | None, str | None]:
    """Return (location, gl) for the region, or raise ValueError for unknown regions.

    Raises:
        ValueError: region is not ``global``/``india`` (validated upstream too).
    """
    if region not in REGION_PARAMS:
        raise ValueError(f"unknown region: {region!r}")
    params = REGION_PARAMS[region]
    return params["location"], params["gl"]


def _specs_for(mode: str, region: str, subfield_ids: list[str] | None) -> list[QuerySpec]:
    """Select the query specs for one ingestion run (plan 4.6 modes).

    Args:
        mode: ``bootstrap`` (all tiers, paginated) or ``daily`` (core only, 1 page).
        region: ``global`` or ``india`` (only affects request params, not the plan).
        subfield_ids: optional restriction to these subfields (admin partial refresh).

    Returns:
        The ordered query specs to run.
    """
    specs = list(JOB_QUERY_PLAN)
    if subfield_ids:
        wanted = set(subfield_ids)
        specs = [spec for spec in specs if spec.subfield_id in wanted]
    if mode == "daily":
        # Daily runs answer "is demand still there": core queries only, 1 page.
        specs = [spec for spec in specs if spec.tier == "core"]
    return specs


def _upsert_posting(db: Session, parsed: Any, seen_at: datetime) -> tuple[JobPosting, bool]:
    """Insert or refresh one posting by dedupe key.

    Args:
        db: the run's session (single transaction per run).
        parsed: a ParsedJob from the parser layer.
        seen_at: timestamp for first_seen_at/last_seen_at.

    Returns:
        ``(posting, is_new)`` where is_new tells whether a row was created.
    """
    dedupe_key = make_dedupe_key(parsed.title, parsed.company, parsed.location)
    posting = db.scalar(select(JobPosting).where(JobPosting.dedupe_key == dedupe_key))
    if posting is None:
        posting = JobPosting(
            dedupe_key=dedupe_key,
            title=parsed.title,
            company=parsed.company,
            location=parsed.location,
            via=parsed.via,
            description=parsed.description,
            apply_url=parsed.apply_url,
            serp_job_id=parsed.serp_job_id,
            extensions=parsed.extensions,
            # Rule-based detection (Phase 1); Phase 2 ORs the model's flag on top.
            is_internship=detect_internship(parsed.title, parsed.extensions),
            first_seen_at=seen_at,
            last_seen_at=seen_at,
            is_active=True,
        )
        db.add(posting)
        db.flush()  # assign posting.id before link rows reference it
        return posting, True

    # Re-seen: keep first_seen_at (identity's birthday) but refresh everything
    # that describes the posting's current life on the market.
    posting.last_seen_at = seen_at
    posting.serp_job_id = parsed.serp_job_id or posting.serp_job_id
    posting.title = parsed.title
    posting.company = parsed.company
    posting.location = parsed.location
    posting.via = parsed.via or posting.via
    posting.description = parsed.description or posting.description
    posting.apply_url = parsed.apply_url or posting.apply_url
    posting.extensions = parsed.extensions
    posting.is_active = True  # a re-seen stale posting comes back to life
    return posting, False


def _upsert_link(
    db: Session,
    posting: JobPosting,
    *,
    subfield_id: str,
    region: str,
    tier: str,
    source_query: str,
    seen_at: datetime,
) -> None:
    """Insert or refresh the (posting, subfield, region) link row.

    Tier policy (plan 1.3.2 / ARCHITECTURE decision log): if a posting was
    already linked to this subfield+region as ``core``, a later ``extended``
    discovery must NOT downgrade it — core is kept. An extended link is
    upgraded when the same posting is later found via the core query.
    """
    link = db.scalar(
        select(JobPostingSubfield).where(
            JobPostingSubfield.posting_id == posting.id,
            JobPostingSubfield.subfield_id == subfield_id,
            JobPostingSubfield.region == region,
        )
    )
    if link is None:
        db.add(
            JobPostingSubfield(
                posting_id=posting.id,
                subfield_id=subfield_id,
                region=region,
                tier=tier,
                source_query=source_query,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
            )
        )
        return
    link.last_seen_at = seen_at
    # source_query must reflect the query of the RETAINED tier: a posting
    # found by the core query and re-found by an extended one keeps its core
    # provenance. (A subfield has exactly one core query, so same-tier
    # re-discovery always rewrites the same value.)
    if link.tier == "extended" and tier == "core":
        link.tier = "core"
        link.source_query = source_query
    elif link.tier == tier:
        link.source_query = source_query


def _ingest_one_query(
    db: Session,
    client: SerpApiClient,
    spec: QuerySpec,
    *,
    mode: str,
    region: str,
    seen_at: datetime,
    max_pages: int,
) -> dict[str, Any]:
    """Run one query (plus pagination) and upsert everything it found.

    Args:
        db: the run's session.
        client: SerpApiClient in fixture or live mode.
        spec: the query to run.
        mode: bootstrap paginates (bounded by max_pages), daily fetches 1 page.
        region: ``global``/``india``.
        seen_at: timestamp stamped on postings/links seen in this run.
        max_pages: upper bound on pages in bootstrap mode.

    Returns:
        ``{"calls": n, "seen": n, "new": n, "errors": [..]}`` for this query.

    Note:
        The session is committed after each page BEFORE the next client call:
        the client logs calls through its own session (AGENTS 3.4.4), and
        SQLite serializes writers — holding an open write transaction across
        a client call would deadlock the call-log INSERT. Upserts are
        idempotent, so per-page commits cannot produce duplicates.
    """
    location, gl = _region_params(region)
    calls = seen = new = 0
    errors: list[str] = []
    next_page_token: str | None = None
    page = 0
    # True only when pagination stopped because max_pages was reached WHILE a
    # next page was still pending — i.e. the sample is truncated by the cap
    # (feeds the Phase 4 saturation flag, plan 4.2). A pending token that ends
    # in FixtureMissingError or a no-token page is "end of data", not a cap.
    hit_page_cap = False

    while page < max_pages:
        page += 1
        try:
            payload = client.search_jobs(
                spec.query,
                location=location,
                gl=gl,
                next_page_token=next_page_token,
                fixture_variant=job_fixture_variant(region, page),
            )
        except FixtureMissingError as exc:
            # Fixture mode, page beyond the recordings: the normal end of
            # pagination, not a failure (task brief + AGENTS 3.4.3 note).
            logger.info("fixture missing for %r p%d — end of data (%s)", spec.query, page, exc.code)
            break
        except AppError as exc:
            # Any other per-query failure is recorded and the run continues
            # (plan 1.3.3) — one bad query must not kill the whole refresh.
            logger.warning("query %r failed: %s", spec.query, exc.message)
            errors.append(f"{spec.query}: {exc.code}: {exc.message}")
            break

        calls += 1
        for parsed in iter_job_results(payload):
            seen += 1
            posting, is_new = _upsert_posting(db, parsed, seen_at)
            if is_new:
                new += 1
            _upsert_link(
                db,
                posting,
                subfield_id=spec.subfield_id,
                region=region,
                tier=spec.tier,
                source_query=spec.query,
                seen_at=seen_at,
            )
        # Release the write lock before the next client call (see docstring):
        # the call log writes through a separate session and SQLite allows a
        # single writer. Idempotent upserts make partial commits safe.
        db.commit()

        if mode != "bootstrap":
            break
        next_page_token = parse_next_page_token(payload)
        if next_page_token is None:
            break
    else:
        # while-condition exit (page == max_pages): if a token is still
        # pending, the cap truncated this query's results.
        hit_page_cap = next_page_token is not None

    return {
        "calls": calls,
        "seen": seen,
        "new": new,
        "errors": errors,
        "hit_page_cap": hit_page_cap,
    }


def _deactivate_stale_postings(db: Session, now: datetime) -> int:
    """Mark postings inactive when not re-seen within STALE_AFTER_DAYS.

    Rows are updated (never deleted) so first_seen history survives for
    trend computation (plan 1.3.4).

    Returns:
        How many postings were deactivated.
    """
    cutoff = now - timedelta(days=STALE_AFTER_DAYS)
    stale = list(db.scalars(select(JobPosting).where(JobPosting.is_active.is_(True))))
    to_deactivate = [posting for posting in stale if posting.last_seen_at < cutoff]
    for posting in to_deactivate:
        posting.is_active = False
    return len(to_deactivate)


def _upsert_pulse_snapshot(
    db: Session, subfield_id: str, region: str, day: datetime, now: datetime
) -> None:
    """Recompute and upsert today's pulse snapshot for one subfield/region.

    Counts (plan 1.3.4/1.4): ``active_postings`` counts only CORE-tier links —
    equalizing subfields that have unequal query counts (see ARCHITECTURE
    decision log). ``new_postings`` counts postings whose first_seen day is
    today. ``internship_postings`` counts active core postings flagged as
    internships. Unique on (subfield, date, region) keeps re-runs idempotent.
    """
    links = list(
        db.scalars(
            select(JobPostingSubfield).where(
                JobPostingSubfield.subfield_id == subfield_id,
                JobPostingSubfield.region == region,
                JobPostingSubfield.tier == "core",
            )
        )
    )
    posting_ids = [link.posting_id for link in links]
    day_start = utc_day_start()
    active = new = internships = 0
    if posting_ids:
        postings = list(db.scalars(select(JobPosting).where(JobPosting.id.in_(posting_ids))))
        for posting in postings:
            if not posting.is_active:
                continue
            active += 1
            if posting.first_seen_at >= day_start:
                new += 1
            if posting.is_internship:
                internships += 1

    snapshot = db.scalar(
        select(PulseSnapshot).where(
            PulseSnapshot.subfield_id == subfield_id,
            PulseSnapshot.snapshot_date == day_start.date(),
            PulseSnapshot.region == region,
        )
    )
    if snapshot is None:
        snapshot = PulseSnapshot(
            subfield_id=subfield_id,
            snapshot_date=day_start.date(),
            region=region,
        )
        db.add(snapshot)
    snapshot.active_postings = active
    snapshot.new_postings = new
    snapshot.internship_postings = internships
    snapshot.updated_at = now


def refresh_jobs(
    db: Session,
    client: SerpApiClient,
    *,
    mode: str,
    region: str,
    subfield_ids: list[str] | None = None,
) -> RefreshRun:
    """Run one jobs ingestion and return the persisted RefreshRun row.

    Args:
        db: session for the whole run (one transaction).
        client: SerpApiClient (fixture or live).
        mode: ``bootstrap`` (all query tiers, paginated) or ``daily`` (core, 1 page).
        region: ``global`` or ``india``.
        subfield_ids: optional restriction to a subset of subfields.

    Returns:
        The RefreshRun row (status done/partial, summary in ``details``).

    Raises:
        ValueError: unknown mode or region — a caller/contract bug, not data.

    Side effects:
        Writes job_postings, job_posting_subfields, pulse_snapshots and one
        refresh_runs row; commits the transaction.
    """
    if mode not in ("bootstrap", "daily"):
        raise ValueError(f"unknown mode: {mode!r}")
    _region_params(region)  # validates region early

    settings = get_settings()
    now = utc_now()

    specs = _specs_for(mode, region, subfield_ids)
    max_pages = settings.serpapi_jobs_max_pages if mode == "bootstrap" else _DAILY_PAGES

    totals = {"postings_seen": 0, "postings_new": 0, "serpapi_calls": 0}
    all_errors: list[str] = []
    page_capped: set[str] = set()
    for spec in specs:
        result = _ingest_one_query(
            db, client, spec, mode=mode, region=region, seen_at=now, max_pages=max_pages
        )
        totals["serpapi_calls"] += result["calls"]
        totals["postings_seen"] += result["seen"]
        totals["postings_new"] += result["new"]
        all_errors.extend(result["errors"])
        # Saturation (plan 4.2/4.5): only CORE-tier caps count, because demand
        # is computed from core links — an extended-query cap cannot compress
        # a subfield's headline count.
        if result["hit_page_cap"] and spec.tier == "core":
            page_capped.add(spec.subfield_id)

    # Post-run maintenance happens even when some queries failed: partial
    # data is still worth snapshotting (plan 1.3.3/1.3.4).
    deactivated = _deactivate_stale_postings(db, now)
    for subfield_id in sorted({spec.subfield_id for spec in specs}):
        _upsert_pulse_snapshot(db, subfield_id, region, now, now)

    # The run row is written AFTER the queries (plan 1.3.5) — creating it up
    # front would hold a write transaction across client calls and deadlock
    # the client's own-session call log on SQLite (single-writer).
    run = RefreshRun(kind="jobs", mode=mode, started_at=now, details={})
    run.finished_at = utc_now()
    run.status = "partial" if all_errors else "done"
    run.serpapi_calls = totals["serpapi_calls"]
    run.details = {
        **totals,
        "region": region,
        "queries_run": len(specs),
        "postings_deactivated": deactivated,
        # Core queries truncated by SERPAPI_JOBS_MAX_PAGES in this run (always
        # empty for daily runs — they fetch one page). Read by paths_service
        # for the Phase 4 saturation flag.
        "page_cap_subfields": sorted(page_capped),
        "errors": all_errors,
    }
    db.add(run)
    db.commit()
    logger.info(
        "refresh_jobs(%s/%s): %d new postings, %d calls, %d errors",
        mode,
        region,
        totals["postings_new"],
        totals["serpapi_calls"],
        len(all_errors),
    )
    return run


def run_refresh_jobs_standalone(
    client: SerpApiClient,
    *,
    mode: str,
    region: str,
    subfield_ids: list[str] | None = None,
) -> RefreshRun:
    """Run a refresh with its OWN session — for schedulers/scripts, not requests.

    Opens a fresh :class:`SessionLocal` and closes it, because background jobs
    must never reuse a request session (AGENTS.md 3.3.8). The scheduler
    (Phase 5) will call this wrapper.

    Raises:
        SQLAlchemyError: re-raised after logging so the scheduler can report
            the failed job; the transaction is rolled back first.
    """
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            return refresh_jobs(db, client, mode=mode, region=region, subfield_ids=subfield_ids)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("standalone jobs refresh failed")
            raise
