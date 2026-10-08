"""Seeder validation and idempotency (plan steps 0.3.3 and 0.8).

These tests read the committed ``app/data/*.json`` reference files (never the
recorded SerpApi fixtures) plus inline payloads built in the test itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

import app.db.seed as seed_module
from app.core.errors import SeedDataError
from app.db.seed import (
    load_reference_json,
    reference_data_counts,
    seed_quiz_questions,
    seed_reference_data,
    validate_quiz_questions,
    validate_reference_data,
)

#: Exact row counts of the committed reference data — a drift here means the
#: data files changed without updating the tests (update deliberately).
EXPECTED_COUNTS = {
    "subfields": 7,
    "concepts": 34,
    "career_paths": 6,
    "skills": 53,
    # Quiz/profile tables are seeded elsewhere (Phase 3); reference seeding
    # does not touch them, so they must stay empty here.
    "questions": 0,
    "profiles": 0,
    "assessments": 0,
}


def _load_reference() -> tuple[Any, Any, Any]:
    """Load the three committed reference files as parsed JSON."""
    return (
        load_reference_json("taxonomy.json"),
        load_reference_json("career_paths.json"),
        load_reference_json("skills_vocab.json"),
    )


def test_reference_data_validates_cleanly() -> None:
    """The committed taxonomy/paths/vocabulary must satisfy every seeder rule."""
    taxonomy, careers, skills = _load_reference()

    assert validate_reference_data(taxonomy, careers, skills) == []


def test_taxonomy_has_no_prerequisite_cycles() -> None:
    """The committed taxonomy must be a DAG (plan 4.5: a cycle is a data bug)."""
    taxonomy, careers, skills = _load_reference()

    problems = validate_reference_data(taxonomy, careers, skills)

    assert [p for p in problems if "cycle" in p] == []


def test_skill_vocab_references_valid_subfields() -> None:
    """Every skill's subfield_ids must exist in the taxonomy (the AI can only emit vocab ids)."""
    taxonomy, careers, skills = _load_reference()

    problems = validate_reference_data(taxonomy, careers, skills)

    assert [p for p in problems if p.startswith("skill ")] == []


def test_validate_detects_prerequisite_cycle() -> None:
    """Inline cyclic data must be reported with a cycle message instead of loading."""
    taxonomy = {
        "subfields": [{"id": "x", "name": "X", "is_scored": True}],
        "concepts": [
            {"id": "a", "subfield_id": "x", "name": "A", "prerequisites": ["b"]},
            {"id": "b", "subfield_id": "x", "name": "B", "prerequisites": ["a"]},
        ],
    }

    problems = validate_reference_data(taxonomy, [], [])

    assert any("cycle" in p for p in problems)


def test_validate_reports_unknown_skill_subfield() -> None:
    """A skill pointing at a nonexistent subfield is a validation problem."""
    taxonomy = {
        "subfields": [{"id": "x", "name": "X", "is_scored": True}],
        "concepts": [],
    }
    skills = [{"id": "s", "name": "S", "subfield_ids": ["nope"], "concept_ids": []}]

    problems = validate_reference_data(taxonomy, [], skills)

    assert any(p.startswith("skill 's'") for p in problems)


def test_seed_is_idempotent(db_session: Session) -> None:
    """Seeding twice must not add rows — upserts are keyed by primary key (AGENTS 3.3.9)."""
    seed_reference_data(db_session)
    first = reference_data_counts(db_session)
    seed_reference_data(db_session)
    second = reference_data_counts(db_session)

    assert first == EXPECTED_COUNTS
    assert second == first


def test_seed_fails_loudly_on_invalid_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """Broken reference data raises SeedDataError with the problems listed, writing nothing."""
    broken_taxonomy = {
        "subfields": [{"id": "x", "name": "X", "is_scored": True}],
        "concepts": [
            {
                "id": "a",
                "subfield_id": "x",
                "name": "A",
                "prerequisites": ["does.not.exist"],
            }
        ],
    }
    (tmp_path / "taxonomy.json").write_text(json.dumps(broken_taxonomy), encoding="utf-8")
    (tmp_path / "career_paths.json").write_text("[]", encoding="utf-8")
    (tmp_path / "skills_vocab.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(seed_module, "DATA_DIR", tmp_path)

    with pytest.raises(SeedDataError, match="unknown prerequisite"):
        seed_reference_data(db_session)

    assert reference_data_counts(db_session)["subfields"] == 0


def test_load_reference_json_missing_file_raises(tmp_path: Path) -> None:
    """A missing reference file is reported as SeedDataError, not a bare OSError."""
    with pytest.raises(SeedDataError, match="not found"):
        load_reference_json("taxonomy.json", directory=tmp_path)


# ---------------------------------------------------------------------------
# Quiz question bank (Phase 3 step 3.1)
# ---------------------------------------------------------------------------


def test_committed_quiz_questions_validate_cleanly() -> None:
    """The committed quiz bank must satisfy every seeder rule against the taxonomy."""
    taxonomy, _, _ = _load_reference()
    questions = load_reference_json("quiz_questions.json")

    problems = validate_quiz_questions(
        questions,
        {s["id"] for s in taxonomy["subfields"]},
        {c["id"] for c in taxonomy["concepts"]},
    )

    assert problems == []


def test_committed_quiz_questions_cover_three_per_scored_subfield() -> None:
    """Every scored subfield needs >= 3 questions or the quiz endpoint refuses (plan 3.1)."""
    taxonomy, _, _ = _load_reference()
    questions = load_reference_json("quiz_questions.json")

    per_subfield: dict[str, int] = {}
    for q in questions:
        per_subfield[q["subfield_id"]] = per_subfield.get(q["subfield_id"], 0) + 1
    scored = [s["id"] for s in taxonomy["subfields"] if s.get("is_scored", True)]

    assert all(per_subfield.get(s, 0) >= 3 for s in scored)


def test_quiz_questions_are_placeholders_not_verified() -> None:
    """Placeholder questions must never ship with verified=true (AGENTS.md 3.11)."""
    questions = load_reference_json("quiz_questions.json")

    assert all(q["verified"] is False for q in questions)


def test_seed_quiz_questions_is_idempotent(db_session: Session) -> None:
    """Seeding the quiz bank twice must not duplicate rows (AGENTS.md 3.3.9)."""
    seed_reference_data(db_session)
    seed_quiz_questions(db_session)
    first = reference_data_counts(db_session)["questions"]
    seed_quiz_questions(db_session)

    assert first == 18
    assert reference_data_counts(db_session)["questions"] == first


def test_seed_quiz_questions_rejects_invalid(tmp_path: Path, monkeypatch, db_session) -> None:
    """A broken bank (bad correct_index / option count) fails loudly, writing nothing."""
    taxonomy, _, _ = _load_reference()
    (tmp_path / "taxonomy.json").write_text(json.dumps(taxonomy), encoding="utf-8")
    (tmp_path / "quiz_questions.json").write_text(
        json.dumps(
            [
                {
                    "id": "bad-1",
                    "subfield_id": "qec",
                    "concept_id": "qec.surface_code",
                    "difficulty": 2,
                    "stem": "s",
                    "options": ["a", "b", "c"],
                    "correct_index": 9,
                    "verified": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_module, "DATA_DIR", tmp_path)

    with pytest.raises(SeedDataError, match="correct_index"):
        seed_quiz_questions(db_session)

    assert reference_data_counts(db_session)["questions"] == 0
