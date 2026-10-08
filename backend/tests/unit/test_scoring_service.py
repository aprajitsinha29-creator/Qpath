"""Unit tests for the pure scoring functions (plan 3.6, BUILD_PLAN 4.5).

All cases are table-driven: one row per behavior, no DB, no HTTP.
"""

from __future__ import annotations

import pytest

from app.services.scoring_service import (
    QuestionMeta,
    normalize_selections,
    per_question_feedback,
    readiness_scores,
    weak_concepts,
)

# A tiny bank covering difficulties 1-3 across two subfields.
META = {
    "qec-1": QuestionMeta("qec", 1, correct_index=2, concept_id="qec.stabilizer_codes"),
    "qec-2": QuestionMeta("qec", 2, correct_index=0, concept_id="qec.logical_vs_physical"),
    "qec-3": QuestionMeta("qec", 3, correct_index=1, concept_id="qec.surface_code"),
    "hw-1": QuestionMeta("hardware", 1, correct_index=3, concept_id="hw.superconducting"),
    "hw-2": QuestionMeta("hardware", 2, correct_index=1, concept_id="hw.trapped_ions"),
    "hw-3": QuestionMeta("hardware", 3, correct_index=0, concept_id="hw.control_readout"),
}


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        # All correct -> 100 in every subfield.
        (
            {"qec-1": 2, "qec-2": 0, "qec-3": 1, "hw-1": 3, "hw-2": 1, "hw-3": 0},
            {"qec": 100.0, "hardware": 100.0},
        ),
        # All wrong -> 0 (no negative marking can push below zero).
        (
            {"qec-1": 0, "qec-2": 1, "qec-3": 2, "hw-1": 0, "hw-2": 0, "hw-3": 1},
            {"qec": 0.0, "hardware": 0.0},
        ),
        # All "Not sure" -> 0 everywhere (guessing must not inflate scores).
        (
            {"qec-1": None, "qec-2": None, "qec-3": None, "hw-1": None, "hw-2": None, "hw-3": None},
            {"qec": 0.0, "hardware": 0.0},
        ),
        # Unanswered (absent from the dict) counts like "Not sure" -> 0.
        ({}, {"qec": 0.0, "hardware": 0.0}),
        # Mixed: correct on difficulties 1 and 3 only -> 4/6 = 66.67 (plan 3.6).
        (
            {"qec-1": 2, "qec-2": 1, "qec-3": 1, "hw-1": 3, "hw-2": 0, "hw-3": 0},
            {"qec": 100 * 4 / 6, "hardware": 100 * 4 / 6},
        ),
        # Difficulty weighting: only the d3 answer correct -> 3/6 = 50.
        (
            {"qec-1": 0, "qec-2": 1, "qec-3": 1, "hw-1": 0, "hw-2": 2, "hw-3": 3},
            {"qec": 50.0, "hardware": 0.0},
        ),
        # Partial submission: only one subfield answered, other subfield empty.
        ({"qec-2": 0}, {"qec": 100 * 2 / 6, "hardware": 0.0}),
    ],
)
def test_readiness_scores_table(answers: dict, expected: dict) -> None:
    """Readiness = 100 * earned / available, weighted by difficulty (plan 4.5)."""
    assert readiness_scores(META, answers) == pytest.approx(expected)


def test_readiness_scores_ignores_unknown_question_ids() -> None:
    """Selections for ids outside the meta dict are not scored (defensive)."""
    scores = readiness_scores(META, {"qec-1": 2, "ghost-q": 0})
    # Only qec-1 was answered (correct, d1): 1/6 of qec's available points.
    assert scores["qec"] == pytest.approx(100.0 / 6)


def test_weak_concepts_lists_wrong_and_not_sure_dedup() -> None:
    """Wrong and "Not sure" answers both feed weak_concepts, deduplicated (plan 3.3)."""
    answers = {
        "qec-1": 0,  # wrong -> qec.stabilizer_codes
        "qec-2": None,  # not sure -> qec.logical_vs_physical
        "qec-3": 1,  # correct
        "hw-1": 2,  # wrong -> hw.superconducting
        "hw-2": 1,  # correct
        "hw-3": 0,  # correct
    }
    assert weak_concepts(META, answers) == [
        "qec.stabilizer_codes",
        "qec.logical_vs_physical",
        "hw.superconducting",
    ]


def test_weak_concepts_deduplicates_repeated_concept() -> None:
    """Two failing questions on the same concept appear once (plan 3.3)."""
    meta = {
        "a": QuestionMeta("qec", 1, correct_index=0, concept_id="qec.surface_code"),
        "b": QuestionMeta("qec", 2, correct_index=1, concept_id="qec.surface_code"),
    }
    assert weak_concepts(meta, {"a": 1, "b": 0}) == ["qec.surface_code"]


def test_normalize_selections_maps_and_keeps_not_sure() -> None:
    """Valid answers map through; "Not sure" (None) is preserved."""
    selections = normalize_selections([("qec-1", 2), ("qec-2", None)], set(META))
    assert selections == {"qec-1": 2, "qec-2": None}


@pytest.mark.parametrize(
    "answers",
    [
        [("qec-1", 2), ("ghost-q", 1)],  # unknown question id
        [("qec-1", 2), ("qec-1", 3)],  # duplicate answer
    ],
)
def test_normalize_selections_rejects_invalid(answers: list) -> None:
    """Unknown ids and duplicates raise ValueError -> HTTP 422 (plan 3.3)."""
    with pytest.raises(ValueError):
        normalize_selections(answers, set(META))


def test_per_question_feedback_flags_correctness() -> None:
    """Feedback marks correct answers and explains, in serve order."""
    answers = {"qec-1": 2, "qec-2": None, "qec-3": 5}
    feedback = per_question_feedback(META, {"qec-1": "expl-1"}, answers)
    # Serve order covers the whole bank; the first three rows are the qec ones.
    assert [f["question_id"] for f in feedback] == [
        "qec-1",
        "qec-2",
        "qec-3",
        "hw-1",
        "hw-2",
        "hw-3",
    ]
    assert feedback[0] == {
        "question_id": "qec-1",
        "correct": True,
        "explanation": "expl-1",
        "concept_id": "qec.stabilizer_codes",
    }
    assert feedback[1] == {
        "question_id": "qec-2",
        "correct": False,
        "explanation": "",
        "concept_id": "qec.logical_vs_physical",
    }
    assert feedback[2] == {
        "question_id": "qec-3",
        "correct": False,
        "explanation": "",
        "concept_id": "qec.surface_code",
    }
