"""Match service: the pure posting-relevance function (plan Section 4.5).

Sits at the bottom of the Phase 5 flow: :mod:`tracker_service` calls it per
posting; it touches nothing — no DB, no HTTP. The formula and weights are the
plan's contract, so they live as named constants with a rationale.

Why these weights: skill overlap (60%) says "this posting wants what you
already have"; readiness (40%) says "you scored well in this subfield on the
diagnostic". Equal split would let a perfect readiness dominate matches for
listings the user shares no skills with, so overlap leads.
"""

from __future__ import annotations

from app.services.scoring_service import readiness_n

#: Overlap share weight in the match formula (plan 4.5).
W_OVERLAP = 0.6
#: Readiness weight in the match formula (plan 4.5).
W_READINESS = 0.4


def posting_match(
    posting_skill_ids: list[str] | None,
    declared_skill_ids: list[str],
    readiness_score: float | None,
) -> float | None:
    """Compute one posting's match score, or ``None`` when there is not enough data.

    Match is 100 × (0.6 × skill_overlap + 0.4 × readiness_n), where

    * ``skill_overlap = |posting_skills ∩ declared| / max(1, |posting_skills|)``
      (the ``max(1, ...)`` guard makes the empty-posting-skills case defined —
      but that case returns ``None`` anyway, see below).
    * ``readiness_n`` comes from the LATEST assessment for the posting's primary
      subfield when the data model stores a scored one, otherwise the tracked
      path's subfield (tracker_service resolves which; this function only
      consumes the resulting number).

    ``None`` means "not enough information" (a real UI state), deliberately
    distinct from 0.

    Args:
        posting_skill_ids: vocabulary ids extracted for the posting. ``None``,
            empty, or a posting whose extraction is incomplete must be passed
            as ``None`` by the caller (extraction status governs availability).
        declared_skill_ids: the profile's declared skills (may be empty).
        readiness_score: 0-100 readiness for the relevant subfield from the
            latest assessment, or ``None`` when never assessed (then the match
            is ``None``).

    Returns:
        0-100 match rounded to 1 decimal, or ``None``.
    """
    # No extracted skills -> no basis for overlap: "not enough information".
    # (A posting whose extraction failed/pending is handled by the caller.)
    if not posting_skill_ids:
        return None
    if readiness_score is None:
        return None
    # Nothing declared -> overlap is undefined, not zero: the 0.4×readiness
    # remainder would masquerade as a real match opinion the user never gave.
    if not declared_skill_ids:
        return None

    declared = set(declared_skill_ids)
    overlap = len(declared.intersection(posting_skill_ids)) / max(1, len(posting_skill_ids))
    match = 100 * (W_OVERLAP * overlap + W_READINESS * readiness_n(readiness_score))
    # 1 decimal keeps serialized scores stable across SQLite round-trips and
    # keeps the UI's tabular numbers honest ("57.5" not "57.500000001").
    return round(match, 1)
