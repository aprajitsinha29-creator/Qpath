"""Skill-extraction service: vocabulary-constrained Gemini extraction over postings.

Phase 2 step 2.4 (plan 4.7). Selects postings whose ``extraction_status`` is
``pending``/``failed`` (and ``extraction_attempts < MAX``), batches them 5 at a
time, renders the extraction prompt, calls the injected
:class:`StructuredLLM` (real Gemini in production, FakeStructuredLLM in tests),
post-validates, and persists the results.

Two validation layers, per plan:
- **Schema validation** happens inside the LLM client (one retry there →
  ``LLMOutputError``). This service receives only schema-valid objects.
- **Domain post-validation** happens here: unknown skill ids are dropped to
  ``unmapped_skills``, an invalid ``primary_subfield_id`` becomes None, and a
  count/``posting_ref`` mismatch invalidates the whole batch → one retry →
  every posting in the batch is marked ``failed`` with ``attempts + 1``
  (postings are dropped from the pool after MAX_EXTRACTION_ATTEMPTS).

Idempotency (AGENTS 3.3.9): ``done`` postings are never re-selected, skill rows
are replaced (delete-then-insert) per posting, so a partial run followed by a
re-run cannot duplicate anything. ``is_internship`` and the other flags are
re-derived from posting text via ``app.services.flag_rules`` — no model claim
reaches the DB unverified (M-10 fix; see the docstring of ``_persist_item``).

The LLM never decides a number or rank here — it only labels postings, and every
label that reaches the DB is vocabulary- or taxonomy-checked (AGENTS 3.3.10).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.gemini.client import StructuredLLM
from app.integrations.gemini.prompts import SKILL_EXTRACTION_PROMPT
from app.integrations.gemini.schemas import ExtractionBatch, PostingExtraction
from app.models import JobPosting, JobPostingSkill, Skill, Subfield
from app.services.flag_rules import (
    derive_is_internship,
    derive_requires_phd,
    derive_seniority,
)

logger = logging.getLogger(__name__)

#: Postings per LLM call (plan 3.5.5 / 4.7: batch of ≤ 5).
EXTRACTION_BATCH_SIZE = 5

#: Descriptions are truncated to ~3,000 chars before entering the prompt
#: (plan 4.7) — bounds token usage without losing the skills section, which
#: appears early in real postings.
DESCRIPTION_TRUNCATE_CHARS = 3000

#: A posting is dropped from extraction after this many failed batch runs
#: (plan 4.7: "attempts + 1; stop after 3 attempts").
MAX_EXTRACTION_ATTEMPTS = 3

#: DB extraction_status values (plan 4.3).
STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


def select_pending_postings(db: Session, limit: int | None = None) -> list[JobPosting]:
    """Return postings eligible for extraction, oldest id first.

    Args:
        db: request/session-scoped session.
        limit: optional cap on how many postings to return.

    Returns:
        Postings with ``extraction_status`` pending/failed and fewer than
        :data:`MAX_EXTRACTION_ATTEMPTS` attempts. Postings at the attempt cap
        are permanently excluded (their content likely breaks extraction).
    """
    statement = (
        select(JobPosting)
        .where(
            JobPosting.extraction_status.in_((STATUS_PENDING, STATUS_FAILED)),
            JobPosting.extraction_attempts < MAX_EXTRACTION_ATTEMPTS,
        )
        .order_by(JobPosting.id.asc())
    )
    if limit is not None:
        statement = statement.limit(max(0, limit))
    return list(db.scalars(statement))


def _render_vocabulary(skills: Sequence[Skill]) -> str:
    """Render ``skills_vocab`` rows as ``id: name (aliases)`` prompt lines."""
    lines = []
    for skill in skills:
        aliases = ", ".join(skill.aliases or [])
        suffix = f" ({aliases})" if aliases else ""
        lines.append(f"- {skill.id}: {skill.name}{suffix}")
    return "\n".join(lines) or "(empty)"


def _render_subfields(subfields: Sequence[Subfield]) -> str:
    """Render subfield rows as ``id: name`` prompt lines (the allowed id set)."""
    return "\n".join(f"- {s.id}: {s.name}" for s in subfields) or "(empty)"


def _render_postings(postings: Sequence[JobPosting]) -> str:
    """Render one prompt block per posting; descriptions truncated (plan 4.7)."""
    blocks = []
    for posting in postings:
        description = (posting.description or "")[:DESCRIPTION_TRUNCATE_CHARS]
        blocks.append(
            f"posting_ref: {posting.id}\ntitle: {posting.title}\n"
            f"company: {posting.company}\ndescription: {description}"
        )
    return "\n---\n".join(blocks)


def build_extraction_prompt(
    postings: Sequence[JobPosting], skills: Sequence[Skill], subfields: Sequence[Subfield]
) -> str:
    """Render the full skill-extraction prompt (plan 4.7 template).

    Args:
        postings: the batch (one output item per posting, same order).
        skills: the full vocabulary — the only ids the model may emit.
        subfields: the valid ``primary_subfield_id`` values.

    Returns:
        The prompt string for :meth:`StructuredLLM.generate_structured`.
    """
    return SKILL_EXTRACTION_PROMPT.format(
        vocabulary=_render_vocabulary(skills),
        subfields=_render_subfields(subfields),
        postings=_render_postings(postings),
    )


def _post_validate_batch(
    batch: ExtractionBatch,
    *,
    expected_refs: list[str],
    valid_skill_ids: set[str],
    valid_subfield_ids: set[str],
) -> list[PostingExtraction] | None:
    """Apply the plan 4.7 post-validation rules to one batch response.

    Args:
        batch: the (schema-valid) model output.
        expected_refs: posting ids that were sent, in order.
        valid_skill_ids: vocabulary ids that may be persisted.
        valid_subfield_ids: subfield ids that may be stored as primary.

    Returns:
        Corrected items in input order, or None when the batch is structurally
        invalid (item count / posting_ref mismatch) and must be retried.

    Correction rules (never trusted silently — AGENTS 3.5.3):
        unknown skill ids are moved to ``unmapped_skills``; an invalid
        ``primary_subfield_id`` becomes None; duplicate skill ids are dropped;
        seniority/PhD/internship flags are re-derived from text evidence by
        :mod:`app.services.flag_rules` (M-10 spot-check fix)
    """
    items = batch.items
    if len(items) != len(expected_refs):
        logger.warning(
            "extraction batch invalid: %d items for %d postings", len(items), len(expected_refs)
        )
        return None
    if [item.posting_ref for item in items] != expected_refs:
        logger.warning("extraction batch invalid: posting_ref order mismatch")
        return None

    corrected: list[PostingExtraction] = []
    for item in items:
        known = [sid for sid in item.skill_ids if sid in valid_skill_ids]
        unknown = [sid for sid in item.skill_ids if sid not in valid_skill_ids]
        if unknown:
            logger.info(
                "dropping %d unknown skill ids to unmapped for posting %s",
                len(unknown),
                item.posting_ref,
            )
        # Deduplicate while preserving order: the model may repeat an id.
        deduped = list(dict.fromkeys(known))
        unmapped = list(dict.fromkeys([*item.unmapped_skills, *unknown]))
        primary = (
            item.primary_subfield_id if item.primary_subfield_id in valid_subfield_ids else None
        )
        corrected.append(
            PostingExtraction(
                posting_ref=item.posting_ref,
                skill_ids=deduped,
                unmapped_skills=unmapped,
                seniority=item.seniority,
                requires_phd=item.requires_phd,
                is_internship=item.is_internship,
                primary_subfield_id=primary,
            )
        )
    return corrected


def _persist_item(db: Session, posting: JobPosting, item: PostingExtraction) -> None:
    """Write one validated extraction onto the posting row (delete-then-insert).

    Args:
        db: the run's session.
        posting: the posting being updated.
        item: the post-validated extraction for ``posting``.

    Notes:
        - ``seniority`` is evidence-gated by :func:`derive_seniority`: a claim
          without a matching keyword becomes NULL, an internship is always
          ``intern``. "Not stated" and "no evidence" are both stored as NULL
          (plan 4.3: "unknown" stays distinguishable from a negative).
        - ``requires_phd`` comes from text rules, so "preferred" wording is
          stored as NULL rather than guessed either way.
        - ``is_internship`` is rule-based from title+extensions (the model's
          flag is ignored); a non-intern title is never flagged internship.
        - ``primary_subfield_id`` is NOT used to create links here: subfield
          links come from the discovery queries (ingestion), and re-linking on
          model output would silently change demand counts. The field is
          persisted in a later phase's matching logic; extracting and
          validating it now keeps the batch contract per plan 4.7.
    """
    # Flag persistence is EVIDENCE-GATED, never taken from the model verbatim
    # (M-10 spot-check: model claims were wrong in 15/20 sampled postings;
    # AGENTS 3.3.10 — the LLM never decides a fact shown in the UI):
    # - seniority survives only when the claimed bucket's keyword appears in
    #   the title or the first 3000 description chars;
    # - requires_phd is re-derived from text (True/false/null rules in
    #   flag_rules.derive_requires_phd);
    # - is_internship is rule-based from title+extensions ONLY; an internship
    #   also forces seniority="intern" (consistency rule), and a non-intern
    #   title can never become an internship — the old model-OR behaviour is
    #   gone because the model could flag regular jobs as internships.
    internship = derive_is_internship(posting.title, posting.extensions)
    if internship:
        posting.seniority = "intern"
    else:
        posting.seniority = derive_seniority(posting.title, posting.description, item.seniority)
    posting.requires_phd = derive_requires_phd(posting.title, posting.description)
    posting.is_internship = internship
    posting.extraction_status = STATUS_DONE

    # Replace, never append: re-extraction (e.g. after a manual status reset)
    # must not leave stale skill rows behind (AGENTS 3.3.9). The flush forces
    # the DELETEs before the new INSERTs — SQLAlchemy otherwise emits inserts
    # first and the unique constraint would reject a re-extracted posting.
    for existing in list(
        db.scalars(select(JobPostingSkill).where(JobPostingSkill.posting_id == posting.id))
    ):
        db.delete(existing)
    db.flush()
    for skill_id in item.skill_ids:
        db.add(JobPostingSkill(posting_id=posting.id, skill_id=skill_id))


def run_extraction(
    db: Session,
    llm: StructuredLLM,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Run vocabulary-constrained extraction over pending postings.

    Args:
        db: session for the whole run.
        llm: injected :class:`StructuredLLM` (real client in production).
        limit: optional cap on postings processed this run; remaining
            candidates are reported as ``skipped``.

    Returns:
        ``{"done": n, "failed": n, "skipped": n}`` — postings marked done,
        postings marked failed this run, and eligible postings not attempted
        (only when ``limit`` cuts the run short).

    Raises:
        LLMOutputError: never swallowed silently — a hard client failure marks
            the batch's postings ``failed`` (logged with context) and the run
            continues with the next batch (plan 1.3.3-style isolation).

    Side effects:
        Updates ``job_postings`` extraction columns, writes
        ``job_posting_skills`` rows, commits once per batch.
    """
    candidates = select_pending_postings(db, limit=None)
    total_candidates = len(candidates)
    batch_list = candidates[:limit] if limit is not None else candidates
    skipped = total_candidates - len(batch_list)

    valid_skill_ids = {row.id for row in db.scalars(select(Skill))}
    valid_subfield_ids = {row.id for row in db.scalars(select(Subfield))}
    # The vocabulary/taxonomy blocks are identical for every batch in the run.
    vocabulary_block = _render_vocabulary(list(db.scalars(select(Skill).order_by(Skill.id))))
    subfields_block = _render_subfields(
        list(db.scalars(select(Subfield).order_by(Subfield.sort_order)))
    )

    done = failed = 0
    for start in range(0, len(batch_list), EXTRACTION_BATCH_SIZE):
        batch = batch_list[start : start + EXTRACTION_BATCH_SIZE]
        expected_refs = [str(posting.id) for posting in batch]
        prompt = SKILL_EXTRACTION_PROMPT.format(
            vocabulary=vocabulary_block,
            subfields=subfields_block,
            postings=_render_postings(batch),
        )

        corrected = None
        # Initial attempt + one retry on structural invalidity (plan 4.7.2).
        for _attempt in range(2):
            try:
                raw = llm.generate_structured(prompt, ExtractionBatch)
            except Exception as exc:  # noqa: BLE001 - recorded, never fatal to the run
                logger.warning("extraction LLM call failed: %s (%s)", type(exc).__name__, exc)
                continue
            corrected = _post_validate_batch(
                raw,
                expected_refs=expected_refs,
                valid_skill_ids=valid_skill_ids,
                valid_subfield_ids=valid_subfield_ids,
            )
            if corrected is not None:
                break
            # Second pass re-uses the same prompt; the model gets a fresh chance.

        if corrected is None:
            # Both attempts unusable: mark failed, attempts + 1, keep going.
            for posting in batch:
                posting.extraction_status = STATUS_FAILED
                posting.extraction_attempts += 1
            failed += len(batch)
            db.commit()
            continue

        for posting, item in zip(batch, corrected, strict=True):
            _persist_item(db, posting, item)
        done += len(batch)
        db.commit()

    logger.info("extraction run: done=%d failed=%d skipped=%d", done, failed, skipped)
    return {"done": done, "failed": failed, "skipped": skipped}
