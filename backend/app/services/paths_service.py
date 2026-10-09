"""Paths service: rank the six career paths with live evidence (plan 4.3).

Sits between the paths router and the models/pulse layers (AGENTS 3.3.1).
The math is delegated to the pure functions in :mod:`scoring_service`; this
module only assembles inputs (interests, readiness, core demand counts, Pulse
evidence) and shapes the :class:`app.schemas.paths.PathResult` rows.

Rules encoded here:
- Requires a diagnostic assessment; otherwise :class:`AssessmentRequiredError`
  (409 ``assessment_required``, plan 4.3).
- Demand uses CORE-tier active postings only (plan 4.6 fairness note), and the
  saturation flag comes from the latest bootstrap's ``page_cap_subfields``
  recorded by :mod:`ingestion_service` (plan 4.2).
- ``GET`` attaches only CACHED explanations (never calls Gemini); the POST
  endpoint triggers :func:`explanation_service.ensure_explanations`.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AssessmentRequiredError, NotFoundError
from app.integrations.gemini.client import StructuredLLM
from app.models import Assessment, CareerPath, PathExplanation, Profile, RefreshRun, Subfield
from app.schemas.paths import (
    PathEvidence,
    PathExplanationOut,
    PathResult,
    PathsOut,
    ScoreBreakdown,
)
from app.services import explanation_service, pulse_service, quiz_service
from app.services.scoring_service import (
    TOP_3,
    WEIGHTS_PERCENT,
    PathCandidate,
    demand_n,
    interest_n,
    rank_paths,
    readiness_n,
    saturation_note,
)

logger = logging.getLogger(__name__)

#: How many top skills travel in the evidence block (the UI shows five).
TOP_SKILLS_IN_EVIDENCE = 5

#: How many sample postings the evidence panel shows per path (plan 4.3).
SAMPLE_POSTINGS = 3

#: Neutral interest used only if a profile somehow lacks a subfield's slider
#: (submit_assessment validates presence, so this is pure defense).
DEFAULT_INTEREST_SLIDER = 3

#: How many latest bootstrap runs to inspect when looking for page-cap data.
LATEST_BOOTSTRAP_SCAN_LIMIT = 50


def _latest_assessment(db: Session, profile_id: str) -> Assessment:
    """Return the profile's newest assessment or raise the 409 guard.

    Args:
        db: request session.
        profile_id: UUID path parameter (profile already resolved).

    Returns:
        The newest :class:`Assessment`.

    Raises:
        AssessmentRequiredError: the profile exists but never submitted the
            diagnostic — 409 ``assessment_required`` (plan 4.3).
    """
    assessment = db.scalar(
        select(Assessment)
        .where(Assessment.profile_id == profile_id)
        .order_by(Assessment.taken_at.desc(), Assessment.id.desc())
        .limit(1)
    )
    if assessment is None:
        raise AssessmentRequiredError(
            "This profile has no diagnostic result yet — complete the orientation diagnostic first."
        )
    return assessment


def _page_cap_subfields(db: Session, region: str) -> set[str]:
    """Return subfields whose CORE query hit the page cap in the latest bootstrap.

    Args:
        db: request session.
        region: the region whose bootstrap run to read.

    Returns:
        The ``page_cap_subfields`` recorded in the newest matching
        ``refresh_runs`` row (empty set when none exists — e.g. before the
        first bootstrap, or for runs recorded before this key existed).
    """
    runs = db.scalars(
        select(RefreshRun)
        .where(RefreshRun.kind == "jobs", RefreshRun.mode == "bootstrap")
        .order_by(RefreshRun.started_at.desc(), RefreshRun.id.desc())
        .limit(LATEST_BOOTSTRAP_SCAN_LIMIT)
    )
    for run in runs:
        details = run.details or {}
        if details.get("region") == region:
            return {str(value) for value in details.get("page_cap_subfields", [])}
    return set()


def _scored_subfields(db: Session) -> list[Subfield]:
    """Return the six scored subfields in taxonomy order (stable input order)."""
    stmt = select(Subfield).where(Subfield.is_scored.is_(True)).order_by(Subfield.sort_order)
    return list(db.scalars(stmt))


def _paths_by_subfield(db: Session) -> dict[str, CareerPath]:
    """Return career paths keyed by subfield (seed enforces 1:1, plan 4.9)."""
    paths = db.scalars(select(CareerPath))
    return {path.subfield_id: path for path in paths}


def build_ranked_paths(
    db: Session, profile_id: str, region: str
) -> tuple[Assessment, list[PathResult], str | None]:
    """Score and rank all six paths for a profile's latest assessment (plan 4.3).

    Args:
        db: request session.
        profile_id: UUID path parameter.
        region: ``global`` or ``india`` — demand/evidence region.

    Returns:
        ``(assessment, results, saturation_note)`` where results are ranked
        best-first with ``explanation=None`` (the caller fills the cache), and
        saturation_note is non-None only when >= 4 of 6 subfields hit the
        page cap (plan 4.5).

    Raises:
        NotFoundError: unknown profile (404).
        AssessmentRequiredError: no diagnostic submitted yet (409).
    """
    profile: Profile = quiz_service.get_profile(db, profile_id)  # 404 if unknown
    assessment = _latest_assessment(db, profile_id)

    subfields = _scored_subfields(db)
    paths = _paths_by_subfield(db)

    # One detail query per subfield: counts, top skills, PhD share, samples.
    details = {
        subfield.id: pulse_service.get_subfield_detail(db, subfield.id, region)
        for subfield in subfields
        if subfield.id in paths
    }
    max_active = max((int(detail["active_postings"]) for detail in details.values()), default=0)
    capped = _page_cap_subfields(db, region)

    candidates: list[PathCandidate] = []
    for subfield_id, detail in details.items():
        path = paths[subfield_id]
        candidates.append(
            PathCandidate(
                path_id=path.id,
                subfield_id=subfield_id,
                # Interests are validated for presence at submit time; the
                # default only guards hand-crafted profiles (see constants).
                interest=interest_n(
                    int(profile.interests.get(subfield_id, DEFAULT_INTEREST_SLIDER))
                ),
                readiness=readiness_n(float(assessment.scores.get(subfield_id, 0.0))),
                demand=demand_n(int(detail["active_postings"]), max_active),
                active_postings=int(detail["active_postings"]),
            )
        )
    ranked = rank_paths(candidates)

    results: list[PathResult] = []
    for item in ranked:
        path = paths[item.subfield_id]
        detail = details[item.subfield_id]
        results.append(
            PathResult(
                path_id=item.path_id,
                title=path.title,
                subfield_id=item.subfield_id,
                rank=item.rank,
                score=item.score,
                breakdown=ScoreBreakdown(
                    interest=item.interest,
                    demand=item.demand,
                    readiness=item.readiness,
                    weights=dict(WEIGHTS_PERCENT),
                ),
                is_top3=item.rank <= TOP_3,
                low_data=item.low_data,
                saturated=item.subfield_id in capped,
                evidence=_build_evidence(detail),
                explanation=None,
            )
        )
    note = saturation_note(capped, len(results))
    return assessment, results, note


def _build_evidence(detail: dict[str, object]) -> PathEvidence:
    """Shape one subfield's Pulse detail into the evidence block (plan 4.3).

    Args:
        detail: output of :func:`pulse_service.get_subfield_detail`.

    Returns:
        PathEvidence with top skills (first 5), PhD share (raw + percent
        rendering) and the three newest sample postings.
    """
    phd_share = detail.get("phd_share")
    return PathEvidence(
        active_postings=int(detail["active_postings"]),
        internship_postings=int(detail["internship_postings"]),
        top_skills=[
            {
                "skill_id": str(skill["skill_id"]),
                "name": str(skill["name"]),
                "share": float(skill["share"]),
                "share_pct": round(float(skill["share"]) * 100, 1),
            }
            for skill in list(detail["top_skills"])[:TOP_SKILLS_IN_EVIDENCE]
        ],
        phd_share=float(phd_share) if phd_share is not None else None,
        phd_share_pct=round(float(phd_share) * 100, 1) if phd_share is not None else None,
        sample_postings=list(detail["postings"])[:SAMPLE_POSTINGS],
    )


def get_ranked_paths(db: Session, profile_id: str, region: str = "global") -> PathsOut:
    """``GET /profiles/{id}/paths``: ranked paths with evidence (plan 4.3).

    Attaches only CACHED explanations — this endpoint never calls Gemini, so
    it works with no key and no quota (design decision 4).

    Args:
        db: request session.
        profile_id: UUID path parameter.
        region: demand/evidence region (default global).

    Returns:
        PathsOut with all six ranked paths and the saturation note (if any).

    Raises:
        NotFoundError: unknown profile (404).
        AssessmentRequiredError: no diagnostic submitted yet (409).
    """
    assessment, results, note = build_ranked_paths(db, profile_id, region)
    cached = explanation_service.cached_explanations(db, profile_id, assessment.id, results)
    filled = [
        result.model_copy(update={"explanation": cached.get(result.path_id)}) for result in results
    ]
    return PathsOut(
        profile_id=profile_id,
        assessment_id=assessment.id,
        region=region,
        saturation_note=note,
        paths=filled,
    )


def get_ranked_paths_with_explanations(
    db: Session,
    profile_id: str,
    region: str = "global",
    llm: StructuredLLM | None = None,
) -> PathsOut:
    """``POST /profiles/{id}/paths/explanations`` (plan 4.4/4.5 batched endpoint).

    Ensures explanations for ALL six paths with ONE batched Gemini call (design
    decision 1), persisting each under its evidence hash, and returns all six
    paths with their explanations attached. Never fails because of Gemini:
    templates are returned with ``generated_by="template"`` instead.

    Args:
        db: request session.
        profile_id: UUID path parameter.
        region: demand/evidence region (default global).
        llm: Gemini client or None when unconfigured.

    Returns:
        PathsOut with all six ranked paths and populated explanation blocks.

    Raises:
        NotFoundError: unknown profile (404).
        AssessmentRequiredError: no diagnostic submitted yet (409).
    """
    assessment, results, note = build_ranked_paths(db, profile_id, region)
    explanations = explanation_service.ensure_explanations(
        db, profile_id, assessment.id, results, llm
    )
    filled = [
        result.model_copy(update={"explanation": explanations.get(result.path_id)})
        for result in results
    ]
    return PathsOut(
        profile_id=profile_id,
        assessment_id=assessment.id,
        region=region,
        saturation_note=note,
        paths=filled,
    )


def request_explanation(
    db: Session,
    profile_id: str,
    path_id: str,
    region: str = "global",
    llm: StructuredLLM | None = None,
) -> PathExplanationOut:
    """``POST /profiles/{id}/paths/{path_id}/explanation`` (plan 4.4/4.5 per-path).

    Ensures explanations for ALL paths with one batched Gemini call (design
    decision 1), persisting each under its evidence hash, then returns the
    requested one. Never fails because of Gemini — templates are returned
    with ``generated_by="template"`` instead.

    Args:
        db: request session.
        profile_id: UUID path parameter.
        path_id: which path's explanation the client asked for.
        region: must match the region used for GET (evidence differs per region).
        llm: Gemini client or None when unconfigured.

    Returns:
        The requested explanation (freshly generated or cached).

    Raises:
        NotFoundError: unknown profile (404) or unknown path id (409 path —
            unknown paths are a plain 404).
        AssessmentRequiredError: no diagnostic submitted yet (409).
    """
    assessment, results, _note = build_ranked_paths(db, profile_id, region)
    known = {result.path_id for result in results}
    if path_id not in known:
        raise NotFoundError(f"unknown career path '{path_id}'")
    explanations = explanation_service.ensure_explanations(
        db, profile_id, assessment.id, results, llm
    )
    return explanations[path_id]


def cached_explanation_count(db: Session, profile_id: str, assessment_id: int) -> int:
    """Return how many explanation rows exist for this cache scope (tests/admin).

    Args:
        db: request session.
        profile_id: owning profile.
        assessment_id: assessment to count rows for.

    Returns:
        Row count (all hashes, including superseded-but-not-yet-replaced ones).
    """
    rows = db.scalars(
        select(PathExplanation).where(
            PathExplanation.profile_id == profile_id,
            PathExplanation.assessment_id == assessment_id,
        )
    )
    return len(list(rows))
