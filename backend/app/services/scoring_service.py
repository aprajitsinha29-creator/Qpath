"""Pure scoring functions for the orientation diagnostic and path matcher
(plan 3.3 / 4.5).

NO database, NO HTTP, NO LLM — everything here is deterministic and unit-tested
(AGENTS.md 3.3.10: the LLM never decides a number). Constants live here.

Formula (BUILD_PLAN 4.5): a correct answer earns its ``difficulty`` (1-3) in
points; wrong, "Not sure" (null) and unanswered earn 0 — no negative marking.
``readiness_s = 100 * earned_s / available_s``; with difficulties 1,2,3 the
available total per subfield is 6.

Phase 4 adds the path-matcher half: normalizations (``interest_n``,
``readiness_n``, ``demand_n``), the weighted ``path_score`` and ``rank_paths``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionMeta:
    """The scoring-relevant projection of a question (no stem/options needed).

    Attributes:
        subfield_id: which scored subfield the question counts toward.
        difficulty: 1-3; doubles as the point value of a correct answer.
        correct_index: the index of the correct option.
        concept_id: taxonomy concept this question tests (feeds weak_concepts).
    """

    subfield_id: str
    difficulty: int
    correct_index: int
    concept_id: str


def normalize_selections(
    answers: list[tuple[str, int | None]], known_ids: set[str]
) -> dict[str, int | None]:
    """Validate raw answers and map them to ``question_id -> selected_index|null``.

    Args:
        answers: (question_id, selected_index-or-None) pairs as submitted.
        known_ids: the servable question ids; anything else is invalid.

    Returns:
        A dict keyed by question id. Missing questions are treated as
        unanswered (they simply do not appear — scoring gives them 0).

    Raises:
        ValueError: on an unknown question id or a duplicate answer; callers
            map this to HTTP 422.
    """
    selections: dict[str, int | None] = {}
    for question_id, selected in answers:
        if question_id not in known_ids:
            raise ValueError(f"unknown question id '{question_id}'")
        if question_id in selections:
            raise ValueError(f"duplicate answer for question '{question_id}'")
        # Keep the "Not sure" (None) marker distinct from a wrong choice: both
        # score 0, but weak_concepts lists both while "correct" differs.
        selections[question_id] = selected
    return selections


def readiness_scores(
    question_meta: dict[str, QuestionMeta], selections: dict[str, int | None]
) -> dict[str, float]:
    """Compute readiness (0-100) per subfield from the submitted selections.

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        selections: question_id -> selected index (int) or None ("Not sure").
            Questions absent from the dict count as unanswered (0 points).

    Returns:
        ``{subfield_id: readiness}`` for every subfield that has at least one
        question in ``question_meta`` (the caller guarantees the 6 scored
        subfields are covered by the >=3-per-subfield guard).

    Note:
        Division safety: ``available_s`` is 0 only if a subfield has no
        questions, which the quiz guard prevents; the guard clause below
        returns 0.0 defensively rather than crashing.
    """
    earned: dict[str, float] = {}
    available: dict[str, float] = {}
    for question_id, meta in question_meta.items():
        available[meta.subfield_id] = available.get(meta.subfield_id, 0) + meta.difficulty
        if selections.get(question_id) == meta.correct_index:
            # Correct: earn the difficulty as points (plan 4.5).
            earned[meta.subfield_id] = earned.get(meta.subfield_id, 0) + meta.difficulty
        # Wrong / None / unanswered: 0 points, no negative marking.
    return {
        subfield_id: 100.0 * earned.get(subfield_id, 0.0) / total if total else 0.0
        for subfield_id, total in available.items()
    }


def weak_concepts(
    question_meta: dict[str, QuestionMeta], selections: dict[str, int | None]
) -> list[str]:
    """Return concepts of wrong / "Not sure" answers, deduplicated, answer order.

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        selections: question_id -> selected index (int) or None ("Not sure").

    Returns:
        Concept ids in the order the failing answers were given (deterministic
        because ``selections`` is built from the submitted answer list order).
    """
    seen: set[str] = set()
    weak: list[str] = []
    for question_id, meta in question_meta.items():
        selected = selections.get(question_id)
        if selected != meta.correct_index and meta.concept_id not in seen:
            # Wrong OR "Not sure" OR unanswered all go here (plan 3.3).
            seen.add(meta.concept_id)
            weak.append(meta.concept_id)
    return weak


def per_question_feedback(
    question_meta: dict[str, QuestionMeta],
    explanations: dict[str, str],
    selections: dict[str, int | None],
) -> list[dict[str, object]]:
    """Build the post-submission feedback rows (question_id, correct, explanation).

    Args:
        question_meta: scoring metadata for every servable question, keyed by id.
        explanations: question_id -> owner-written explanation text.
        selections: question_id -> selected index (int) or None ("Not sure").

    Returns:
        A list of plain dicts (Pydantic serializes them) in servable-question
        order; ``correct`` is False for wrong, "Not sure" and unanswered.
    """
    return [
        {
            "question_id": question_id,
            "correct": selections.get(question_id) == meta.correct_index,
            "explanation": explanations.get(question_id, ""),
            "concept_id": meta.concept_id,
        }
        for question_id, meta in question_meta.items()
    ]


# ---------------------------------------------------------------------------
# Path matcher (plan 4.2 / BUILD_PLAN 4.5)
# ---------------------------------------------------------------------------

#: Path score weights (sum to 1.0). Rationale: interest leads (a beginner has
#: low readiness everywhere, so readiness must not dominate); demand keeps
#: recommendations grounded in the live market (the project's whole point);
#: readiness favors a realistic start. See BUILD_PLAN 4.5.
W_INTEREST = 0.40
W_DEMAND = 0.30
W_READINESS = 0.30

#: Weights as displayed percents, derived from the constants above so the UI,
#: the evidence JSON and the hand-checkable score can never drift apart.
WEIGHTS_PERCENT: dict[str, float] = {
    "interest": W_INTEREST * 100,
    "demand": W_DEMAND * 100,
    "readiness": W_READINESS * 100,
}

#: Below this many core-sourced active postings a path is flagged ``low_data``
#: and the UI must say demand evidence is thin (plan 1.4 / 4.5). Defined here
#: (not in pulse_service) because this is the constants module; pulse imports it.
LOW_DATA_THRESHOLD = 8

#: The saturation guard fires when at least this many subfields hit the search
#: page cap in the latest bootstrap (plan 4.5: "≥ 4 of 6 subfields").
SATURATION_MIN_SUBFIELDS = 4

#: Ranks 1..TOP_3 are highlighted on the results page (plan 4.3 "top 3").
TOP_3 = 3

#: Normalized components are rounded to this many digits BEFORE scoring, and
#: the score to this many digits after: the UI displays the rounded values, so
#: recomputing ``100 * (0.40*i + 0.30*d + 0.30*r)`` from the displayed numbers
#: reproduces the displayed score exactly (plan 4.8 acceptance check).
COMPONENT_DIGITS = 3
SCORE_DIGITS = 1


def interest_n(slider: int) -> float:
    """Normalize an interest slider (1-5) to 0-1 (plan 4.5: (slider-1)/4).

    Args:
        slider: raw slider value as submitted with the diagnostic.

    Returns:
        0 for slider 1, 0.5 for 3, 1 for 5. Values outside 1-5 are clamped:
        the API validates the six subfield keys but not the slider range, and
        a score >100 would be worse than a capped one (defensive clamp).
    """
    return min(1.0, max(0.0, (slider - 1) / 4))


def readiness_n(readiness_s: float) -> float:
    """Normalize a readiness score (0-100) to 0-1 (plan 4.5).

    Args:
        readiness_s: readiness for one subfield as stored on the assessment.

    Returns:
        ``readiness_s / 100`` clamped to 0-1.
    """
    return min(1.0, max(0.0, readiness_s / 100))


def demand_n(active: int, max_active: int) -> float:
    """Normalize a subfield's core active-posting count to 0-1 (plan 4.5).

    ``demand_n = ln(1 + active) / ln(1 + max_active)`` — a log scale stops one
    big subfield from flattening the rest of the field. ``active`` must count
    CORE-tier links only so subfields with more (or longer) queries get no
    artificial demand advantage (plan 4.6 fairness note).

    Args
        active: core-tier active postings for this subfield (selected region).
        max_active: the maximum across all scored subfields for the same region.

    Returns:
        0-1; 0.0 when ``max_active`` is 0 (no data anywhere — no division by
        zero, plan 4.7 "zero postings everywhere" case).
    """
    if max_active <= 0:
        return 0.0
    return math.log1p(active) / math.log1p(max_active)


def path_score(interest: float, demand: float, readiness: float) -> float:
    """Compute the 0-100 path score from normalized components (plan 4.5).

    ``score = 100 * (W_INTEREST*interest + W_DEMAND*demand + W_READINESS*readiness)``.

    The weights (module constants, rationale in their comment) are part of the
    deterministic contract: the LLM never touches them (AGENTS 3.3.10).

    Args:
        interest: normalized interest 0-1.
        demand: normalized demand 0-1.
        readiness: normalized readiness 0-1.

    Returns:
        Score 0-100 for components within 0-1.
    """
    return 100.0 * (W_INTEREST * interest + W_DEMAND * demand + W_READINESS * readiness)


def saturation_note(capped_subfields: set[str], total_paths: int) -> str | None:
    """Return the sampling-saturation note when the guard fires (plan 4.5).

    Args:
        capped_subfields: subfields whose CORE query hit the page cap in the
            latest bootstrap refresh (see paths_service).
        total_paths: number of scored paths (6 for the standard taxonomy).

    Returns:
        A human-readable note when >= SATURATION_MIN_SUBFIELDS subfields hit
        the cap (demand differences are compressed by sampling), else None.
    """
    if len(capped_subfields) < SATURATION_MIN_SUBFIELDS:
        return None
    return (
        f"{len(capped_subfields)} of {total_paths} subfields hit the search page cap "
        "in the latest bootstrap refresh, so demand differences are compressed "
        "by sampling."
    )


@dataclass(frozen=True)
class PathCandidate:
    """Raw inputs for one path before scoring.

    Attributes:
        path_id: career path id (stable slug, e.g. ``qec_engineer``).
        subfield_id: the scored subfield the path maps 1:1 onto.
        interest: normalized interest 0-1 (from ``interest_n``).
        readiness: normalized readiness 0-1 (from ``readiness_n``).
        demand: normalized demand 0-1 (from ``demand_n``).
        active_postings: core active postings behind ``demand`` (drives low_data).
    """

    path_id: str
    subfield_id: str
    interest: float
    readiness: float
    demand: float
    active_postings: int


@dataclass(frozen=True)
class RankedPath:
    """One scored path: deterministic rank, score and display-ready components.

    ``interest``/``demand``/``readiness`` are PERCENTS (0-100, 1 decimal) as
    the UI shows them; ``score`` is computed from the rounded 0-1 components so
    the displayed math checks out by hand.
    """

    path_id: str
    subfield_id: str
    rank: int
    score: float
    interest: float
    demand: float
    readiness: float
    active_postings: int
    low_data: bool


def rank_paths(candidates: Sequence[PathCandidate]) -> list[RankedPath]:
    """Score and rank path candidates deterministically (plan 4.2).

    Components are rounded to :data:`COMPONENT_DIGITS` first, the score is
    computed from those rounded values and rounded to :data:`SCORE_DIGITS` —
    so re-deriving the score from the numbers the UI displays is exact.

    Tie-break (plan 4.5): higher score, then higher demand, then alphabetical
    path id. ``low_data`` is ``active_postings < LOW_DATA_THRESHOLD``.

    Args:
        candidates: one :class:`PathCandidate` per scored path.

    Returns:
        Ranked paths, best first, with 1-based ``rank``; empty list only when
        the taxonomy has no paths (cannot happen post-seed).
    """
    scored: list[tuple[PathCandidate, float, float, float, float]] = []
    for candidate in candidates:
        interest = round(min(1.0, max(0.0, candidate.interest)), COMPONENT_DIGITS)
        demand = round(min(1.0, max(0.0, candidate.demand)), COMPONENT_DIGITS)
        readiness = round(min(1.0, max(0.0, candidate.readiness)), COMPONENT_DIGITS)
        score = round(path_score(interest, demand, readiness), SCORE_DIGITS)
        scored.append((candidate, interest, demand, readiness, score))

    # Tie-break: score desc, demand desc, path id asc (deterministic, plan 4.5).
    scored.sort(key=lambda row: (-row[4], -row[3], row[0].path_id))

    ranked: list[RankedPath] = []
    for position, (candidate, interest, demand, readiness, score) in enumerate(scored, start=1):
        ranked.append(
            RankedPath(
                path_id=candidate.path_id,
                subfield_id=candidate.subfield_id,
                rank=position,
                score=score,
                interest=round(interest * 100, SCORE_DIGITS),
                demand=round(demand * 100, SCORE_DIGITS),
                readiness=round(readiness * 100, SCORE_DIGITS),
                active_postings=candidate.active_postings,
                low_data=candidate.active_postings < LOW_DATA_THRESHOLD,
            )
        )
    return ranked
