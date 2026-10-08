"""Idempotent reference-data seeder: loads ``app/data/*.json`` into SQLite.

Runs on every startup from the lifespan (after ``create_all``). All validation
happens **before** any write: referenced ids must resolve, concept prerequisites
must form a DAG (a cycle is a data bug — the Phase 6 learning plan topologically
sorts this graph), skill ``subfield_ids`` must exist, and career paths must map
1:1 onto scored subfields. Any problem raises :class:`SeedDataError` so the app
fails at startup with a clear message (plan step 0.3.3).
"""

from __future__ import annotations

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import SeedDataError
from app.models import Assessment, CareerPath, Concept, Profile, Question, Skill, Subfield

logger = logging.getLogger(__name__)

#: Where the committed reference JSON files live (taxonomy, careers, skills, ...).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_reference_json(filename: str, directory: Path | None = None) -> Any:
    """Read one reference JSON file.

    Args:
        filename: file name inside ``directory`` (e.g. ``taxonomy.json``).
        directory: defaults to :data:`DATA_DIR` (resolved at call time so tests
            can repoint the module attribute).

    Returns:
        The parsed JSON payload.

    Raises:
        SeedDataError: when the file is missing or not valid JSON.
    """
    base = DATA_DIR if directory is None else directory
    path = base / filename
    if not path.is_file():
        raise SeedDataError(f"{filename} not found in {path.parent}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SeedDataError(f"{filename} is not valid JSON: {exc}") from exc


def validate_reference_data(taxonomy: object, career_paths: object, skills: object) -> list[str]:
    """Check the three reference payloads and return every problem found.

    Args:
        taxonomy: parsed ``taxonomy.json`` (``{"subfields": [...], "concepts": [...]}``).
        career_paths: parsed ``career_paths.json`` (a list).
        skills: parsed ``skills_vocab.json`` (a list).

    Returns:
        A list of human-readable problems; an empty list means the data can be
        seeded. Problems are collected instead of raised one-by-one so a broken
        file reports everything at once.
    """
    problems: list[str] = []

    # --- Shape guards: bail out early so the deep checks cannot crash. ---
    if not isinstance(taxonomy, dict):
        return ["taxonomy.json must be a JSON object"]
    raw_subfields = taxonomy.get("subfields")
    raw_concepts = taxonomy.get("concepts")
    if not isinstance(raw_subfields, list) or not raw_subfields:
        return ["taxonomy.json: 'subfields' must be a non-empty list"]
    if not isinstance(raw_concepts, list):
        return ["taxonomy.json: 'concepts' must be a list"]
    if not isinstance(career_paths, list):
        return ["career_paths.json must be a JSON array"]
    if not isinstance(skills, list):
        return ["skills_vocab.json must be a JSON array"]

    # --- Subfields ---
    subfield_ids: set[str] = set()
    scored_ids: set[str] = set()
    for raw in raw_subfields:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw.get("name"):
            problems.append(f"subfield entry lacks id/name: {raw!r}")
            continue
        subfield_id = raw["id"]
        if subfield_id in subfield_ids:
            problems.append(f"duplicate subfield id '{subfield_id}'")
        subfield_ids.add(subfield_id)
        if raw.get("is_scored", True):
            scored_ids.add(subfield_id)

    # --- Concepts (two passes: ids first, so prerequisites can resolve) ---
    concept_ids: set[str] = set()
    prerequisites: dict[str, list[str]] = {}
    for raw in raw_concepts:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw.get("name"):
            problems.append(f"concept entry lacks id/name: {raw!r}")
            continue
        concept_id = raw["id"]
        if concept_id in concept_ids:
            problems.append(f"duplicate concept id '{concept_id}'")
        concept_ids.add(concept_id)
        owner = raw.get("subfield_id")
        if owner not in subfield_ids:
            problems.append(f"concept '{concept_id}' references unknown subfield '{owner}'")
        prereqs = raw.get("prerequisites", [])
        if not isinstance(prereqs, list):
            problems.append(f"concept '{concept_id}': prerequisites must be a list")
            prereqs = []
        prerequisites[concept_id] = [p for p in prereqs if isinstance(p, str)]

    unresolved = [
        (cid, p) for cid, prereqs in prerequisites.items() for p in prereqs if p not in concept_ids
    ]
    for cid, p in unresolved:
        problems.append(f"concept '{cid}' has unknown prerequisite '{p}'")
    if not unresolved and _has_prerequisite_cycle(prerequisites):
        problems.append("concept prerequisites contain a cycle")

    # --- Career paths: 1:1 over scored subfields ---
    path_ids: set[str] = set()
    paths_per_subfield: dict[str, int] = {}
    for raw in career_paths:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw.get("title"):
            problems.append(f"career path entry lacks id/title: {raw!r}")
            continue
        path_id = raw["id"]
        if path_id in path_ids:
            problems.append(f"duplicate career path id '{path_id}'")
        path_ids.add(path_id)
        target = raw.get("subfield_id")
        if target not in subfield_ids:
            problems.append(f"career path '{path_id}' references unknown subfield '{target}'")
            continue
        if target not in scored_ids:
            problems.append(f"career path '{path_id}' targets unscored subfield '{target}'")
            continue
        paths_per_subfield[target] = paths_per_subfield.get(target, 0) + 1
    for subfield_id in sorted(scored_ids):
        count = paths_per_subfield.get(subfield_id, 0)
        if count == 0:
            problems.append(f"scored subfield '{subfield_id}' has no career path")
        elif count > 1:
            problems.append(
                f"scored subfield '{subfield_id}' has {count} career paths (expected exactly 1)"
            )

    # --- Skills: vocabulary ids + valid subfield/concept references ---
    skill_ids: set[str] = set()
    for raw in skills:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw.get("name"):
            problems.append(f"skill entry lacks id/name: {raw!r}")
            continue
        skill_id = raw["id"]
        if skill_id in skill_ids:
            problems.append(f"duplicate skill id '{skill_id}'")
        skill_ids.add(skill_id)
        for ref in raw.get("subfield_ids", []):
            if ref not in subfield_ids:
                problems.append(f"skill '{skill_id}' references unknown subfield '{ref}'")
        for ref in raw.get("concept_ids", []):
            if ref not in concept_ids:
                problems.append(f"skill '{skill_id}' references unknown concept '{ref}'")

    return problems


def _has_prerequisite_cycle(prerequisites: dict[str, list[str]]) -> bool:
    """Return True when the prerequisite graph contains a cycle (Kahn's algorithm).

    Args:
        prerequisites: concept id -> prerequisite concept ids. Callers must have
            already verified that every reference resolves.

    A cycle means the Phase 6 topological sort would loop forever, so the seeder
    treats it as a fatal data bug (plan 4.5).
    """
    in_degree = {cid: 0 for cid in prerequisites}
    dependents: dict[str, list[str]] = {cid: [] for cid in prerequisites}
    for cid, prereqs in prerequisites.items():
        for prereq in prereqs:
            in_degree[cid] += 1
            dependents[prereq].append(cid)
    queue = deque(cid for cid, degree in in_degree.items() if degree == 0)
    removed = 0
    while queue:
        cid = queue.popleft()
        removed += 1
        for dependent in dependents[cid]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
    return removed != len(prerequisites)


def validate_quiz_questions(
    questions: object, subfield_ids: set[str], concept_ids: set[str]
) -> list[str]:
    """Check the quiz-question payload and return every problem found.

    Args:
        questions: parsed ``quiz_questions.json`` (a list of question objects).
        subfield_ids: valid subfield ids (from the already-validated taxonomy).
        concept_ids: valid concept ids (from the already-validated taxonomy).

    Returns:
        A list of human-readable problems; empty means the bank can be seeded.
        Per BUILD_PLAN 6.2: exactly 4 options, ``correct_index`` 0-3,
        ``difficulty`` 1-3, and resolvable ``subfield_id``/``concept_id``.
    """
    problems: list[str] = []
    if not isinstance(questions, list):
        return ["quiz_questions.json must be a JSON array"]

    seen_ids: set[str] = set()
    for raw in questions:
        if not isinstance(raw, dict):
            problems.append(f"question entry is not an object: {raw!r}")
            continue
        qid = raw.get("id")
        if not isinstance(qid, str) or not qid:
            problems.append(f"question entry lacks a string id: {raw!r}")
            continue
        if qid in seen_ids:
            problems.append(f"duplicate question id '{qid}'")
        seen_ids.add(qid)

        sub_ref = raw.get("subfield_id")
        if sub_ref not in subfield_ids:
            problems.append(f"question '{qid}' references unknown subfield '{sub_ref}'")
        concept_ref = raw.get("concept_id")
        if concept_ref not in concept_ids:
            problems.append(f"question '{qid}' references unknown concept '{concept_ref}'")

        options = raw.get("options")
        if (
            not isinstance(options, list)
            or len(options) != 4
            or not all(isinstance(o, str) and o for o in options)
        ):
            problems.append(f"question '{qid}' must have exactly 4 non-empty string options")

        correct = raw.get("correct_index")
        if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct <= 3:
            problems.append(f"question '{qid}' has invalid correct_index {correct!r} (need 0-3)")

        difficulty = raw.get("difficulty")
        if (
            not isinstance(difficulty, int)
            or isinstance(difficulty, bool)
            or not 1 <= difficulty <= 3
        ):
            problems.append(f"question '{qid}' has invalid difficulty {difficulty!r} (need 1-3)")

        if not isinstance(raw.get("stem"), str) or not raw.get("stem"):
            problems.append(f"question '{qid}' lacks a stem")
        # 'verified' may only ever move to true by the owner's hand (M-08); the
        # seeder merely requires the field to be a bool so serve-time filtering
        # in quiz_service sees a well-defined flag.
        if not isinstance(raw.get("verified", False), bool):
            problems.append(f"question '{qid}' has non-boolean 'verified'")

    return problems


def seed_quiz_questions(db: Session) -> None:
    """Upsert quiz questions from ``app/data/quiz_questions.json``.

    Every question is stored with its owner-controlled ``verified`` flag;
    whether unverified rows are *served* is decided at request time by
    ``ALLOW_UNVERIFIED_QUESTIONS`` (quiz_service) so the flag can be flipped
    without reseeding (deviation from plan 3.1 recorded in ARCHITECTURE.md).

    Args:
        db: an open session; commits at the end.

    Raises:
        SeedDataError: when the file is invalid or references unknown ids.

    Safe to run repeatedly: rows are merged by primary key, so replacing a
    placeholder with verified content and restarting updates it in place
    (AGENTS.md 3.3.9).
    """
    taxonomy = load_reference_json("taxonomy.json")
    questions = load_reference_json("quiz_questions.json")
    taxonomy_payload = cast("dict[str, Any]", taxonomy)
    subfield_ids = {s["id"] for s in taxonomy_payload["subfields"] if isinstance(s, dict)}
    concept_ids = {c["id"] for c in taxonomy_payload["concepts"] if isinstance(c, dict)}

    problems = validate_quiz_questions(questions, subfield_ids, concept_ids)
    if problems:
        raise SeedDataError("Invalid quiz questions: " + "; ".join(problems))

    json_ids = {raw["id"] for raw in questions}

    # Prune questions whose id is no longer in the JSON (e.g. placeholder rows
    # replaced by real content). Without this, stale rows would survive from an
    # existing dev database and could be served alongside the new bank.
    result = db.execute(Question.__table__.delete().where(~Question.id.in_(list(json_ids))))
    pruned = int(result.rowcount)

    rows: list[Question] = []
    for sort_order, raw in enumerate(questions):
        # list(questions) order is stable, so sort_order is the serve order.
        rows.append(
            Question(
                id=raw["id"],
                subfield_id=raw["subfield_id"],
                concept_id=raw["concept_id"],
                difficulty=raw["difficulty"],
                stem=raw["stem"],
                options=raw["options"],
                correct_index=raw["correct_index"],
                explanation=raw.get("explanation", ""),
                source_refs=raw.get("source_refs", []),
                verified=bool(raw.get("verified", False)),
                sort_order=raw.get("sort_order", sort_order),
            )
        )
    for row in rows:
        db.merge(row)
    db.commit()
    logger.info("quiz questions seeded: %d rows (pruned %d stale)", len(rows), pruned)


def seed_reference_data(db: Session) -> None:
    """Upsert taxonomy, career paths and skills from ``app/data/*.json``.

    Args:
        db: an open session; commits once at the end.

    Raises:
        SeedDataError: when any file is missing/unparseable or validation finds
            problems. Nothing is written in that case (validation runs first).

    Safe to run repeatedly: rows are merged by primary key, so re-seeding updates
    in place and never duplicates (AGENTS.md 3.3.9).
    """
    taxonomy = load_reference_json("taxonomy.json")
    career_paths = load_reference_json("career_paths.json")
    skills = load_reference_json("skills_vocab.json")

    problems = validate_reference_data(taxonomy, career_paths, skills)
    if problems:
        raise SeedDataError("Invalid reference data: " + "; ".join(problems))

    subfields: list[Subfield] = []
    concepts: list[Concept] = []
    paths: list[CareerPath] = []
    skill_rows: list[Skill] = []

    # Shapes are guaranteed by validate_reference_data (a mismatch would have
    # raised above); cast only narrows the types for the readers below.
    taxonomy_payload = cast("dict[str, Any]", taxonomy)
    for raw in taxonomy_payload["subfields"]:
        subfields.append(Subfield(**raw))
    for raw in taxonomy["concepts"]:
        concepts.append(Concept(**raw))
    for raw in career_paths:
        paths.append(CareerPath(**raw))
    for raw in skills:
        skill_rows.append(Skill(**raw))

    for row in subfields:
        db.merge(row)
    # Flush parent rows before children: the mappers have no relationship()
    # between them, so the unit of work would otherwise pick an arbitrary table
    # order and SQLite would reject the foreign keys.
    db.flush()
    for row in [*concepts, *paths, *skill_rows]:
        db.merge(row)
    db.commit()

    logger.info(
        "reference data seeded: %d subfields, %d concepts, %d career paths, %d skills",
        len(subfields),
        len(concepts),
        len(paths),
        len(skill_rows),
    )


def reference_data_counts(db: Session) -> dict[str, int]:
    """Return current row counts per reference table (used by tests and diagnostics)."""
    counts: dict[str, int] = {}
    for model in (Subfield, Concept, CareerPath, Skill, Question, Profile, Assessment):
        total = db.scalar(select(func.count()).select_from(model))
        counts[model.__tablename__] = int(total or 0)
    return counts
