"""``GET /quiz`` — servable diagnostic questions (plan 3.4).

Thin router per AGENTS.md 3.3.1. The response schema guarantees that no
answer material (correct_index/explanation) can leak: it is not on
``QuizQuestionOut`` at all (AGENTS.md 3.10.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.quiz import QuizQuestionOut, QuizResponse
from app.services import quiz_service

router = APIRouter(tags=["quiz"])


@router.get("/quiz", response_model=QuizResponse, summary="Diagnostic questions (no answers)")
def get_quiz(db: Session = Depends(get_db)) -> QuizResponse:
    """Return the servable quiz questions in serve order.

    Args:
        db: request session.

    Returns:
        QuizResponse with questions ordered by ``sort_order``; never includes
        correct answers or explanations.

    Raises:
        QuizContentError: any scored subfield has < 3 servable questions (503).
    """
    return QuizResponse(
        questions=[QuizQuestionOut.model_validate(q) for q in quiz_service.build_quiz(db)]
    )
