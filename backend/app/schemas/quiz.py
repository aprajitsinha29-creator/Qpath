"""Schemas for the quiz/profile endpoints (plan 3.2).

``QuizQuestionOut`` deliberately has NO ``correct_index`` and NO ``explanation``:
GET /quiz must never reveal answers — scoring happens server-side
(AGENTS.md 3.10.3). ORM models never leave the service layer (AGENTS.md 3.3.4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class QuizQuestionOut(BaseModel):
    """One servable quiz question — answer material is stripped by design.

    ``selected_index`` ranges over 0-3; ``selected_index=null`` ("Not sure")
    is submitted via :class:`AnswerIn` at scoring time.
    """

    id: str
    subfield_id: str
    concept_id: str
    difficulty: int = Field(ge=1, le=3)
    stem: str
    options: list[str] = Field(min_length=4, max_length=4)


class QuizResponse(BaseModel):
    """The full servable quiz: questions in ``sort_order``."""

    questions: list[QuizQuestionOut]


class AnswerIn(BaseModel):
    """One answer: ``selected_index`` 0-3, or null for "Not sure"."""

    question_id: str
    selected_index: int | None = Field(default=None, ge=0, le=3)


class AssessmentIn(BaseModel):
    """Diagnostic submission: six interest sliders plus the answers."""

    interests: dict[str, int] = Field(description="{subfield_id: slider 1-5}")
    answers: list[AnswerIn]


class PerQuestionFeedback(BaseModel):
    """Per-question result returned only AFTER scoring (never by GET /quiz)."""

    question_id: str
    correct: bool
    explanation: str
    concept_id: str


class AssessmentOut(BaseModel):
    """Scored diagnostic result: readiness per subfield plus feedback."""

    assessment_id: int
    profile_id: str
    taken_at: datetime
    # {subfield_id: readiness 0-100} (plan 4.5, difficulty-weighted).
    scores: dict[str, float]
    interests: dict[str, int]
    per_question: list[PerQuestionFeedback]
    # Concepts of wrong / not-sure answers, deduplicated, in answer order.
    weak_concepts: list[str]


class ProfileCreateIn(BaseModel):
    """Profile creation body; the client-generated UUID may be supplied.

    Anonymous by design (AGENTS.md 3.10.4): only the UUID is stored.
    """

    profile_id: str | None = Field(
        default=None, pattern=r"^[0-9a-fA-F-]{32,36}$", description="Optional client UUID"
    )


class ProfileOut(BaseModel):
    """Anonymous profile projection; ``id`` is the UUID the client keeps."""

    profile_id: str
    created_at: datetime
    interests: dict[str, int]
