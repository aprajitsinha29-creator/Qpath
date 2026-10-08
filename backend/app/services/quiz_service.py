"""Quiz/diagnostic service: build the quiz, manage anonymous profiles, score submissions.

Sits between the quiz/profile routers and the models layer (AGENTS.md 3.3.1).
The <3-questions-per-scored-subfield guard lives here so a lopsided question
bank can never silently bias readiness scores (plan 3.1).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import InvalidAssessmentError, NotFoundError, QuizContentError
from app.models import Assessment, Profile, Question, Subfield
from app.schemas.quiz import AssessmentIn, AssessmentOut, PerQuestionFeedback, ProfileOut
from app.services import scoring_service
from app.services.scoring_service import QuestionMeta

logger = logging.getLogger(__name__)

#: Each scored subfield must have at least this many servable questions (plan 3.1).
MIN_QUESTIONS_PER_SUBFIELD = 3


def _servable_questions(db: Session) -> list[Question]:
    """Return the questions that may be served under the current settings.

    Unverified rows are served only while ALLOW_UNVERIFIED_QUESTIONS is true
    (dev mode until the owner finishes verification, manual task M-08).
    """
    allow_unverified = get_settings().allow_unverified_questions
    stmt = select(Question).order_by(Question.sort_order, Question.id)
    questions = list(db.scalars(stmt))
    return [q for q in questions if q.verified or allow_unverified]


def build_quiz(db: Session) -> list[Question]:
    """Return the servable questions in serve order, enforcing the >=3 guard.

    Args:
        db: request session.

    Returns:
        Questions ordered by ``sort_order`` (then id for stability), filtered
        by the verified/unverified policy.

    Raises:
        QuizContentError: when any scored subfield has fewer than
            :data:`MIN_QUESTIONS_PER_SUBFIELD` servable questions.
    """
    questions = _servable_questions(db)
    scored_ids = set(db.scalars(select(Subfield.id).where(Subfield.is_scored.is_(True))))

    per_subfield: dict[str, int] = {subfield_id: 0 for subfield_id in scored_ids}
    for question in questions:
        if question.subfield_id in per_subfield:
            per_subfield[question.subfield_id] += 1
    short = sorted(s for s, n in per_subfield.items() if n < MIN_QUESTIONS_PER_SUBFIELD)
    if short:
        # Named subfields make the message actionable (owner: add/verify content).
        raise QuizContentError(
            "Quiz cannot be served: scored subfields with fewer than "
            f"{MIN_QUESTIONS_PER_SUBFIELD} servable questions: {', '.join(short)}. "
            "Add verified questions to app/data/quiz_questions.json (or set "
            "ALLOW_UNVERIFIED_QUESTIONS=true while developing)."
        )
    return questions


def create_profile(db: Session, profile_id: str | None = None) -> ProfileOut:
    """Create (or idempotently return) an anonymous profile.

    Args:
        db: request session.
        profile_id: optional client-generated UUID; when provided and already
            known, the existing profile is returned so retries are safe
            (AGENTS.md 3.3.9).

    Returns:
        The profile projection (UUID + timestamps only, no personal data).
    """
    if profile_id is not None:
        existing = db.get(Profile, profile_id)
        if existing is not None:
            return ProfileOut.model_validate(existing)
    profile = Profile(id=profile_id or str(uuid.uuid4()))
    db.add(profile)
    db.commit()
    logger.info("profile created: %s", profile.id)
    return ProfileOut.model_validate(profile)


def get_profile(db: Session, profile_id: str) -> Profile:
    """Fetch one profile or raise NotFoundError.

    Args:
        db: request session.
        profile_id: UUID path parameter.

    Returns:
        The ORM Profile (service-internal use; routers project to schemas).

    Raises:
        NotFoundError: when no profile with that UUID exists (404).
    """
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise NotFoundError(f"profile '{profile_id}' does not exist")
    return profile


def submit_assessment(db: Session, profile_id: str, payload: AssessmentIn) -> AssessmentOut:
    """Validate a diagnostic submission, score it and persist the result.

    Also stores the interests on the profile (latest wins; history is kept in
    ``assessments``).

    Args:
        db: request session.
        profile_id: UUID path parameter.
        payload: interests ({subfield_id: 1-5}) plus answers.

    Returns:
        The scored result: readiness per subfield, per-question feedback and
        weak concepts.

    Raises:
        NotFoundError: unknown profile (404).
        InvalidAssessmentError: unknown question id or duplicate answer (422),
            unknown interest subfield, missing interest for a scored subfield,
            or a selected_index outside 0-3 for the question's options.
        QuizContentError: when the servable bank fails the >=3-per-subfield
            guard (scoring a quiz that was never servable would be nonsense).
    """
    profile = get_profile(db, profile_id)
    questions = build_quiz(db)
    scored_ids = set(db.scalars(select(Subfield.id).where(Subfield.is_scored.is_(True))))

    unknown_interests = set(payload.interests) - scored_ids
    if unknown_interests:
        raise InvalidAssessmentError(
            f"interests reference unknown subfields: {', '.join(sorted(unknown_interests))}"
        )
    missing_interests = scored_ids - set(payload.interests)
    if missing_interests:
        raise InvalidAssessmentError(
            f"interests are missing scored subfields: {', '.join(sorted(missing_interests))}"
        )

    known_ids = {q.id for q in questions}
    by_id = {q.id: q for q in questions}
    try:
        selections = scoring_service.normalize_selections(
            [(a.question_id, a.selected_index) for a in payload.answers], known_ids
        )
    except ValueError as exc:
        raise InvalidAssessmentError(str(exc)) from exc
    # Semantic bounds: an index valid for one question may not exist for a
    # 4-option question (0-3 is guaranteed by the schema, but a question could
    # later serve fewer options — check against the actual list).
    for question_id, selected in selections.items():
        if selected is not None and not 0 <= selected < len(by_id[question_id].options):
            raise InvalidAssessmentError(
                f"selected_index {selected} out of range for question '{question_id}'"
            )

    meta = {
        q.id: QuestionMeta(
            subfield_id=q.subfield_id,
            difficulty=q.difficulty,
            correct_index=q.correct_index,
            concept_id=q.concept_id,
        )
        for q in questions
    }
    scores = scoring_service.readiness_scores(meta, selections)
    weak = scoring_service.weak_concepts(meta, selections)
    feedback = scoring_service.per_question_feedback(
        meta, {q.id: q.explanation for q in questions}, selections
    )

    profile.interests = dict(payload.interests)
    assessment = Assessment(
        profile_id=profile.id,
        answers=[
            {"question_id": a.question_id, "selected_index": a.selected_index}
            for a in payload.answers
        ],
        scores={k: round(v, 2) for k, v in scores.items()},
    )
    db.add(assessment)
    db.commit()
    logger.info("assessment scored: profile=%s assessment=%s", profile.id, assessment.id)

    return AssessmentOut(
        assessment_id=assessment.id,
        profile_id=profile.id,
        taken_at=assessment.taken_at,
        scores=assessment.scores,
        interests=profile.interests,
        per_question=[PerQuestionFeedback.model_validate(f) for f in feedback],
        weak_concepts=weak,
    )


def latest_assessment(db: Session, profile_id: str) -> AssessmentOut:
    """Return the profile's most recent assessment with feedback rebuilt.

    Feedback (correct/explanation/concept) is derived from the stored raw
    answers rather than persisted, so fixing a question's explanation or key
    (owner task M-08) immediately corrects the history view.

    Args:
        db: request session.
        profile_id: UUID path parameter.

    Returns:
        The latest AssessmentOut.

    Raises:
        NotFoundError: unknown profile, or the profile has no assessments yet.
    """
    profile = get_profile(db, profile_id)
    assessment = db.scalar(
        select(Assessment)
        .where(Assessment.profile_id == profile.id)
        .order_by(Assessment.taken_at.desc(), Assessment.id.desc())
        .limit(1)
    )
    if assessment is None:
        raise NotFoundError(f"profile '{profile_id}' has no assessments yet")

    questions = list(db.scalars(select(Question).order_by(Question.sort_order, Question.id)))
    meta = {
        q.id: QuestionMeta(
            subfield_id=q.subfield_id,
            difficulty=q.difficulty,
            correct_index=q.correct_index,
            concept_id=q.concept_id,
        )
        for q in questions
    }
    selections = {
        str(a.get("question_id")): a.get("selected_index")  # type: ignore[arg-type]
        for a in assessment.answers
        if isinstance(a, dict) and a.get("question_id") is not None
    }
    weak = scoring_service.weak_concepts(meta, selections)
    feedback = scoring_service.per_question_feedback(
        meta, {q.id: q.explanation for q in questions}, selections
    )
    return AssessmentOut(
        assessment_id=assessment.id,
        profile_id=profile.id,
        taken_at=assessment.taken_at,
        scores=assessment.scores,
        interests=profile.interests,
        per_question=[PerQuestionFeedback.model_validate(f) for f in feedback],
        weak_concepts=weak,
    )
