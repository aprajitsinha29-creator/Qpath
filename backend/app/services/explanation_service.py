"""Grounded path explanations: batched Gemini call, evidence cache, template fallback.

Phase 4 step 4.4 (plan 4.4 + design decisions 1 and 2). Flow:

1. :func:`build_evidence` turns one ranked :class:`PathResult` into the
   grounded JSON the model may cite — display-ready numbers only (every value
   the UI shows, so anything the model copies is visible on screen).
2. :func:`evidence_hash` is the sha256 of that JSON (sorted keys): the cache
   key per (profile, assessment, path) in ``path_explanations``.
3. :func:`ensure_explanations` returns cached rows whose hash still matches;
   for everything missing it makes **ONE** Gemini call for all six paths
   (design decision 1 — the quota is tiny), validates each item against the
   plan 4.7 word rules **and** :func:`validate_numbers` (design decision 2: a
   number not present in the evidence JSON rejects that item), and builds the
   deterministic :func:`build_template` from the same evidence for anything
   that failed — call-level failure, per-item failure, missing Gemini key or
   :class:`GeminiDailyQuotaExhausted` (no retry — templates at once). The UI
   is NEVER failed because of Gemini (design decision 1/4).

Every outcome — llm or template — is persisted, so the next request is a
cache hit and a transient Gemini outage only downgrades until the evidence
changes (a new assessment or refreshed posting counts produce a new hash).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import GeminiDailyQuotaExhausted, LLMOutputError
from app.integrations.gemini.client import StructuredLLM
from app.integrations.gemini.prompts import PATH_EXPLANATIONS_PROMPT
from app.integrations.gemini.schemas import PathExplanationItem, PathExplanationsBatch
from app.models import PathExplanation
from app.schemas.paths import PathExplanationOut, PathResult
from app.services.scoring_service import LOW_DATA_THRESHOLD

logger = logging.getLogger(__name__)

# Plan 4.7 output contract (word budgets enforced per item in validate_explanation).
HEADLINE_MAX_WORDS = 12
REASON_COUNT = 3
REASON_MAX_WORDS = 25
CAVEAT_MAX_WORDS = 30
NEXT_STEP_MAX_WORDS = 25

#: Number tokens in explanations: integers, decimals, optional leading minus.
#: Deliberately simple — the allowed set comes from the evidence JSON, so
#: false negatives (e.g. "1,024") can only fall back to the template, never
#: leak an ungrounded number into the UI (design decision 2).
NUMBER_RE = r"-?\d+(?:\.\d+)?"


def build_evidence(result: PathResult, total_paths: int) -> dict[str, Any]:
    """Build the grounded JSON input for one path (plan 4.4.1).

    Only numbers and items derived from the ranked result — no external
    facts. Percent renderings are duplicated (e.g. ``share`` and
    ``share_pct``) so the model can cite the same value in whichever form the
    UI shows and still pass the numbers validator.

    Args:
        result: one ranked path (rank/score/breakdown/evidence already final).
        total_paths: how many paths were ranked (the model may say "six").

    Returns:
        A JSON-serializable dict; hashing it gives the cache key.
    """
    evidence = result.evidence
    return {
        "path_id": result.path_id,
        "title": result.title,
        "subfield_id": result.subfield_id,
        "total_paths": total_paths,
        "rank": result.rank,
        "score": result.score,
        "breakdown": {
            "interest_pct": result.breakdown.interest,
            "demand_pct": result.breakdown.demand,
            "readiness_pct": result.breakdown.readiness,
            "weights_pct": dict(result.breakdown.weights),
        },
        "low_data": result.low_data,
        "low_data_threshold": LOW_DATA_THRESHOLD,
        "saturated": result.saturated,
        "active_postings": evidence.active_postings,
        "internship_postings": evidence.internship_postings,
        "phd_share": round(evidence.phd_share, 3) if evidence.phd_share is not None else None,
        "phd_share_pct": evidence.phd_share_pct,
        "top_skills": [
            {"name": skill.name, "share_pct": skill.share_pct} for skill in evidence.top_skills
        ],
        "sample_postings": [
            {"title": p.title, "company": p.company, "location": p.location}
            for p in evidence.sample_postings
        ],
    }


def _canonical_json(value: object) -> str:
    """Return the deterministic JSON used for hashing and number extraction."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence_hash(evidence: dict[str, Any]) -> str:
    """Return the sha256 hex of the canonical evidence JSON (cache key part).

    Args:
        evidence: the dict from :func:`build_evidence`.

    Returns:
        64-char hex digest; changes whenever any cited value changes.
    """
    return hashlib.sha256(_canonical_json(evidence).encode("utf-8")).hexdigest()


