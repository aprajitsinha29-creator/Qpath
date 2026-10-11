"""Unit tests for the evidence-gated flag rules (M-10 regression suite).

Pure functions only — no DB, no network, no LLM (AGENTS 3.7.1). Each keyword
rule and each consistency rule from the bug-fix spec has its own case; the
table-driven batches cover every keyword of every bucket.

Background (why these rules exist): the M-10 spot check found the model's
seniority/PhD/internship claims wrong in 15/20 sampled postings, because
``_persist_item`` used to store them verbatim. These tests pin the contract:
a claim survives only with matching keyword evidence, "Scientist" is never
seniority evidence, PhD flags come from text, internship comes from title
and extensions only.
"""

from __future__ import annotations

import pytest

from app.services.flag_rules import (
    EVIDENCE_DESCRIPTION_CHARS,
    derive_is_internship,
    derive_requires_phd,
    derive_seniority,
    find_seniority_evidence,
)

# ---------------------------------------------------------------- seniority


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Senior Research Scientist", {"senior"}),
        ("Staff Engineer, QEC", {"senior"}),
        ("Principal Scientist", {"senior"}),
        ("Sr. Quantum Developer", {"senior"}),
        ("Quantum Software Developer II (Mid-level)", {"mid"}),
        ("Entry-level encoding engineer", {"entry"}),
        ("Junior Researcher", {"entry"}),
        ("Associate Quantum Scientist", {"entry"}),
        ("New Grad Software Engineer", {"entry"}),
        ("Team Lead, Quantum Compilers", {"lead"}),
        ("Director of Quantum Hardware", {"lead"}),
        ("Head of Quantum Algorithms", {"lead"}),
        ("Engineering Manager", {"lead"}),
        ("Summer Intern, Microwave Design", {"intern"}),
        ("Postdoctoral Researcher", {"postdoc"}),
        ("Postdoc in Error Correction", {"postdoc"}),
        ("PhD Student Position", {"phd_student"}),
        ("Doctoral Student, QEC", {"phd_student"}),
        ("PhD Candidate in Quantum Info", {"phd_student"}),
        ("Assistant Professor of Physics", {"faculty"}),
        ("Quantum Faculty Position", {"faculty"}),
        ("Lecturer in Quantum Computing", {"faculty"}),
        ("Quantum Scientist", set()),
        ("Software Engineer", set()),
        ("Great benefits and a bonus structure", set()),
        ("", set()),
    ],
)
def test_find_seniority_evidence_keyword_rules(text: str, expected: set[str]) -> None:
    """Every bucket keyword matches; role words and noise match nothing."""
    assert find_seniority_evidence(text) == expected


def test_find_seniority_evidence_case_insensitive_and_plural() -> None:
    """Keywords work in any case and with plurals ("Interns", "PROFESSORS")."""
    assert find_seniority_evidence(" interns ") == {"intern"}
    assert find_seniority_evidence("PROFESSORS WANTED") == {"faculty"}


def test_find_seniority_evidence_reword_fakes_no_evidence() -> None:
    """Substring traps never count: staffing/mislead are not staff/lead."""
    assert find_seniority_evidence("staffing coordinator") == set()
    assert find_seniority_evidence("misleading title") == set()


@pytest.mark.parametrize(
    ("model", "expected"),
    [("unknown", None), ("", None), (None, None)],
)
def test_derive_seniority_no_claim_is_null(model: str | None, expected: str | None) -> None:
    """A missing/\"unknown\" claim stays NULL — the spec's \"Otherwise null\"."""
    assert derive_seniority("Senior Engineer", "description", model) is expected


def test_derive_seniority_kept_when_keyword_in_title() -> None:
    """Claim + matching title keyword → bucket is stored."""
    assert derive_seniority("Senior Quantum Scientist", None, "senior") == "senior"


def test_derive_seniority_kept_when_keyword_in_first_3000_chars() -> None:
    """Keyword deep inside the first 3000 chars still supports the claim."""
    padding = "x" * 2900
    assert derive_seniority("Engineer", f"{padding} mid-level role", "mid") == "mid"


def test_derive_seniority_dropped_when_keyword_beyond_3000_chars() -> None:
    """Evidence past the window does not count (same window the model saw)."""
    assert "senior" not in (
        derive_seniority("Engineer", "x" * 3000 + " senior role", "senior") or ""
    )
    assert (
        len("x" * 3000 + " senior role") > EVIDENCE_DESCRIPTION_CHARS
    )  # sanity: the case really is out of window


