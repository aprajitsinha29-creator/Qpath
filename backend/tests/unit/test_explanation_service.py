"""Unit tests for the pure explanation logic (plan 4.7, design decisions 1/2).

No DB, no HTTP, no LLM: evidence building/hashing, the numbers-in-evidence
validator, the per-item plan 4.7 domain checks, and the deterministic template
fallback (which must itself pass the numbers validator — design decision 2).
"""

from __future__ import annotations

import pytest

from app.integrations.gemini.schemas import PathExplanationItem
from app.schemas.paths import PathEvidence, PathExplanationOut, PathResult, ScoreBreakdown
from app.schemas.pulse import PostingOut
from app.services.explanation_service import (
    HEADLINE_MAX_WORDS,
    REASON_COUNT,
    build_evidence,
    build_template,
    evidence_hash,
    validate_explanation,
    validate_numbers,
)
from app.services.scoring_service import WEIGHTS_PERCENT

# A representative low-demand path whose values reappear in assertions.
SAMPLE = {
    "path_id": "qec_engineer",
    "title": "QEC Researcher / Engineer",
    "subfield_id": "qec",
    "rank": 2,
    "score": 63.7,
    "interest": 75.0,
    "demand": 41.7,
    "readiness": 71.7,
    "active": 12,
    "internships": 3,
    "phd_share": 0.333,
    "phd_share_pct": 33.3,
    "share": 0.667,
    "share_pct": 66.7,
}


def _posting() -> PostingOut:
    """One minimal sample posting (fields the evidence panel renders)."""
    from datetime import datetime

    return PostingOut(
        id=1,
        title="QEC Engineer",
        company="Riverlane",
        location="Cambridge, UK",
        via="LinkedIn",
        apply_url="https://example.com/job/1",
        is_internship=False,
        first_seen_at=datetime(2026, 10, 1, 12, 0, 0),
        snippet="Build decoders.",
    )


def make_result(**overrides: object) -> PathResult:
    """Build a PathResult fixture; keyword overrides replace top-level fields."""
    values: dict[str, object] = {
        "path_id": SAMPLE["path_id"],
        "title": SAMPLE["title"],
        "subfield_id": SAMPLE["subfield_id"],
        "rank": SAMPLE["rank"],
        "score": SAMPLE["score"],
        "breakdown": ScoreBreakdown(
            interest=SAMPLE["interest"],
            demand=SAMPLE["demand"],
            readiness=SAMPLE["readiness"],
            weights=dict(WEIGHTS_PERCENT),
        ),
        "is_top3": True,
        "low_data": True,
        "saturated": False,
        "evidence": PathEvidence(
            active_postings=SAMPLE["active"],
            internship_postings=SAMPLE["internships"],
            top_skills=[
                {
                    "skill_id": "stim",
                    "name": "Stim",
                    "share": SAMPLE["share"],
                    "share_pct": SAMPLE["share_pct"],
                }
            ],
            phd_share=SAMPLE["phd_share"],
            phd_share_pct=SAMPLE["phd_share_pct"],
            sample_postings=[_posting()],
        ),
        "explanation": None,
    }
    values.update(overrides)
    return PathResult(**values)  # type: ignore[arg-type]


def make_item(**overrides: object) -> PathExplanationItem:
    """Build a valid model item; keyword overrides break individual rules."""
    values: dict[str, object] = {
        "path_id": SAMPLE["path_id"],
        "headline": "Strong fit for error correction",
        "reasons": [
            f"Interest {SAMPLE['interest']}% from your diagnostic.",
            f"Readiness {SAMPLE['readiness']}% on this subfield.",
            f"{SAMPLE['active']} active postings back this path.",
        ],
        "caveat": "Demand evidence is thin because the sample is small.",
        "next_step": "Compare it with your top-ranked paths.",
    }
    values.update(overrides)
    return PathExplanationItem(**values)  # type: ignore[arg-type]


# --------------------------------------------------------------------- evidence


def test_build_evidence_contains_display_renderings() -> None:
    """Every UI-visible number lands in the evidence (raw + percent forms)."""
    evidence = build_evidence(make_result(), 6)

    assert evidence["active_postings"] == SAMPLE["active"]
    assert evidence["breakdown"]["interest_pct"] == SAMPLE["interest"]
    assert evidence["breakdown"]["weights_pct"] == WEIGHTS_PERCENT
    assert evidence["phd_share"] == SAMPLE["phd_share"]
    assert evidence["phd_share_pct"] == SAMPLE["phd_share_pct"]
    assert evidence["top_skills"][0]["share_pct"] == SAMPLE["share_pct"]
    assert evidence["low_data_threshold"] == 8
    assert evidence["total_paths"] == 6
    # Items, too: titles/companies are evidence the model may echo.
    assert evidence["sample_postings"][0]["company"] == "Riverlane"


def test_evidence_hash_is_stable_and_tracks_changes() -> None:
    """Same result → same hash; any cited number changing → new hash (cache)."""
    baseline = evidence_hash(build_evidence(make_result(), 6))

    assert evidence_hash(build_evidence(make_result(), 6)) == baseline
    # Score moved (e.g. new postings ingested) → stale cache must not be used.
    changed = make_result(score=64.0)
    assert evidence_hash(build_evidence(changed, 6)) != baseline
    # Rank moved (retake) → also a different hash.
    reranked = make_result(rank=3)
    assert evidence_hash(build_evidence(reranked, 6)) != baseline


