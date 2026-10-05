"""Parser unit tests (plan step 1.7) against real recorded fixture shapes.

Pure-function tests: no DB, no HTTP. Most cases build minimal dicts shaped like
the real recordings; two load the committed fixtures directly so the parsers
are pinned to actual SerpApi response shapes — including the empty-result India
fixture (no ``jobs_results``) and the India software fixture that lacks
``job_highlights`` (every field except title/company is optional, AGENTS 3.4.7).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.integrations.serpapi.parsers import (
    detect_internship,
    iter_job_results,
    make_dedupe_key,
    parse_job_result,
    parse_next_page_token,
)
from app.integrations.serpapi.queries import job_fixture_variant

#: The committed recordings directory (read-only access — never written).
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "serpapi"


def _load_fixture(name: str) -> dict:
    """Load one committed fixture file, failing the test loudly if missing."""
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _job(**overrides: object) -> dict:
    """A minimal well-formed raw posting (matches real fixture shape)."""
    base: dict = {
        "title": "Quantum Error Correction Researcher",
        "company_name": "Riverlane",
        "location": "Cambridge, UK",
        "via": "LinkedIn",
        "extensions": ["3 days ago", "Full–time"],
        "apply_options": [{"title": "LinkedIn", "link": "https://example.com/apply/1"}],
        "share_link": "https://www.google.com/search?ibp=htl;jobs;q=...",
        "source_link": "https://careers.example.com/job/1",
        "job_id": "abc123",
        "description": "You will design decoders for quantum error correction.",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------- parse_job_result


def test_parse_job_result_requires_title_and_company() -> None:
    """An item lacking either required field is skipped, not defaulted."""
    no_company = parse_job_result({"title": "Engineer"})
    no_title = parse_job_result({"company_name": "Acme"})
    blank_title = parse_job_result({"title": "   ", "company_name": "Acme"})
    assert no_company is None and no_title is None and blank_title is None


def test_parse_job_result_skips_non_dict_item() -> None:
    """A non-object entry (string, number) is dropped without raising."""
    assert parse_job_result("not a job") is None
    assert parse_job_result(None) is None


def test_parse_job_result_extracts_all_optional_fields() -> None:
    """Optional fields map onto ParsedJob with defaults when absent."""
    parsed = parse_job_result(_job())
    assert parsed is not None
    assert parsed.title == "Quantum Error Correction Researcher"
    assert parsed.company == "Riverlane"
    assert parsed.location == "Cambridge, UK"
    assert parsed.via == "LinkedIn"
    assert parsed.extensions == ["3 days ago", "Full–time"]
    assert parsed.serp_job_id == "abc123"
    assert parsed.description == "You will design decoders for quantum error correction."


def test_parse_job_result_missing_optional_fields_become_defaults() -> None:
    """Only title+company present: everything else defaults (AGENTS 3.4.7)."""
    parsed = parse_job_result({"title": "Quantum Engineer", "company_name": "IQM"})
    assert parsed is not None
    assert parsed.location is None
    assert parsed.via is None
    assert parsed.description is None
    assert parsed.apply_url is None
    assert parsed.serp_job_id is None
    assert parsed.extensions == []


def test_parse_job_result_apply_url_precedence() -> None:
    """apply_options[0].link wins over share_link over source_link (plan 1.2.1)."""
    parsed = parse_job_result(_job())
    assert parsed is not None
    assert parsed.apply_url == "https://example.com/apply/1"

    no_apply = parse_job_result(_job(apply_options=[]))
    assert no_apply is not None
    assert no_apply.apply_url == "https://www.google.com/search?ibp=htl;jobs;q=..."

    only_source = parse_job_result(_job(apply_options=[], share_link=None))
    assert only_source is not None
    assert only_source.apply_url == "https://careers.example.com/job/1"

    nothing = parse_job_result(_job(apply_options=[], share_link=None, source_link=None))
    assert nothing is not None
    assert nothing.apply_url is None


def test_parse_job_result_apply_url_skips_malformed_options() -> None:
    """Non-dict options and link-less options are skipped, first valid link used."""
    raw = _job(
        apply_options=[{"title": "broken"}, "garbage", {"title": "OK", "link": "https://x.co/j"}]
    )
    parsed = parse_job_result(raw)
    assert parsed is not None
    assert parsed.apply_url == "https://x.co/j"


@pytest.mark.parametrize(
    ("raw_extensions", "expected"),
    [
        (None, []),
        ("not-a-list", []),
        ([1, 2], []),
        (["Full–time", "", "  "], ["Full–time"]),  # blanks dropped, strings kept
        (["3 days ago", 42, "Hybrid work"], ["3 days ago", "Hybrid work"]),  # mixed types
    ],
)
def test_parse_job_result_normalizes_extensions(
    raw_extensions: object, expected: list[str]
) -> None:
    """Extensions normalize to a list[str]; non-strings and blanks are dropped."""
    parsed = parse_job_result(_job(extensions=raw_extensions))
    assert parsed is not None
    assert parsed.extensions == expected


# ---------------------------------------------------- committed fixture shape pinning


def test_iter_job_results_parses_committed_global_fixture() -> None:
    """The real QEC global page-1 recording parses into 10 valid postings."""
    payload = _load_fixture("google_jobs__quantum-error-correction__global_p1.json")
    jobs = iter_job_results(payload)
    assert len(jobs) == 10
    assert all(job.title and job.company for job in jobs)
    assert all(job.apply_url for job in jobs)


def test_iter_job_results_handles_india_fixture_without_job_highlights() -> None:
    """The India software fixture has no job_highlights on any item — parses fine.

    Plan 1.5: job_highlights appeared only in global results; every field
    except title/company must be optional.
    """
    payload = _load_fixture("google_jobs__quantum-software-engineer__india_p1.json")
    assert all("job_highlights" not in item for item in payload["jobs_results"])
    jobs = iter_job_results(payload)
    assert len(jobs) == 10
    assert all(job.company for job in jobs)


def test_iter_job_results_empty_result_fixture_yields_no_postings() -> None:
    """The India QEC fixture (the 'no results' error body) parses to zero postings.

    It has no ``jobs_results`` key at all — zero postings, not an error
    (plan 1.7 / task notes).
    """
    payload = _load_fixture("google_jobs__quantum-error-correction__india_p1.json")
    assert "jobs_results" not in payload
    assert iter_job_results(payload) == []


def test_iter_job_results_malformed_items_are_skipped() -> None:
    """Mixed-shape lists skip bad entries but keep the good ones."""
    payload = {"jobs_results": [_job(), "garbage", {"title": "Only Title"}, _job()]}
    jobs = iter_job_results(payload)
    assert len(jobs) == 2


def test_iter_job_results_non_dict_payloads_yield_empty() -> None:
    """Whatever the client returns, a non-dict body is zero postings."""
    assert iter_job_results(None) == []
    assert iter_job_results([1, 2, 3]) == []


# ------------------------------------------------------------------- detect_internship


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Quantum Intern", True),
        ("quantum SOFTWARE INTERN (summer)", True),
        ("Research Internship — QEC team", True),
        ("Internships: 2027 cohort", True),
        ("interns wanted", True),
        ("Internal Tools Engineer", False),  # must not match (plan 1.2.2)
        ("International Sales Manager", False),  # must not match (plan 1.2.2)
        ("Internalization engineer", False),
        ("Quantum Software Engineer", False),
        ("", False),
        (None, False),
    ],
)
def test_detect_internship_table(text: str | None, expected: bool) -> None:
    """\\bintern(ship)?s?\\b matches intern titles, never internal/international."""
    assert detect_internship(text, []) is expected


def test_detect_internship_matches_extensions_too() -> None:
    """Extensions like 'Internship' count even when the title is generic."""
    assert detect_internship("Quantum Engineer", ["6 weeks ago", "Internship"]) is True
    assert detect_internship("Quantum Engineer", ["6 weeks ago", "Full–time"]) is False


# --------------------------------------------------------------------- make_dedupe_key


def test_make_dedupe_key_is_stable_across_case_and_punctuation() -> None:
    """Normalization makes keys insensitive to case/punct/whitespace differences."""
    a = make_dedupe_key("Quantum Software Engineer", "IQM Inc.", "Munich, Germany")
    b = make_dedupe_key("QUANTUM SOFTWARE   ENGINEER", "iqm inc", "Munich Germany")
    assert a == b


def test_make_dedupe_key_differs_for_different_triples() -> None:
    """Different title/company/location produce different keys."""
    base = make_dedupe_key("Title", "Company", "Location")
    assert base != make_dedupe_key("Title", "Company", "Other")
    assert base != make_dedupe_key("Title", "Company2", "Location")
    assert base != make_dedupe_key("Title2", "Company", "Location")


def test_make_dedupe_key_treats_missing_location_as_empty() -> None:
    """None and empty-string locations dedupe together (same job, missing field)."""
    assert make_dedupe_key("T", "C", None) == make_dedupe_key("T", "C", "")


def test_make_dedupe_key_is_sha1_hex() -> None:
    """Key is a 40-char lowercase hex digest (column is String(40))."""
    key = make_dedupe_key("x", "y", "z")
    assert len(key) == 40
    assert all(c in "0123456789abcdef" for c in key)


# ----------------------------------------------------------------- parse_next_page_token


def test_parse_next_page_token_reads_pagination() -> None:
    """Token is read from serpapi_pagination.next_page_token (real fixture shape)."""
    payload = _load_fixture("google_jobs__quantum-error-correction__global_p1.json")
    token = parse_next_page_token(payload)
    assert token is not None
    assert len(token) > 20


def test_parse_next_page_token_absent_or_blank_returns_none() -> None:
    """Missing/empty/malformed pagination means 'no more data', never an error."""
    assert parse_next_page_token({}) is None
    assert parse_next_page_token({"serpapi_pagination": {}}) is None
    assert parse_next_page_token({"serpapi_pagination": {"next_page_token": "  "}}) is None
    assert parse_next_page_token({"serpapi_pagination": "oops"}) is None
    assert parse_next_page_token(None) is None


def test_job_fixture_variant_names() -> None:
    """Variant naming matches the recording plan (global_p1/p2, india_p1)."""
    assert job_fixture_variant("global", 1) == "global_p1"
    assert job_fixture_variant("global", 2) == "global_p2"
    assert job_fixture_variant("india", 1) == "india_p1"
    with pytest.raises(ValueError, match="unknown region"):
        job_fixture_variant("mars", 1)