def test_derive_seniority_unlabelled_senior_becomes_null() -> None:
    """Regression: "Quantum Scientist" with model "senior" must become NULL."""
    assert derive_seniority("Quantum Scientist", "Build quantum circuits.", "senior") is None


def test_derive_seniority_engineer_or_scientist_never_evidence() -> None:
    """Role words like Scientist/Engineer must not infer any bucket."""
    assert derive_seniority("Research Scientist", None, "senior") is None
    assert derive_seniority("Quantum Engineer", None, "mid") is None


def test_derive_seniority_wrong_model_bucket_dropped() -> None:
    """A bucket in the schema but unbacked here (or garbage) is dropped."""
    assert derive_seniority("Intern", None, "faculty") is None
    assert derive_seniority("Professor", None, "garbage") is None
    assert derive_seniority("Professor", None, "faculty") == "faculty"


def test_derive_seniority_faculty_bucket() -> None:
    """The new faculty bucket survives only on professor/faculty/lecturer text."""
    assert derive_seniority("Faculty Position in QIT", None, "faculty") == "faculty"
    assert derive_seniority("Teacher", None, "faculty") is None


# ---------------------------------------------------------------- PhD flag


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A PhD in physics is required.", True),
        ("Must hold a doctorate in EE.", True),
        ("Requires a PhD or equivalent experience.", True),
        ("PhD required, 3+ years.", True),
        ("Required qualifications: PhD in quantum information.", True),
        ("This postdoc position studies error correction.", True),
        ("We welcome PhD candidates to apply.", True),
        ("Open to doctoral students in CS.", True),
        ("No PhD required.", False),
        ("No doctorate is needed for this role.", False),
        ("This position does not require a PhD.", False),
        ("PhD is not required for this role.", False),
        ("A PhD is preferred but not required.", None),  # "preferred" tested below too
        ("PhD preferred.", None),
        ("Preferred background: doctorate in physics.", None),
        ("Strong quantum background required.", None),  # "required" without PhD
        ("Quantum Scientist with 5 years experience.", None),  # silence → null
    ],
)
def test_derive_requires_phd_true_false_and_null(text: str, expected: bool | None) -> None:
    """True/False/None exactly per the spec; "preferred" is None, never guessed."""
    assert derive_requires_phd(text, None) is expected


def test_derive_requires_phd_no_phd_wins_over_role() -> None:
    """Explicit negative beats everything, incl. role-word evidence."""
    assert derive_requires_phd("Postdoc — no PhD required (sabbatical hire)", None) is False


def test_derive_requires_phd_searches_description_window() -> None:
    """PhD wording deep in the description is still found."""
    description = "x" * 2500 + " A PhD is required for this position."
    assert derive_requires_phd("Engineer", description) is True


# ----------------------------------------------------------- internship rule


@pytest.mark.parametrize(
    ("title", "extensions", "expected"),
    [
        ("Research Intern", [], True),
        ("Quantum Engineer Internship", [], True),
        ("Summer interns program", [], True),
        ("Research Intern", ["6 weeks ago", "Internship"], True),
        ("Quantum Developer", ["Internship"], True),
        ("Research Intern", ["Full–time"], True),
        ("Internal tools engineer", [], False),  # "internal" never matches
        ("International sales", [], False),
        ("Quantum Scientist", [], False),
        ("Scientist", ["Full–time", "3 days ago"], False),
        ("", [], False),
    ],
)
def test_derive_is_internship_title_and_extensions_rule(
    title: str, extensions: list[str], expected: bool
) -> None:
    """\\bintern(ship)?s?\\b on title/extensions; never "internal"; input-only."""
    assert derive_is_internship(title, extensions) is expected


# --------------------------------------------------- internship↔seniority consistency


def test_internship_keyword_is_also_intern_seniority_evidence() -> None:
    """The internship regex IS the intern bucket keyword: an internship title
    carries "intern" evidence, and a contradicting model claim (e.g. senior)
    is dropped in favour of intern in the service layer (covered end-to-end in
    test_extraction_flags)."""
    assert find_seniority_evidence("Research Intern") == {"intern"}
    assert derive_seniority("Research Intern", None, "intern") == "intern"
    assert derive_seniority("Research Intern", None, "senior") is None


def test_non_intern_title_cannot_become_internship() -> None:
    """A regular title (even with a contradicting model claim) is not an
    internship: rule-based detection never consults the model flag."""
    assert derive_is_internship("Senior Quantum Scientist", []) is False
    assert derive_is_internship("Senior Quantum Scientist", ["Full\u2013time"]) is False
