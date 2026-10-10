"""Unit tests for the pure match function (Phase 5, tests 1-7).

Pure logic only: no DB, no network (AGENTS.md 3.7.1). Table-driven cases from
the phase instructions, asserted with pytest.approx.
"""

from __future__ import annotations

import pytest

from app.services.match_service import posting_match

CASES = [
    # (case name, posting_skills, declared, readiness, expected)
    ("full_overlap_readiness_1", ["python", "qiskit"], ["python", "qiskit"], 100.0, 100.0),
    ("no_overlap_readiness_1", [" Stim".strip()], ["python"], 100.0, 40.0),
    ("one_of_two_declared_readiness_half", ["a", "b"], ["a"], 50.0, 50.0),
    ("one_of_three_declared_readiness_75", ["a", "b", "c"], ["a"], 75.0, 50.0),
    ("declared_superset_overlap_one", ["python"], ["python", "qiskit", "stim"], 100.0, 100.0),
]


@pytest.mark.parametrize(
    ("posting_skills", "declared", "readiness", "expected"),
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_posting_match_formulas(
    posting_skills: list[str], declared: list[str], readiness: float, expected: float
) -> None:
    """Cases 1-6: the plan 4.5 formula with the stated weights."""
    assert posting_match(posting_skills, declared, readiness) == pytest.approx(expected, abs=1e-9)


def test_posting_match_no_extracted_skills_returns_none() -> None:
    """Case 7: None (not enough info), never 0 — the caller distinguishes the two."""
    assert posting_match([], ["python"], 100.0) is None
    assert posting_match(None, ["python"], 100.0) is None


def test_posting_match_no_declared_skills_returns_none() -> None:
    """No declared skills -> None, not 0.4×readiness: overlap is undefined,
    not zero, and the readiness remainder would fake a match opinion."""
    assert posting_match(["python", "stim"], [], 100.0) is None
    assert posting_match(["python"], [], 50.0) is None
    assert posting_match(["python", "qiskit"], [], 0.0) is None
