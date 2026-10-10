"""Profile and assessment endpoints (plan 3.4).

Thin routers per AGENTS.md 3.3.1: parse input, call the service, return the
schema. Scoring happens inside the service — never here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.quiz import AssessmentIn, AssessmentOut, ProfileCreateIn, ProfileOut
from app.schemas.skills import DeclaredSkillsIn
from app.services import quiz_service, skills_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut, summary="Create an anonymous profile")
def create_profile(
    body: ProfileCreateIn | None = None, db: Session = Depends(get_db)
) -> ProfileOut:
    """Create (or idempotently return) an anonymous profile.

    Args:
        body: optional; may carry a client-generated UUID so the browser's
            localStorage identity matches the server row on retries.
        db: request session.

    Returns:
        ProfileOut with the profile UUID (no personal data, AGENTS.md 3.10.4).
    """
    profile_id = body.profile_id if body is not None else None
    return quiz_service.create_profile(db, profile_id)


@router.put("/{profile_id}/skills", response_model=ProfileOut, summary="Replace declared skills")
def replace_declared_skills(
    profile_id: str, payload: DeclaredSkillsIn, db: Session = Depends(get_db)
) -> ProfileOut:
    """Replace the profile's whole declared-skills list (carry-over from Phase 4).

    Atomic and vocabulary-validated: every id must exist in the seeded skills
    table, else 422 ``invalid_skills`` and nothing is written. Duplicates are
    removed keeping first-seen order; an empty list clears the list. Only
    ``declared_skills`` changes — interests, assessments, ``last_seen_at``,
    ``chosen_path_id`` and ``completed_concepts`` are untouched.

    Args:
        profile_id: UUID path parameter.
        payload: ``{"skill_ids": [str, ...]}`` — the full replacement list.
        db: request session.

    Returns:
        ProfileOut with the updated ``declared_skills``.

    Raises:
        NotFoundError: unknown profile (404).
        InvalidSkillsError: unknown skill ids (422), nothing written.
    """
    profile = skills_service.replace_declared_skills(db, profile_id, payload.skill_ids)
    return ProfileOut.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileOut, summary="Fetch a profile")
def get_profile(profile_id: str, db: Session = Depends(get_db)) -> ProfileOut:
    """Return one anonymous profile.

    Args:
        profile_id: UUID path parameter.
        db: request session.

    Returns:
        ProfileOut.

    Raises:
        NotFoundError: unknown profile (404).
    """
    return ProfileOut.model_validate(quiz_service.get_profile(db, profile_id))


@router.post(
    "/{profile_id}/assessment", response_model=AssessmentOut, summary="Submit the diagnostic"
)
def submit_assessment(
    profile_id: str, payload: AssessmentIn, db: Session = Depends(get_db)
) -> AssessmentOut:
    """Score a diagnostic submission and store it as the profile's latest.

    Args:
        profile_id: UUID path parameter.
        payload: interests (six sliders) plus answers ("Not sure" = null).
        db: request session.

    Returns:
        AssessmentOut: readiness per subfield, per-question feedback, weak
        concepts. Explanations appear only HERE, never in GET /quiz.

    Raises:
        NotFoundError: unknown profile (404).
        InvalidAssessmentError: unknown/duplicate answers or bad interests (422).
        QuizContentError: the servable bank fails the >=3-per-subfield guard (503).
    """
    return quiz_service.submit_assessment(db, profile_id, payload)


@router.get(
    "/{profile_id}/assessments/latest",
    response_model=AssessmentOut,
    summary="Latest assessment for a profile",
)
def latest_assessment(profile_id: str, db: Session = Depends(get_db)) -> AssessmentOut:
    """Return the profile's most recent scored assessment.

    Args:
        profile_id: UUID path parameter.
        db: request session.

    Returns:
        AssessmentOut.

    Raises:
        NotFoundError: unknown profile, or no assessments yet (404).
    """
    return quiz_service.latest_assessment(db, profile_id)
