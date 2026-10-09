"""Unit tests for the pure scoring functions (plan 3.6 / 4.7, BUILD_PLAN 4.5).

All cases are table-driven: one row per behavior, no DB, no HTTP. The second
half covers the Phase 4 path matcher: normalizations, weighted score, ranking
and the saturation note.
"""

from __future__ import annotations

import math

import pytest

from app.services.scoring_service import (
    LOW_DATA_THRESHOLD,
    SATURATION_MIN_SUBFIELDS,
    W_DEMAND,
    W_INTEREST,
    W_READINESS,
    WEIGHTS_PERCENT,
    PathCandidate,
    QuestionMeta,
    demand_n,
    interest_n,
    normalize_selections,
    path_score,
    per_question_feedback,
    rank_paths,
    readiness_n,
    readiness_scores,
    saturation_note,
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


# ---------------------------------------------------------------------------
# Phase 4: path matcher (plan 4.2 / 4.7)
# ---------------------------------------------------------------------------


def test_path_score_weights_sum_to_one() -> None:
    """The three named weights must sum to 1.0 (plan 4.7 weights-sum check)."""
    assert W_INTEREST + W_DEMAND + W_READINESS == pytest.approx(1.0)
    assert WEIGHTS_PERCENT == {"interest": 40.0, "demand": 30.0, "readiness": 30.0}


@pytest.mark.parametrize(
    ("slider", "expected"),
    [
        (1, 0.0),
        (2, 0.25),
        (3, 0.5),
        (5, 1.0),
        # Out-of-range values clamp instead of producing a >100 score.
        (0, 0.0),
        (7, 1.0),
    ],
)
def test_interest_n_table(slider: int, expected: float) -> None:
    """interest_n = (slider - 1) / 4, clamped to 0-1 (plan 4.5)."""
    assert interest_n(slider) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, 0.0), (50, 0.5), (100, 1.0), (-10, 0.0), (250, 1.0)],
)
def test_readiness_n_table(score: float, expected: float) -> None:
    """readiness_n = score / 100, clamped to 0-1 (plan 4.5)."""
    assert readiness_n(score) == pytest.approx(expected)


def test_demand_n_zero_postings_everywhere_is_zero() -> None:
    """max_active = 0 → 0.0, no division by zero (plan 4.7 edge case)."""
    assert demand_n(0, 0) == 0.0


def test_demand_n_dominant_subfield_is_one() -> None:
    """The subfield with max_active normalizes to 1.0 exactly."""
    assert demand_n(120, 120) == pytest.approx(1.0)


def test_demand_n_uses_log_scale() -> None:
    """demand_n = ln(1+active)/ln(1+max) (plan 4.5 log compression)."""
    assert demand_n(10, 100) == pytest.approx(math.log(11) / math.log(101))
    # A subfield with 1/10th the postings is NOT at 1/10th the demand.
    assert demand_n(10, 100) > 0.1


def test_path_score_matches_formula() -> None:
    """score = 100 * (0.4*i + 0.3*d + 0.3*r) (plan 4.5)."""
    assert path_score(1.0, 0.0, 0.0) == pytest.approx(40.0)
    assert path_score(0.5, 1.0, 0.5) == pytest.approx(100 * (0.2 + 0.3 + 0.15))
    assert path_score(0.0, 0.0, 0.0) == 0.0


def _candidate(
    path_id: str,
    *,
    interest: float = 0.5,
    demand: float = 0.5,
    readiness: float = 0.5,
    active: int = 10,
) -> PathCandidate:
    """Shorthand for a PathCandidate with overridable fields."""
    return PathCandidate(
        path_id=path_id,
        subfield_id=path_id.removesuffix("_path"),
        interest=interest,
        demand=demand,
        readiness=readiness,
        active_postings=active,
    )


