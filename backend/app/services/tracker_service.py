"""Tracker service: chosen path, seen markers, and the opportunities feed (plan 5.1-5.3).

Orchestration only (AGENTS 3.3.1): scoring normalization comes from
:mod:`scoring_service`, matching from :mod:`match_service`, and the visibility
query mirrors the pulse_service counting rules (both tiers for the feed).
Ordering happens in Python on the materialized feed rows: SQLite has no stable
mixed-direction composite sort for nullable floats, so the plan's explicit
deterministic order (match desc, first_seen desc, id) is applied here with a
sort key rather than in SQL.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import (
    AssessmentRequiredError,
    InvalidPathError,
    NotFoundError,
    PathRequiredError,
)
from app.models import (
    Assessment,
    CareerPath,
    JobPosting,
    JobPostingSkill,
    JobPostingSubfield,
    PulseSnapshot,
    RefreshRun,
    Skill,
    Subfield,
)
from app.schemas.opportunities import (
    ChosenPathOut,
    OpportunitiesOut,
    OpportunityItem,
    SeenOut,
)
from app.services import quiz_service
from app.services.match_service import posting_match

logger = logging.getLogger(__name__)

#: Region whose latest successful jobs refresh sets ``last_refreshed_at`` and
#: the default feed region (plan 5.3).
DEFAULT_FEED_REGION = "global"


def set_chosen_path(db: Session, profile_id: str, path_id: str) -> ChosenPathOut:
    """Track (or switch) the profile's chosen career path (plan 5.1).

    Re-PUT with a different valid path switches the tracked path.

    Args:
        db: request session.
        profile_id: UUID path parameter.
        path_id: career path id from the seeded taxonomy (must exist).

    Returns:
        ChosenPathOut carrying the tracked path id.

    Raises:
        NotFoundError: unknown profile (404).
        InvalidPathError: unknown path id (422 ``invalid_path``).
    """
    profile = quiz_service.get_profile(db, profile_id)  # 404 gate
    path = db.get(CareerPath, path_id)
    if path is None:
        raise InvalidPathError(f"unknown career path '{path_id}'")
    old = profile.chosen_path_id
    profile.chosen_path_id = path.id
    db.commit()
    logger.info("chosen path set: profile=%s path=%s (was %s)", profile.id, path.id, old)
    return ChosenPathOut(profile_id=profile.id, chosen_path_id=profile.chosen_path_id)


def mark_seen(db: Session, profile_id: str, now: Callable[[], datetime] | None = None) -> SeenOut:
    """Set the profile's ``last_seen_at`` to now via the injectable clock (plan 5.1).

    The frontend calls this explicitly after the user has viewed the feed;
    ``GET`` never does (so NEW badges do not vanish on refresh by accident).

    Args:
        db: request session.
        profile_id: UUID path parameter.
        now: injectable clock (defaults to :func:`utc_now`) so tests control
            time without sleeps or a time library (prerequisite (d)).

    Returns:
        SeenOut with the new marker.

    Raises:
        NotFoundError: unknown profile (404).
    """
    profile = quiz_service.get_profile(db, profile_id)
    stamp = (now or utc_now)()
    profile.last_seen_at = stamp
    db.commit()
    logger.info("profile seen: profile=%s at=%s", profile.id, stamp)
    return SeenOut(profile_id=profile.id, last_seen_at=stamp)


def get_opportunities(
    db: Session,
    profile_id: str,
    *,
    region: str = DEFAULT_FEED_REGION,
    internship: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    now: Callable[[], datetime] | None = None,
) -> OpportunitiesOut:
    """Build the matched-opportunities feed WITHOUT touching ``last_seen_at`` (plan 5.3).

    Source: active postings linked to the chosen path's subfield in the
    requested region, BOTH tiers (tiers exist to keep demand fair, not to
    hide listings from a user). Per item, ``match`` is ``None`` ("not enough
    information") when the profile declared no skills, the posting was never
    successfully extracted, or it has no extracted skills — never a partial
    score built from readiness alone. ``readiness_n`` input comes from the LATEST assessment
    for the TRACKED PATH's subfield: the data model stores no posting-level
    primary subfield that is scored, so the tracked path's subfield is the
    fallback — recorded in ARCHITECTURE.md decision log.

    Args:
        db: request session.
        profile_id: UUID path parameter.
        region: ``global`` (default) or ``india``.
        internship: optional filter (True = internships only, False = only
            non-internships, None = both).
        limit/offset: paging; ``total`` is computed before slicing.
        now: injectable clock (kept for symmetry / future stale-checks).

    Returns:
        OpportunitiesOut sorted match desc, then first_seen desc, then id asc
        (deterministic), with ``first_visit`` and ``last_refreshed_at``.

    Raises:
        NotFoundError: unknown profile (404).
        PathRequiredError: no (or a stale) chosen path (409 ``path_required``).
        AssessmentRequiredError: no diagnostic submitted (409
            ``assessment_required``).
    """
    profile = quiz_service.get_profile(db, profile_id)
    if not profile.chosen_path_id:
        raise PathRequiredError("track a career path before requesting opportunities")
    path = db.get(CareerPath, profile.chosen_path_id)
    if path is None:
        # Reference data was re-seeded without this path; treat as "track
        # again" rather than an internal-inconsistency 404.
        logger.warning("profile %s tracks unknown path id", profile_id)
        raise PathRequiredError("tracked path no longer exists — pick one again")

    # The readiness input needs a diagnostic; no assessment -> 409 guard.
    assessment = db.scalar(
        select(Assessment)
        .where(Assessment.profile_id == profile.id)
        .order_by(Assessment.taken_at.desc(), Assessment.id.desc())
        .limit(1)
    )
    if assessment is None:
        raise AssessmentRequiredError(
            "complete the orientation diagnostic before matching opportunities"
        )
    readiness_raw = float(assessment.scores.get(path.subfield_id, 0.0))

    # Feed is read-only: NEVER write last_seen_at here (plan 5.1 rule).
    last_seen = profile.last_seen_at
    first_visit = last_seen is None
    declared_ids = list(profile.declared_skills)
    declared_set = set(declared_ids)

    # Visibility phase in SQL: region + subfield + active (+ internship).
    # Outer joins keep postings without extracted skills in the feed.
    stmt = (
        select(JobPosting, JobPostingSkill.skill_id, Skill.name)
        .join(JobPostingSubfield, JobPostingSubfield.posting_id == JobPosting.id)
        .outerjoin(JobPostingSkill, JobPostingSkill.posting_id == JobPosting.id)
        .outerjoin(Skill, Skill.id == JobPostingSkill.skill_id)
        .where(
            JobPostingSubfield.subfield_id == path.subfield_id,
            JobPostingSubfield.region == region,
            JobPosting.is_active.is_(True),
        )
    )
    if internship is not None:
        stmt = stmt.where(JobPosting.is_internship.is_(bool(internship)))
    rows = db.execute(stmt).all()

    # Materialization: unique postings with their extracted skill id/name pairs.
    postings: dict[int, JobPosting] = {}
    skills_by_posting: dict[int, list[tuple[str, str]]] = {}
    seen_postings: set[int] = set()
    for posting, skill_id, skill_name in rows:
        seen_postings.add(posting.id)
        postings[posting.id] = posting
        if skill_id and skill_name:
            skills_by_posting.setdefault(posting.id, []).append((skill_id, skill_name))

    match_of: dict[int, float | None] = {}
    matched_names_of: dict[int, list[str]] = {}
    for posting_id, pairs in skills_by_posting.items():
        posting = postings[posting_id]
        if posting.extraction_status == "done" and pairs:
            pair_map = dict(pairs)
            posting_skill_ids = list(pair_map)
            match = posting_match(posting_skill_ids, declared_ids, readiness_raw)
            matched = [pair_map[sid] for sid in posting_skill_ids if sid in declared_set]
            matched_names = sorted(matched)
            match_of[posting_id] = match
            matched_names_of[posting_id] = matched_names
        else:
            match_of[posting_id] = None
            matched_names_of[posting_id] = []

    items: list[OpportunityItem] = []
    for posting_id, posting in postings.items():
        is_new = last_seen is None or posting.first_seen_at > last_seen
        items.append(
            OpportunityItem(
                posting_id=posting_id,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                via=posting.via,
                apply_url=posting.apply_url,
                is_internship=posting.is_internship,
                first_seen_at=posting.first_seen_at,
                is_new=is_new,
                match=match_of.get(posting_id),
                matched_skills=matched_names_of.get(posting_id, []),
            )
        )

    # Deterministic order: match desc (None sorts last), first_seen desc, id asc.
    NEG_INF = float("-inf")

    def sort_key(item: OpportunityItem) -> tuple[float, float, int]:
        match = item.match if item.match is not None else NEG_INF
        return (-match, -item.first_seen_at.timestamp(), item.posting_id)

    items.sort(key=sort_key)
    total = len(items)
    window = items[offset : offset + limit]

    return OpportunitiesOut(
        profile_id=profile.id,
        path_id=path.id,
        region=region,
        first_visit=first_visit,
        total=total,
        last_seen_at=last_seen,
        last_refreshed_at=_latest_finished_jobs_refresh(db, region),
        items=window,
    )


def _latest_finished_jobs_refresh(db: Session, region: str) -> datetime | None:
    """Latest SUCCESSFUL jobs refresh for the requested region (plan 5.3).

    ``refresh_runs.details`` carries the region; rows for other regions are
    skipped, and rows predating that marker (None) count as global.

    Args:
        db: request session.
        region: ``global`` or ``india``.

    Returns:
        The newest ``finished_at`` among done/partial jobs runs for the
        region, or ``None`` when the region was never refreshed successfully.
    """
    runs = db.scalars(
        select(RefreshRun)
        .where(RefreshRun.kind == "jobs", RefreshRun.status.in_(["done", "partial"]))
        .order_by(RefreshRun.finished_at.desc().nullslast(), RefreshRun.id.desc())
    )
    for run in runs:
        details = run.details if isinstance(run.details, dict) else {}
        run_region = details.get("region")
        if run_region == region:
            return run.finished_at
    return None


def get_trend(
    db: Session, subfield_id: str, *, region: str = DEFAULT_FEED_REGION
) -> list[dict[str, object]]:
    """Snapshot series for one subfield/region, date ascending (plan 5.4).

    Args:
        db: request session.
        subfield_id: taxonomy id; must exist (404 otherwise).
        region: which region's snapshots to return.

    Returns:
        ``[{date, active, new, internships}]`` oldest-first; ``[]`` when the
        subfield exists but has no snapshots yet (UI shows "no history yet").

    Raises:
        NotFoundError: unknown subfield id (404).
    """
    if db.get(Subfield, subfield_id) is None:
        raise NotFoundError(f"unknown subfield '{subfield_id}'")
    rows = db.scalars(
        select(PulseSnapshot)
        .where(PulseSnapshot.subfield_id == subfield_id, PulseSnapshot.region == region)
        .order_by(PulseSnapshot.snapshot_date.asc())
    )
    return [
        {
            "date": row.snapshot_date.isoformat(),
            "active": row.active_postings,
            "new": row.new_postings,
            "internships": row.internship_postings,
        }
        for row in rows
    ]


def latest_refresh_per_kind(db: Session) -> dict[str, dict[str, object]]:
    """Last run per kind (jobs/scholar/extraction) with summary fields (plan 5.4).

    Args:
        db: request session.

    Returns:
        ``{kind: {time, status, serpapi_calls, counts, error}}`` — only kinds
        with at least one run appear; the router maps absent kinds to nulls
        so the response shape is stable for the UI.
    """
    result: dict[str, dict[str, object]] = {}
    runs = db.scalars(
        select(RefreshRun).order_by(RefreshRun.started_at.desc(), RefreshRun.id.desc())
    )
    for run in runs:
        if run.kind in result:
            continue  # first hit per kind in newest-first order IS the latest
        details = run.details if isinstance(run.details, dict) else {}
        counts = {k: v for k, v in details.items() if isinstance(v, (int, float))}
        result[run.kind] = {
            "time": run.finished_at or run.started_at,
            "status": run.status,
            "serpapi_calls": run.serpapi_calls,
            "counts": counts,
            "error": run.error,
        }
    return result


def upsert_day_snapshot_for_testing(
    db: Session,
    subfield_id: str,
    region: str,
    day: date,
    *,
    active: int,
    new: int,
    internships: int,
) -> None:
    """Test-only snapshot writer: seeds one (subfield, region, day) row exactly
    the way :func:`ingestion_service._upsert_pulse_snapshot` would, so tests 22
    (idempotent re-run) and 24 (trend ordering) can build history without a
    fake refresh. NOT called by any request path (no synthetic runtime data)."""
    row = db.scalar(
        select(PulseSnapshot).where(
            PulseSnapshot.subfield_id == subfield_id,
            PulseSnapshot.snapshot_date == day,
            PulseSnapshot.region == region,
        )
    )
    if row is None:
        row = PulseSnapshot(subfield_id=subfield_id, snapshot_date=day, region=region)
        db.add(row)
    row.active_postings = active
    row.new_postings = new
    row.internship_postings = internships
    db.commit()