def _numbers_in(text: str) -> set[float]:
    """Extract every numeric token from ``text`` as floats (0.0-equal compare)."""
    return {float(token) for token in re.findall(NUMBER_RE, text)}


def validate_numbers(fields: Sequence[str], evidence: dict[str, Any]) -> bool:
    """Return True when every number in ``fields`` exists in the evidence JSON.

    Design decision 2: explanations may only cite numbers present in the
    evidence passed to the model — anything else is ungrounded and the item
    falls back to its deterministic template.

    Args:
        fields: the text pieces of one explanation (headline, reasons, caveat,
            next_step).
        evidence: the grounded dict this item was generated from.

    Returns:
        True if the explanation cites no unknown number.
    """
    allowed = _numbers_in(_canonical_json(evidence))
    cited: set[float] = set()
    for field in fields:
        cited |= _numbers_in(field)
    return cited <= allowed


def validate_explanation(
    item: PathExplanationItem | None, evidence: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    """Validate one model item against the plan 4.7 contract (domain checks).

    Args:
        item: the item returned for this path (may be missing entirely).
        evidence: the grounded dict the item was generated from.

    Returns:
        ``(payload, "ok")`` when valid, where payload is the stored
        ``{headline, reasons, caveat, next_step}`` dict; else
        ``(None, "<reason>")`` so the caller can log why it templated.
    """
    if item is None:
        return None, "missing from the model response"
    if item.path_id != evidence["path_id"]:
        return None, f"path_id mismatch: {item.path_id!r}"
    if not item.headline.strip() or not item.caveat.strip() or not item.next_step.strip():
        return None, "empty headline/caveat/next_step"
    if len(item.reasons) != REASON_COUNT:
        return None, f"expected exactly {REASON_COUNT} reasons, got {len(item.reasons)}"
    if any(not reason.strip() for reason in item.reasons):
        return None, "empty reason"
    budgets = (
        (item.headline, HEADLINE_MAX_WORDS, "headline"),
        (item.caveat, CAVEAT_MAX_WORDS, "caveat"),
        (item.next_step, NEXT_STEP_MAX_WORDS, "next_step"),
        *(
            (reason, REASON_MAX_WORDS, f"reason {index + 1}")
            for index, reason in enumerate(item.reasons)
        ),
    )
    for text, limit, name in budgets:
        if len(text.split()) > limit:
            return None, f"{name} exceeds {limit} words"
    fields = [item.headline, *item.reasons, item.caveat, item.next_step]
    if not validate_numbers(fields, evidence):
        return None, "cites a number not present in the evidence"
    return (
        {
            "headline": item.headline.strip(),
            "reasons": [reason.strip() for reason in item.reasons],
            "caveat": item.caveat.strip(),
            "next_step": item.next_step.strip(),
        },
        "ok",
    )


def build_template(evidence: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic fallback explanation from the same evidence.

    Plan 4.4.4 / design decision 1: the UI must never break. Every number
    used here is read from ``evidence`` itself, so the template passes
    :func:`validate_numbers` by construction (asserted by a unit test).

    Args:
        evidence: the grounded dict from :func:`build_evidence`.

    Returns:
        The payload dict in the plan 4.7 shape.
    """
    breakdown = evidence["breakdown"]
    rank = evidence["rank"]
    total = evidence["total_paths"]
    active = evidence["active_postings"]

    if evidence["low_data"]:
        demand_reason = (
            f"Only {active} active postings ({breakdown['demand_pct']}% normalized demand) — "
            "demand evidence is thin."
        )
    else:
        demand_reason = (
            f"{active} active postings back this path "
            f"({breakdown['demand_pct']}% normalized demand)."
        )

    if evidence["low_data"]:
        caveat = (
            f"Fewer than {evidence['low_data_threshold']} active postings for this subfield — "
            "treat the demand signal as indicative."
        )
    elif evidence["saturated"]:
        caveat = (
            "The latest refresh hit the search page cap, so demand differences "
            "between subfields are compressed by sampling."
        )
    else:
        caveat = (
            "Counts are a sample of live postings, not a census; scores use only "
            "your diagnostic and the data shown."
        )

    return {
        "headline": f"Rank {rank} of {total}: {evidence['title']}",
        "reasons": [
            f"Your interest is {breakdown['interest_pct']}% from the diagnostic.",
            f"Your readiness for this subfield is {breakdown['readiness_pct']}%.",
            demand_reason,
        ],
        "caveat": caveat,
        "next_step": "Compare this path's evidence with your top-ranked paths before deciding.",
    }


def _cached_rows(
    db: Session, profile_id: str, assessment_id: int, evidence: dict[str, dict[str, Any]]
) -> dict[str, PathExplanation]:
    """Load cache rows whose evidence hash still matches the current evidence.

    Args:
        db: request session.
        profile_id: owning profile.
        assessment_id: the assessment the explanations belong to.
        evidence: path_id -> current grounded evidence.

    Returns:
        path_id -> fresh :class:`PathExplanation` row (stale-hash rows are
        ignored and later replaced on regeneration).
    """
    rows = db.scalars(
        select(PathExplanation).where(
            PathExplanation.profile_id == profile_id,
            PathExplanation.assessment_id == assessment_id,
            PathExplanation.path_id.in_(list(evidence)),
        )
    )
    fresh: dict[str, PathExplanation] = {}
    for row in rows:
        current = evidence.get(row.path_id)
        if current is not None and row.evidence_hash == evidence_hash(current):
            fresh[row.path_id] = row
    return fresh


def _to_out(row: PathExplanation) -> PathExplanationOut:
    """Project a cache row onto the API schema (payload + provenance)."""
    return PathExplanationOut.model_validate(
        {
            **row.payload,
            "generated_by": row.generated_by,
            "model": row.model,
            "generated_at": row.generated_at,
        }
    )


def _persist(
    db: Session,
    profile_id: str,
    assessment_id: int,
    hashes: dict[str, str],
    generated: dict[str, tuple[dict[str, Any], str]],
) -> dict[str, PathExplanation]:
    """Replace stale rows and insert the newly generated payloads (idempotent).

    Args:
        db: request session (committed by this function).
        profile_id / assessment_id: cache scope.
        hashes: path_id -> current evidence hash.
        generated: path_id -> (payload, generated_by).

    Returns:
        path_id -> the row now holding that path's explanation.
    """
    existing = list(
        db.scalars(
            select(PathExplanation).where(
                PathExplanation.profile_id == profile_id,
                PathExplanation.assessment_id == assessment_id,
                PathExplanation.path_id.in_(list(generated)),
            )
        )
    )
    for row in existing:
        # Same scope but a different evidence hash: superseded, drop it so the
        # cache holds exactly one row per (profile, assessment, path).
        if hashes.get(row.path_id) != row.evidence_hash:
            db.delete(row)

    model_name = get_settings().gemini_model or None
    rows: dict[str, PathExplanation] = {}
    for path_id, (payload, generated_by) in generated.items():
        row = PathExplanation(
            profile_id=profile_id,
            assessment_id=assessment_id,
            path_id=path_id,
            evidence_hash=hashes[path_id],
            payload=payload,
            generated_by=generated_by,
            model=model_name if generated_by == "llm" else None,
        )
        db.add(row)
        rows[path_id] = row
    db.commit()
    return rows


def cached_explanations(
    db: Session,
    profile_id: str,
    assessment_id: int,
    results: Sequence[PathResult],
) -> dict[str, PathExplanationOut]:
    """Return the fresh cached explanations for the ranked paths (no LLM).

    Args:
        db: request session.
        profile_id: owning profile.
        assessment_id: latest assessment id.
        results: the ranked paths (``explanation`` not yet filled).

    Returns:
        path_id -> explanation for paths whose cache row matches the current
        evidence hash; uncached paths are simply absent (the caller leaves
        ``explanation`` null until POST generates them).
    """
    evidence = {r.path_id: build_evidence(r, len(results)) for r in results}
    rows = _cached_rows(db, profile_id, assessment_id, evidence)
    return {path_id: _to_out(row) for path_id, row in rows.items()}


def ensure_explanations(
    db: Session,
    profile_id: str,
    assessment_id: int,
    results: Sequence[PathResult],
    llm: StructuredLLM | None,
) -> dict[str, PathExplanationOut]:
    """Return explanations for ALL paths, generating the missing ones in ONE call.

    Args:
        db: request session (committed when something new was generated).
        profile_id: owning profile.
        assessment_id: latest assessment id (cache scope).
        results: the ranked paths (``explanation`` not yet filled).
        llm: the Gemini-backed client, or None when unconfigured — None goes
            straight to templates (design decision 4).

    Returns:
        path_id -> explanation for every path in ``results``. Never raises
        because of Gemini: call failure, item failure, quota exhaustion
        (GeminiDailyQuotaExhausted — no retry) and a missing key all produce
        ``generated_by="template"`` rows instead (design decision 1).
    """
    evidence = {r.path_id: build_evidence(r, len(results)) for r in results}
    hashes = {path_id: evidence_hash(ev) for path_id, ev in evidence.items()}
    fresh = _cached_rows(db, profile_id, assessment_id, evidence)

    missing = [r.path_id for r in results if r.path_id not in fresh]
    if missing:
        generated = _generate(evidence, missing, llm)
        fresh.update(_persist(db, profile_id, assessment_id, hashes, generated))
    return {path_id: _to_out(row) for path_id, row in fresh.items()}


def _generate(
    evidence: dict[str, dict[str, Any]],
    missing: list[str],
    llm: StructuredLLM | None,
) -> dict[str, tuple[dict[str, Any], str]]:
    """Generate payloads for ``missing`` paths: one LLM call, template fallbacks.

    Args:
        evidence: path_id -> grounded evidence for every path.
        missing: path_ids needing a fresh explanation.
        llm: Gemini client or None (unconfigured → templates, design decision 4).

    Returns:
        path_id -> (payload, "llm" | "template"). Never raises: call failure,
        per-item validation failure, quota exhaustion (no retry) and a missing
        key all degrade to templates (design decision 1).
    """
    if llm is None:
        logger.info("gemini not configured — building template explanations")
        return {path_id: (build_template(evidence[path_id]), "template") for path_id in missing}

    prompt = PATH_EXPLANATIONS_PROMPT.format(
        paths=_canonical_json([evidence[path_id] for path_id in missing])
    )
    try:
        batch = llm.generate_structured(prompt, PathExplanationsBatch)
    except GeminiDailyQuotaExhausted as exc:
        # Design decision 1: quota exhausted -> do not retry, templates at once.
        logger.warning("gemini quota exhausted, using templates: %s", exc.message)
        return {path_id: (build_template(evidence[path_id]), "template") for path_id in missing}
    except LLMOutputError as exc:
        logger.warning("explanation call failed, using templates: %s", exc.message)
        return {path_id: (build_template(evidence[path_id]), "template") for path_id in missing}
    except Exception:
        # Design decision 1: the UI never sees an explanation error. Log the
        # full traceback (not swallowed silently — AGENTS 3.3.5) and degrade.
        logger.exception("unexpected explanation failure; using templates")
        return {path_id: (build_template(evidence[path_id]), "template") for path_id in missing}

    items = {item.path_id: item for item in batch.explanations}
    generated: dict[str, tuple[dict[str, Any], str]] = {}
    for path_id in missing:
        payload, reason = validate_explanation(items.get(path_id), evidence[path_id])
        if payload is None:
            logger.warning(
                "explanation for %s failed validation (%s) — templating", path_id, reason
            )
            generated[path_id] = (build_template(evidence[path_id]), "template")
        else:
            generated[path_id] = (payload, "llm")
    return generated
