"""Skills service: read the vocabulary and manage declared skills (carry-over).

Cut from Phase 4 and implemented per the task spec. Sits between the
skills/profiles routers and the models layer (AGENTS.md 3.3.1). The
declared-skills PUT is *additive to the profile only*: it must not affect
scoring, ranking or any other profile field — the paths math never reads
``declared_skills`` (test_declared_skills_do_not_change_ranked_paths
locks that in).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidSkillsError
from app.models import Profile, Skill
from app.schemas.skills import SkillOut
from app.services import quiz_service

logger = logging.getLogger(__name__)


def list_skills(db: Session) -> list[SkillOut]:
    """Return the whole vocabulary sorted by name (plan contract for the picker).

    Args:
        db: request session.

    Returns:
        Every seeded skill as :class:`SkillOut`, ordered by name (ties broken
        by id for total determinism).
    """
    rows = db.scalars(select(Skill).order_by(Skill.name, Skill.id))
    return [SkillOut.model_validate(row) for row in rows]


def _validate_skills(db: Session, skill_ids: list[str]) -> list[str]:
    """Dedupe keeping first-seen order and check every id against the vocabulary.

    Args:
        db: request session.
        skill_ids: ids exactly as the client sent them (may contain dupes).

    Returns:
        The deduplicated, order-preserving list.

    Raises:
        InvalidSkillsError: (422 ``invalid_skills``) with the offending ids in
            the message when any id is not in the seeded ``skills`` table.
            Nothing is written in that case — validation completes before the
            profile mutation begins (atomicity).
    """
    # First-seen order preserved; duplicates collapse to one entry.
    seen: set[str] = set()
    ordered: list[str] = []
    for skill_id in skill_ids:
        if skill_id not in seen:
            seen.add(skill_id)
            ordered.append(skill_id)

    known = set(db.scalars(select(Skill.id)))
    unknown = sorted(set(ordered) - known)
    if unknown:
        raise InvalidSkillsError(f"unknown skill id(s): {', '.join(unknown)}")
    return ordered


def replace_declared_skills(db: Session, profile_id: str, skill_ids: list[str]) -> Profile:
    """Replace the profile's whole ``declared_skills`` list (plan Phase 4 cut item).

    Atomicity: validation runs *before* any attribute is touched, and only
    ``declared_skills`` is assigned — ``interests``, ``last_seen_at``,
    ``chosen_path_id``, ``completed_concepts`` and the assessment history are
    never modified here.

    Args:
        db: request session.
        profile_id: UUID path parameter.
        skill_ids: full replacement list (raw, possibly duplicated); an empty
            list is valid and clears the list.

    Returns:
        The updated ORM :class:`Profile` (router projects to a schema).

    Raises:
        NotFoundError: unknown profile (404) — reused from quiz_service.
        InvalidSkillsError: unknown skill id (422), nothing written.
    """
    profile: Profile = quiz_service.get_profile(db, profile_id)  # 404 gate first
    validated = _validate_skills(db, skill_ids)
    profile.declared_skills = validated
    db.commit()
    logger.info("declared skills replaced: profile=%s count=%d", profile.id, len(validated))
    return profile
