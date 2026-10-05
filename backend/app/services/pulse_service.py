"""Pulse service: aggregates stored postings into the six Market Pulse cards.

Phase 1 step 1.4. Pure read-side logic over the tables the ingestion service
writes: per subfield it counts core-sourced active postings (headline demand),
extended-only postings (``extra_postings``), internships, top companies, and
computes ``new_this_week`` — which stays ``null`` until the stored corpus spans
at least 2 distinct ingestion days, because with a single day of data "new
this week" would equal "everything" and mislead (plan 1.4; the UI renders
"tracking since <date>" instead).

Counting rules (see ARCHITECTURE.md decision log):
- ``active_postings`` counts postings whose link row is CORE tier only, so
  subfields with more queries get no artificial demand advantage.
- ``extra_postings`` counts postings linked only via extended queries; they
  still appear in posting lists.
- ``low_data`` is ``active_postings < 8`` (plan 4.5 constant, used by scoring
  in Phase 4 too — defined once here).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.models import JobPosting, JobPostingSubfield, Subfield

logger = logging.getLogger(__name__)

#: Below this many core-sourced active postings a card is flagged ``low_data``
#: and the UI must say demand evidence is thin (plan 1.4 / 4.5).
LOW_DATA_THRESHOLD = 8

#: "New this week" window used once the corpus spans ≥ 2 ingestion days.
NEW_THIS_WEEK_DAYS = 7

#: Minimum distinct first-seen days in the corpus before ``new_this_week``
#: becomes meaningful (plan 1.4: "spans ≥ 2 distinct ingestion days").
MIN_DAYS_FOR_NEW_POSTINGS = 2

#: Number of top companies shown per card.
TOP_COMPANIES_COUNT = 5

#: How many postings the default list endpoint returns.
DEFAULT_POSTINGS_LIMIT = 20

#: Length of the posting snippet shown in list views (plan 1.5: ~240 chars).
SNIPPET_LENGTH = 240


def to_posting_out(posting: JobPosting) -> dict[str, object]:
    """Project a JobPosting row onto the PostingOut schema shape (with snippet).

    Args:
        posting: an ORM row (never sent to the router directly — AGENTS 3.3.4).

    Returns:
        A dict matching ``schemas.pulse.PostingOut``; ``snippet`` is the first
        :data:`SNIPPET_LENGTH` characters of the description, or None.
    """
    description = posting.description or ""
    snippet = description[:SNIPPET_LENGTH] if description else None
    return {
        "id": posting.id,
        "title": posting.title,
        "company": posting.company,
        "location": posting.location,
        "via": posting.via,
        "apply_url": posting.apply_url,
        "is_internship": posting.is_internship,
        "first_seen_at": posting.first_seen_at,
        "snippet": snippet,
    }


def _active_core_posting_ids(db: Session, subfield_id: str, region: str) -> set[int]:
    """Return ids of active postings linked to the subfield/region via CORE tier.

    A join (not a count) because several aggregations need the id set and the
    posting rows themselves (companies, internships, first-seen days).
    """
    rows = db.execute(
        select(JobPosting.id)
        .join(JobPostingSubfield, JobPostingSubfield.posting_id == JobPosting.id)
        .where(
            JobPostingSubfield.subfield_id == subfield_id,
            JobPostingSubfield.region == region,
            JobPostingSubfield.tier == "core",
            JobPosting.is_active.is_(True),
        )
    )
    return {row[0] for row in rows.all()}


def _extra_posting_ids(db: Session, subfield_id: str, region: str) -> set[int]:
    """Return ids of active postings linked ONLY via extended-tier queries.

    These appear in posting lists but not in headline counts, keeping demand
    fair across subfields with unequal query counts (plan 4.6 fairness note).
    """
    rows = db.execute(
        select(JobPostingSubfield.posting_id, JobPostingSubfield.tier)
        .where(
            JobPostingSubfield.subfield_id == subfield_id,
            JobPostingSubfield.region == region,
            JobPosting.is_active.is_(True),
        )
        .join(JobPosting, JobPosting.id == JobPostingSubfield.posting_id)
    )
    seen: dict[int, set[str]] = {}
    for posting_id, tier in rows.all():
        seen.setdefault(posting_id, set()).add(tier)
    return {pid for pid, tiers in seen.items() if tiers == {"extended"}}


def _top_companies(db: Session, posting_ids: set[int]) -> list[str]:
    """Return the most frequent companies among the given postings (top N).

    Args:
        db: request session.
        posting_ids: postings to aggregate (both tiers — companies reflect the
            whole visible corpus of the card).

    Returns:
        Up to :data:`TOP_COMPANIES_COUNT` company names, most frequent first,
        alphabetical as tie-break (deterministic order, AGENTS 3.3.10).
    """
    if not posting_ids:
        return []
    rows = db.execute(
        select(JobPosting.company, func.count())
        .where(JobPosting.id.in_(posting_ids))
        .group_by(JobPosting.company)
        .order_by(func.count().desc(), JobPosting.company.asc())
        .limit(TOP_COMPANIES_COUNT)
    )
    return [company for company, _ in rows.all()]


def _corpus_spans_multiple_days(first_seen_dates: list[object]) -> bool:
    """Return True when postings were first seen on ≥ 2 distinct days.

    Args:
        first_seen_dates: ``date`` or ``datetime`` values of postings' first_seen_at.

    A single-day corpus has no meaningful "new this week": everything arrived
    the same day the tracking started, so the count would just equal the total
    (plan 1.4 requires null in that case).
    """

    def _to_date(value: object) -> object:
        return value.date() if isinstance(value, datetime) else value

    distinct = {_to_date(value) for value in first_seen_dates}
    return len(distinct) >= MIN_DAYS_FOR_NEW_POSTINGS


def get_pulse_cards(db: Session, region: str) -> list[dict[str, object]]:
    """Aggregate one PulseCard payload per scored subfield (ordered by sort_order).

    Args:
        db: request session.
        region: ``global`` or ``india`` — counts are computed per region.

    Returns:
        A list of dicts shaped like ``schemas.pulse.PulseCard``:
        ``subfield_id, name, description, active_postings, extra_postings,
        internship_postings, new_this_week (int | None), tracking_since
        (ISO date str | None), top_companies, low_data``.
        Empty list only if the taxonomy is missing (cannot happen post-seed).
    """
    subfields = list(
        db.scalars(
            select(Subfield).where(Subfield.is_scored.is_(True)).order_by(Subfield.sort_order)
        )
    )
    now = utc_now()
    week_ago = now - timedelta(days=NEW_THIS_WEEK_DAYS)

    cards: list[dict[str, object]] = []
    for subfield in subfields:
        core_ids = _active_core_posting_ids(db, subfield.id, region)
        extra_ids = _extra_posting_ids(db, subfield.id, region)
        all_ids = core_ids | extra_ids

        internship_count = 0
        new_this_week: int | None = None
        tracking_since: str | None = None

        if all_ids:
            postings = list(db.scalars(select(JobPosting).where(JobPosting.id.in_(all_ids))))
            internship_count = sum(1 for p in postings if p.is_internship)
            # tracking_since = earliest first_seen across the subfield's corpus.
            first_seen_dates = [p.first_seen_at.date() for p in postings]
            tracking_since = min(first_seen_dates).isoformat()
            # new_this_week is deliberately null for a single-day corpus: with
            # one ingestion day the number would be the total, which reads as
            # growth when it is just the initial sample (plan 1.4).
            if _corpus_spans_multiple_days(first_seen_dates):
                new_this_week = sum(1 for p in postings if p.first_seen_at >= week_ago)

        cards.append(
            {
                "subfield_id": subfield.id,
                "name": subfield.name,
                "description": subfield.description,
                "active_postings": len(core_ids),
                "extra_postings": len(extra_ids),
                "internship_postings": internship_count,
                "new_this_week": new_this_week,
                "tracking_since": tracking_since,
                "top_companies": _top_companies(db, all_ids),
                "low_data": len(core_ids) < LOW_DATA_THRESHOLD,
            }
        )
    return cards


def list_postings(
    db: Session,
    subfield_id: str,
    *,
    region: str = "global",
    internship: bool | None = None,
    limit: int = DEFAULT_POSTINGS_LIMIT,
    offset: int = 0,
) -> tuple[list[JobPosting], int]:
    """List postings linked to a subfield (both tiers), newest first.

    Args:
        db: request session.
        subfield_id: the subfield whose postings to show.
        region: ``global`` or ``india``.
        internship: True → only internships, False → only non-internships,
            None → everything.
        limit: page size (1..100; values outside are clamped).
        offset: pagination offset (>= 0).

    Returns:
        ``(postings, total)`` where total is the count matching the filters
        (before limit/offset) so the UI can paginate.

    Raises:
        NotFoundError: unknown subfield id (router maps to 404).
    """
    from app.core.errors import NotFoundError

    subfield = db.get(Subfield, subfield_id)
    if subfield is None:
        raise NotFoundError(f"unknown subfield: {subfield_id}")

    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    # Both core and extended postings are listed; distinct join rows cannot
    # occur because the link table is unique on (posting, subfield, region).
    statement = (
        select(JobPosting)
        .join(JobPostingSubfield, JobPostingSubfield.posting_id == JobPosting.id)
        .where(
            JobPostingSubfield.subfield_id == subfield_id,
            JobPostingSubfield.region == region,
            JobPosting.is_active.is_(True),
        )
        .distinct()
        .order_by(JobPosting.last_seen_at.desc(), JobPosting.id.asc())
    )
    if internship is not None:
        statement = statement.where(JobPosting.is_internship.is_(bool(internship)))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    postings = list(db.scalars(statement.limit(limit).offset(offset)))
    return postings, int(total)