# ---------------------------------------------------------------- numbers rule


def test_validate_numbers_accepts_numbers_copied_from_evidence() -> None:
    """Design decision 2: citing only evidence numbers passes."""
    evidence = build_evidence(make_result(), 6)
    fields = [
        f"Rank {SAMPLE['rank']} of {SAMPLE['interest']}%",  # rank + interest pct
        f"{SAMPLE['active']} postings, phd {SAMPLE['phd_share_pct']}%",
        f"skill share {SAMPLE['share_pct']}% and threshold 8",
    ]
    assert validate_numbers(fields, evidence) is True


@pytest.mark.parametrize(
    "field",
    [
        "There are 999 active postings.",  # invented count
        "Demand grew 42% this year.",  # invented trend + wrong number
        "Salaries reach 100000.",  # salaries are forbidden content anyway
        "Readiness is 75.5%.",  # not the displayed 75.0 — rounding is a rewrite
    ],
)
def test_validate_numbers_rejects_numbers_not_in_evidence(field: str) -> None:
    """Any number absent from the evidence JSON rejects the item (design 2)."""
    evidence = build_evidence(make_result(), 6)
    assert validate_numbers([field], evidence) is False


def test_validate_numbers_roundtrip_of_float_renderings() -> None:
    """Whole-number rendering of a float value (42 vs 42.0) still matches."""
    evidence = {"active_postings": 42}
    assert validate_numbers(["Only 42 postings"], evidence) is True


# ---------------------------------------------------------- plan 4.7 item rules


def test_validate_explanation_accepts_a_contract_valid_item() -> None:
    """The representative item passes every plan 4.7 rule."""
    evidence = build_evidence(make_result(), 6)
    payload, reason = validate_explanation(make_item(), evidence)

    assert reason == "ok"
    assert payload is not None
    assert payload["headline"] == "Strong fit for error correction"
    assert len(payload["reasons"]) == REASON_COUNT


@pytest.mark.parametrize(
    ("item", "expected_reason_fragment"),
    [
        (None, "missing"),
        (make_item(path_id="other_path"), "path_id mismatch"),
        (make_item(reasons=["only one reason"]), "expected exactly 3"),
        (make_item(reasons=["a", "b", "c", "d"]), "expected exactly 3"),
        (make_item(headline=""), "empty headline/caveat/next_step"),
        (make_item(caveat=""), "empty headline/caveat/next_step"),
        (make_item(headline="word " * (HEADLINE_MAX_WORDS + 1)), "exceeds 12 words"),
        (make_item(caveat="word " * 31), "exceeds 30 words"),
        (make_item(next_step="word " * 26), "exceeds 25 words"),
        (
            make_item(reasons=["word " * 26, "fine", "ok"]),
            "exceeds 25 words",
        ),
        (make_item(caveat="The market grew 42% last year."), "number not present"),
    ],
)
def test_validate_explanation_rejects_bad_items(
    item: PathExplanationItem | None, expected_reason_fragment: str
) -> None:
    """Each plan 4.7 / design-2 violation yields (None, reason) — never a raise."""
    evidence = build_evidence(make_result(), 6)
    payload, reason = validate_explanation(item, evidence)

    assert payload is None
    assert expected_reason_fragment in reason


# --------------------------------------------------------------------- template


def test_template_passes_the_numbers_validator() -> None:
    """Design decision 2 applies to templates too: built from evidence only."""
    evidence = build_evidence(make_result(), 6)
    template = build_template(evidence)
    fields = [template["headline"], *template["reasons"], template["caveat"], template["next_step"]]

    assert validate_numbers(fields, evidence) is True


def test_template_is_deterministic_and_labelled_by_callers() -> None:
    """Same evidence → byte-identical template (plan 4.4 'deterministic')."""
    evidence = build_evidence(make_result(), 6)
    assert build_template(evidence) == build_template(evidence)


@pytest.mark.parametrize(
    ("overrides", "expected_fragment"),
    [
        ({"low_data": True}, "fewer than 8 active postings"),
        ({"low_data": False, "saturated": True}, "search page cap"),
        ({"low_data": False, "saturated": False}, "sample of live postings"),
    ],
)
def test_template_caveat_reflects_flags(overrides: dict, expected_fragment: str) -> None:
    """Caveat wording honestly reports thin data, saturation, or plain sampling."""
    evidence = build_evidence(make_result(**overrides), 6)
    assert expected_fragment in build_template(evidence)["caveat"].lower()


def test_template_output_validates_as_an_api_payload() -> None:
    """The stored payload + provenance round-trips through PathExplanationOut."""
    evidence = build_evidence(make_result(), 6)
    out = PathExplanationOut.model_validate(
        {**build_template(evidence), "generated_by": "template", "model": None}
    )
    assert out.generated_by == "template"
    assert out.model is None
    assert len(out.reasons) == 3
