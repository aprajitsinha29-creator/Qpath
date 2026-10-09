"""Pulse service: aggregates stored postings into the six Market Pulse cards.

Phase 1 step 1.4 (cards, postings) extended in Phase 2 step 2.6 with the
intelligence layer: top skills (share of the subfield's active extracted
postings), seniority/PhD mix, extraction coverage and research themes.
Pure read-side logic over the tables the ingestion/research services write:
per subfield it counts core-sourced active postings (headline demand),
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
- Skill shares, mixes and coverage are computed over **all linked active
  postings for the requested region** (both tiers): skills describe the
  postings, not demand, and excluding extended-only postings would hide real
  signal in thin subfields (the demand-fairness rule applies to counts only).
- Themes come from the newest ``research_themes`` batch (qualitative only —
  no counts or trends are computed from Scholar, AGENTS 3.4.9).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import NotFoundError
from app.models import (
    JobPosting,
    JobPostingSkill,
    JobPostingSubfield,
    PaperSnapshot,
    Skill,
    Subfield,
)

# The low-data constant lives with the other scoring constants (plan 4.2 —
# scoring_service is the single source for LOW_DATA_THRESHOLD).
from app.services.scoring_service import LOW_DATA_THRESHOLD

logger = logging.getLogger(__name__)

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

#: How many top skills to include in the pulse card (plan 2.6).
TOP_SKILLS_CARD_LIMIT = 5

#: How many themes to include in the pulse card (plan 2.6).
TOP_THEMES_CARD_LIMIT = 3


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
                "top_skills": _top_skills(db, all_ids, limit=5),
                "themes": _themes_with_papers(db, subfield.id)[:3],
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


def _all_linked_posting_ids(db: Session, subfield_id: str, region: str) -> set[int]:
    """Return ids of ALL active postings linked to the subfield/region (both tiers).

    Skills, seniority mix, extraction coverage and themes describe the postings
    themselves, not demand; excluding extended-only postings would hide real
    signal in thin subfields (ARCHITECTURE.md decision log).
    """
    rows = db.execute(
        select(JobPostingSubfield.posting_id)
        .join(JobPosting, JobPosting.id == JobPostingSubfield.posting_id)
        .where(
            JobPostingSubfield.subfield_id == subfield_id,
            JobPostingSubfield.region == region,
            JobPosting.is_active.is_(True),
        )
    )
    return {row[0] for row in rows.all()}


def _top_skills(db: Session, posting_ids: set[int], limit: int) -> list[dict[str, object]]:
    """Return top skills by mention share among extracted postings.

    Args:
        db: request session.
        posting_ids: active postings linked to the subfield/region (both tiers).
        limit: maximum number of skills to return.

    Returns:
        List of ``{skill_id, name, share}`` sorted by share desc, name asc tie-break.
        Share = mentions / count of ACTIVE EXTRACTED postings for that subfield+region
        (denominator = postings with ``extraction_status='done'``, NOT all postings).
        Empty list when nothing extracted.
    """
    if not posting_ids:
        return []

    # Ensure we see the latest committed state
    db.expire_all()

    # Denominator: active postings with extraction_status = 'done'
    extracted_count = (
        db.scalar(
            select(func.count())
            .select_from(JobPosting)
            .where(
                JobPosting.id.in_(posting_ids),
                JobPosting.extraction_status == "done",
            )
        )
        or 0
    )

    if extracted_count == 0:
        return []

    # Numerator: skill mentions among extracted postings
    rows = db.execute(
        select(JobPostingSkill.skill_id, func.count(JobPostingSkill.posting_id.distinct()))
        .join(JobPosting, JobPosting.id == JobPostingSkill.posting_id)
        .where(
            JobPosting.id.in_(posting_ids),
            JobPosting.extraction_status == "done",
        )
        .group_by(JobPostingSkill.skill_id)
        .order_by(
            func.count(JobPostingSkill.posting_id.distinct()).desc(),
            JobPostingSkill.skill_id.asc(),
        )
        .limit(limit)
    )

    skill_rows = rows.all()
    skill_ids = [row[0] for row in skill_rows]
    if not skill_ids:
        return []

    # Fetch skill names for the result
    skills = {s.id: s.name for s in db.scalars(select(Skill).where(Skill.id.in_(skill_ids)))}

    return [
        {"skill_id": sid, "name": skills.get(sid, sid), "share": count / extracted_count}
        for sid, count in skill_rows
    ]


def _seniority_mix(db: Session, posting_ids: set[int]) -> dict[str, object]:
    """Return seniority counts and PhD share among the given postings.

    Args:
        db: request session.
        posting_ids: active postings linked to the subfield/region (both tiers).

    Returns:
        Dict with:
        - per-seniority counts (including "unknown" bucket for NULL/unknown)
        - phd_share: share of postings with requires_phd=True among postings
          where requires_phd IS NOT NULL (None when no posting states it).
    """
    if not posting_ids:
        return {"seniority": {}, "phd_share": None}

    postings = list(db.scalars(select(JobPosting).where(JobPosting.id.in_(posting_ids))))

    # Seniority counts: include "unknown" bucket for NULL/unknown
    seniority_counts: dict[str, int] = {}
    for p in postings:
        key = p.seniority if p.seniority else "unknown"
        seniority_counts[key] = seniority_counts.get(key, 0) + 1

    # PhD share: only among postings where requires_phd is NOT NULL
    phd_known = [p for p in postings if p.requires_phd is not None]
    phd_share: float | None = None
    if phd_known:
        phd_true = sum(1 for p in phd_known if p.requires_phd)
        phd_share = phd_true / len(phd_known)

    return {"seniority": seniority_counts, "phd_share": phd_share}


def _extraction_coverage(db: Session, posting_ids: set[int]) -> float:
    """Return extraction coverage: done / total over active linked postings.

    Args:
        db: request session.
        posting_ids: active postings linked to the subfield/region (both tiers).

    Returns:
        Coverage as float in [0, 1]; 0.0 when no postings.
    """
    if not posting_ids:
        return 0.0

    total = len(posting_ids)
    done = (
        db.scalar(
            select(func.count())
            .select_from(JobPosting)
            .where(
                JobPosting.id.in_(posting_ids),
                JobPosting.extraction_status == "done",
            )
        )
        or 0
    )
    return done / total


def _themes_with_papers(db: Session, subfield_id: str) -> list[dict[str, object]]:
    """Return themes from the newest research batch with resolved paper refs.

    Args:
        db: request session.
        subfield_id: subfield to look up.

    Returns:
        List of ``{label, summary, papers: [{id, title, link}]}``.
        Empty list when no themes exist. Missing paper ids are skipped defensively.
    """
    from app.services.research_service import latest_themes_by_subfield

    themes = latest_themes_by_subfield(db, subfield_id)
    if not themes:
        return []

    # Collect all paper ids needed
    all_paper_ids: set[int] = set()
    for theme in themes:
        all_paper_ids.update(theme.get("paper_ids", []))

    if not all_paper_ids:
        return [{"label": t["label"], "summary": t["summary"], "papers": []} for t in themes]

    # Fetch papers in one query
    papers = {
        p.id: {"id": p.id, "title": p.title, "link": p.link}
        for p in db.scalars(select(PaperSnapshot).where(PaperSnapshot.id.in_(all_paper_ids)))
    }

    # Resolve papers per theme, preserving order, skipping missing ids
    result: list[dict[str, object]] = []
    for theme in themes:
        paper_refs = [papers[pid] for pid in theme.get("paper_ids", []) if pid in papers]
        result.append(
            {
                "label": theme["label"],
                "summary": theme["summary"],
                "papers": paper_refs,
            }
        )
    return result


def get_subfield_detail(db: Session, subfield_id: str, region: str) -> dict[str, object]:
    """Return the full detail payload for one subfield.

    Args:
        db: request session.
        subfield_id: subfield to detail.
        region: ``global`` or ``india``.

    Returns:
        Dict shaped like ``schemas.pulse.SubfieldDetail``: the card fields
        PLUS ``top_skills`` (full list), ``seniority_mix``, ``phd_share``,
        ``extraction_coverage``, ``themes`` (with papers incl. title+link),
        and postings list (first 20, newest first).

    Raises:
        NotFoundError: unknown subfield id.
    """
    subfield = db.get(Subfield, subfield_id)
    if subfield is None:
        raise NotFoundError(f"unknown subfield: {subfield_id}")

    core_ids = _active_core_posting_ids(db, subfield_id, region)
    extra_ids = _extra_posting_ids(db, subfield_id, region)
    all_ids = core_ids | extra_ids

    # Base card fields
    internship_count = 0
    new_this_week: int | None = None
    tracking_since: str | None = None

    if all_ids:
        postings = list(db.scalars(select(JobPosting).where(JobPosting.id.in_(all_ids))))
        internship_count = sum(1 for p in postings if p.is_internship)
        first_seen_dates = [p.first_seen_at.date() for p in postings]
        tracking_since = min(first_seen_dates).isoformat()
        now = utc_now()
        week_ago = now - timedelta(days=NEW_THIS_WEEK_DAYS)
        if _corpus_spans_multiple_days(first_seen_dates):
            new_this_week = sum(1 for p in postings if p.first_seen_at >= week_ago)

    # Intelligence fields (computed over all linked active postings, both tiers)
    top_skills = _top_skills(db, all_ids, limit=50)  # full list for detail
    seniority_mix = _seniority_mix(db, all_ids)
    extraction_coverage = _extraction_coverage(db, all_ids)
    themes = _themes_with_papers(db, subfield_id)

    # Postings list (newest first, first 20)
    postings_list, _ = list_postings(db, subfield_id, region=region, limit=20, offset=0)
    postings_out = [to_posting_out(p) for p in postings_list]

    return {
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
        "top_skills": top_skills,
        "seniority_mix": seniority_mix["seniority"],
        "phd_share": seniority_mix["phd_share"],
        "extraction_coverage": extraction_coverage,
        "themes": themes,
        "postings": postings_out,
    }