def test_rank_paths_orders_by_score_and_displayed_math_matches() -> None:
    """Highest score first; hand-recomputing from displayed values matches (4.8)."""
    ranked = rank_paths(
        [
            _candidate("low_path", interest=0.0),
            _candidate("high_path", interest=1.0),
            _candidate("mid_path", interest=0.5),
        ]
    )

    assert [r.path_id for r in ranked] == ["high_path", "mid_path", "low_path"]
    assert [r.rank for r in ranked] == [1, 2, 3]
    # Displayed math is exact: score == weighted sum of displayed percents.
    for r in ranked:
        recomputed = (
            r.interest * WEIGHTS_PERCENT["interest"]
            + r.demand * WEIGHTS_PERCENT["demand"]
            + r.readiness * WEIGHTS_PERCENT["readiness"]
        ) / 100
        assert r.score == pytest.approx(recomputed, abs=0.05)


def test_rank_paths_tie_breaks_by_demand_then_id() -> None:
    """Equal scores: higher demand wins; then alphabetical id (plan 4.5)."""
    ranked = rank_paths(
        [
            _candidate("b_path", demand=0.4, interest=0.5),
            _candidate("a_path", demand=0.4, interest=0.5),
            _candidate("c_path", demand=0.9, interest=0.5),
        ]
    )

    assert [r.path_id for r in ranked] == ["c_path", "a_path", "b_path"]


def test_rank_paths_zero_postings_everywhere_scores_on_profile_only() -> None:
    """No postings anywhere → demand 0 for all, no crash, ranking still works."""
    ranked = rank_paths(
        [
            _candidate("a_path", active=0, demand=0.0),
            _candidate("b_path", active=0, demand=0.0),
        ]
    )

    assert all(r.demand == 0.0 for r in ranked)
    # Identical everything → alphabetical tie-break keeps the order stable.
    assert [r.path_id for r in ranked] == ["a_path", "b_path"]


def test_rank_paths_low_data_flag_below_threshold() -> None:
    """active_postings < 8 → low_data (plan 4.5); at 8 → not low."""
    ranked = rank_paths(
        [
            _candidate("thin_path", active=LOW_DATA_THRESHOLD - 1),
            _candidate("ok_path", active=LOW_DATA_THRESHOLD),
        ]
    )
    flags = {r.path_id: r.low_data for r in ranked}

    assert flags["thin_path"] is True
    assert flags["ok_path"] is False


def test_rank_paths_interest_only_and_demand_side_tie_on_demand() -> None:
    """Interest-only vs an equal-total demand/readiness combo tie by score,
    and the tie-break then ranks the demand-heavy candidate first (plan 4.5)."""
    ranked = rank_paths(
        [
            # interest 1.0 → 40 points, no demand/readiness.
            _candidate("interest_path", interest=1.0, demand=0.0, readiness=0.0),
            # demand 1.0 → 30 points + readiness 1/3 → 10 points = 40 points.
            _candidate("demand_path", interest=0.0, demand=1.0, readiness=1.0 / 3),
        ]
    )
    scores = {r.path_id: r.score for r in ranked}

    # readiness rounds to 0.333 → 9.99 points, so the tie is within a point.
    assert scores["interest_path"] == pytest.approx(scores["demand_path"], abs=0.1)
    # On a near-tie the higher demand component ranks first.
    assert ranked[0].path_id == "demand_path"


@pytest.mark.parametrize(
    ("capped", "expected_note"),
    [
        (set(), None),
        ({"qec"}, None),
        # One below the guard: 3 of 6 is still under plan 4.5's ">= 4 of 6".
        ({"qec", "hardware", "software"}, None),
        (
            {"qec", "hardware", "software", "qml"},
            "4 of 6 subfields hit the search page cap",
        ),
    ],
)
def test_saturation_note_guard(capped: set[str], expected_note: str | None) -> None:
    """The saturation note appears only at >= SATURATION_MIN_SUBFIELDS (plan 4.5)."""
    note = saturation_note(capped, 6)
    if expected_note is None:
        assert note is None
    else:
        assert note is not None and expected_note in note
    assert SATURATION_MIN_SUBFIELDS == 4
