"""Schemas for the quiz/profile endpoints (plan 3.2).

``QuizQuestionOut`` deliberately has NO ``correct_index`` and NO ``explanation``:
GET /quiz must never reveal answers — scoring happens server-side
(AGENTS.md 3.10.3). ORM models never leave the service layer (AGENTS.md 3.3.4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestionOut(BaseModel):
    """One servable quiz question — answer material is stripped by design.

    Built from ORM rows (from_attributes); the ORM's ``correct_index`` and
    ``explanation`` columns are simply not declared here, so they can never
    serialize (AGENTS.md 3.10.3).
    """

    model_config = ConfigDict(from_attributes=True)  # build from ORM rows

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

    model_config = ConfigDict(from_attributes=True)  # build from ORM rows

    # The ORM column is ``id``; the wire name is ``profile_id`` for clarity.
    profile_id: str = Field(validation_alias="id")
    created_at: datetime
    interests: dict[str, int]
    # Carry-over from Phase 4 scope: vocabulary-validated skill ids declared by
    # the user via PUT /profiles/{id}/skills. Additive only — ranking does not
    # read this field (test_declared_skills_do_not_change_ranked_paths).
    declared_skills: list[str] = Field(default_factory=list)
    # Phase 5: the tracked career path (set via PUT /profiles/{id}/chosen-path).
    # last_seen_at and completed_concepts stay unexposed — nothing consumes them
    # yet and they are internal bookkeeping.
    chosen_path_id: str | None = None
