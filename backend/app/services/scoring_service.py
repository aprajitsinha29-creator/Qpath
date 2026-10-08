"""Pure scoring functions for the orientation diagnostic (plan 3.3 / 4.5).

NO database, NO HTTP, NO LLM — everything here is deterministic and unit-tested
(AGENTS.md 3.3.10: the LLM never decides a number). Constants live here.

Formula (BUILD_PLAN 4.5): a correct answer earns its ``difficulty`` (1-3) in
points; wrong, "Not sure" (null) and unanswered earn 0 — no negative marking.
``readiness_s = 100 * earned_s / available_s``; with difficulties 1,2,3 the
available total per subfield is 6.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionMeta:
    """The scoring-relevant projection of a question (no stem/options needed).

    Attributes:
        subfield_id: which scored subfield the question counts toward.
        difficulty: 1-3; doubles as the point value of a correct answer.
        correct_index: the index of the correct option.
        concept_id: taxonomy concept this question tests (feeds weak_concepts).
    """

    subfield_id: str
    difficulty: int
    correct_index: int
    concept_id: str


def normalize_selections(
    answers: list[tuple[str, int | None]], known_ids: set[str]
) -> dict[str, int | None]:
    """Validate raw answers and map them to ``question_id -> selected_index|null``.

    Args:
        answers: (question_id, selected_index-or-None) pairs as submitted.
        known_ids: the servable question ids; anything else is invalid.

    Returns:
        A dict keyed by question id. Missing questions are treated as
        unanswered (they simply do not appear — scoring gives them 0).

    Raises:
        ValueError: on an unknown question id or a duplicate answer; callers
            map this to HTTP 422.
    """
    selections: dict[str, int | None] = {}
    for question_id, selected in answers:
        if question_id not in known_ids:
            raise ValueError(f"unknown question id '{question_id}'")
        if question_id in selections:
            raise ValueError(f"duplicate answer for question '{question_id}'")
        # Keep the "Not sure" (None) marker distinct from a wrong choice: both
        # score 0, but weak_concepts lists both while "correct" differs.
        selections[question_id] = selected
    return selections


def readiness_scores(
    question_meta: dict[str, QuestionMeta], selections: dict[str, int | None]
) -> dict[str, float]:
    """Compute readiness (0-100) per subfield from the submitted selections.

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        selections: question_id -> selected index (int) or None ("Not sure").
            Questions absent from the dict count as unanswered (0 points).

    Returns:
        ``{subfield_id: readiness}`` for every subfield that has at least one
        question in ``question_meta`` (the caller guarantees the 6 scored
        subfields are covered by the >=3-per-subfield guard).

    Note:
        Division safety: ``available_s`` is 0 only if a subfield has no
        questions, which the quiz guard prevents; the guard clause below
        returns 0.0 defensively rather than crashing.
    """
    earned: dict[str, float] = {}
    available: dict[str, float] = {}
    for question_id, meta in question_meta.items():
        available[meta.subfield_id] = available.get(meta.subfield_id, 0) + meta.difficulty
        if selections.get(question_id) == meta.correct_index:
            # Correct: earn the difficulty as points (plan 4.5).
            earned[meta.subfield_id] = earned.get(meta.subfield_id, 0) + meta.difficulty
        # Wrong / None / unanswered: 0 points, no negative marking.
    return {
        subfield_id: 100.0 * earned.get(subfield_id, 0.0) / total if total else 0.0
        for subfield_id, total in available.items()
    }


def weak_concepts(
    question_meta: dict[str, QuestionMeta], selections: dict[str, int | None]
) -> list[str]:
    """Return concepts of wrong / "Not sure" answers, deduplicated, answer order.

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        selections: question_id -> selected index (int) or None ("Not sure").

    Returns:
        Concept ids in the order the failing answers were given (deterministic
        because ``selections`` is built from the submitted answer list order).
    """
    seen: set[str] = set()
    weak: list[str] = []
    for question_id, meta in question_meta.items():
        selected = selections.get(question_id)
        if selected != meta.correct_index and meta.concept_id not in seen:
            # Wrong OR "Not sure" OR unanswered all go here (plan 3.3).
            seen.add(meta.concept_id)
            weak.append(meta.concept_id)
    return weak


def per_question_feedback(
    question_meta: dict[str, QuestionMeta],
    explanations: dict[str, str],
    selections: dict[str, int | None],
) -> list[dict[str, object]]:
    """Build the post-submission feedback rows (question_id, correct, explanation).

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        explanations: question_id -> owner-written explanation text.
        selections: question_id -> selected index (int) or None ("Not sure").

    Returns:
        A list of plain dicts (Pydantic serializes them) in servable-question
        order; ``correct`` is False for wrong, "Not sure" and unanswered.
    """
    return [
        {
            "question_id": question_id,
            "correct": selections.get(question_id) == meta.correct_index,
            "explanation": explanations.get(question_id, ""),
            "concept_id": meta.concept_id,
        }
        for question_id, meta in question_meta.items()
    ]
