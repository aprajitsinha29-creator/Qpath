"""Research service + Scholar parser tests (plan 2.5 / 2.8) — no network.

Scholar fixtures are written to per-test tmp dirs (never live calls); the LLM
is the offline :class:`FakeStructuredLLM`. Covers the year parser
(table-driven), theme index validation, empty-result handling and the refresh
endpoint wiring with the LLM dependency overridden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.integrations.gemini.client import FakeStructuredLLM
from app.integrations.gemini.schemas import Theme, ThemeSet
from app.integrations.serpapi.parsers import (
    iter_scholar_results,
    parse_scholar_result,
    parse_scholar_year,
)
from app.models import PaperSnapshot, ResearchTheme
from app.services import research_service

pytestmark = pytest.mark.usefixtures("_seed_reference_data")

ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


# ------------------------------------------------------------- Scholar parsers


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("A Smith - Phys Rev, 2025 - nature.com", 2025),
        ("J Doe - arXiv preprint arXiv:2610.01923, 2026 - arxiv.org", 2026),
        ("A Lemeshko - researchgate.net", None),  # no year at all
        ("Phys Rev A 98, 012345 (2018) - 12 pages", 2018),
        ("", None),
        (None, None),
        ("co-authored 1999 paper, reprinted 2024", 2024),  # last match wins
        ("in 2100 nothing", None),  # 4-digit but not 19xx/20xx
        ("Volume 19, issue 3", None),  # '19' alone is not a year
    ],
)
def test_parse_scholar_year_table(summary: str | None, expected: int | None) -> None:
    """The last 19xx/20xx year in the summary wins (plan 2.5.1)."""
    assert parse_scholar_year(summary) == expected


def _paper(**overrides: Any) -> dict[str, Any]:
    """A minimal raw Scholar result matching the committed fixtures' shape."""
    base: dict[str, Any] = {
        "position": 1,
        "title": "Surface code with improved decoding",
        "result_id": "abc123",
        "link": "https://arxiv.org/abs/2610.01923",
        "snippet": "2 days ago - We improve decoder latency …",
        "publication_info": {"summary": "F Burt - arXiv preprint, 2026 - arxiv.org"},
        "inline_links": {"cited_by": {"total": 2, "cites_id": "123"}},
    }
    base.update(overrides)
    return base


def test_parse_scholar_result_requires_title_only() -> None:
    """title is required; every other field is optional (AGENTS 3.4.7)."""
    parsed = parse_scholar_result(_paper())
    assert parsed is not None
    assert parsed.title == "Surface code with improved decoding"
    assert parsed.year == 2026
    assert parsed.cited_by == 2

    minimal = parse_scholar_result({"title": "Bare title"})
    assert minimal is not None
    assert minimal.snippet is None and minimal.link is None
    assert minimal.year is None and minimal.cited_by is None


def test_parse_scholar_result_skips_malformed_items() -> None:
    """Non-dict items and title-less items are dropped, never raised."""
    assert parse_scholar_result("garbage") is None
    assert parse_scholar_result({"snippet": "no title"}) is None
    assert parse_scholar_result(None) is None


def test_iter_scholar_results_parses_committed_fixture() -> None:
    """The committed QEC Scholar recording parses end to end."""
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "serpapi"
        / "google_scholar__quantum-error-correction__recent.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    papers = iter_scholar_results(payload)
    assert len(papers) >= 15
    assert all(p.title for p in papers)


def test_iter_scholar_results_empty_body_yields_no_papers() -> None:
    """A body without organic_results (e.g. the 'no results' error) → []."""
    assert iter_scholar_results({"error": "Google hasn't returned any results..."}) == []
    assert iter_scholar_results({}) == []
    assert iter_scholar_results(None) == []


# ------------------------------------------------------------ theme validation


def _fake_themes(*themes: Theme) -> FakeStructuredLLM:
    """Build a fake LLM returning the given themes."""
    return FakeStructuredLLM([ThemeSet(themes=list(themes))])


def _papers(n: int) -> list[PaperSnapshot]:
    """In-memory snapshots (ids 1..n) for validation tests."""
    return [
        PaperSnapshot(id=i, subfield_id="qec", batch_id="b", query="q", title=f"P{i}")
        for i in range(1, n + 1)
    ]


def test_theme_indexes_out_of_range_are_dropped() -> None:
    """An index beyond the batch is dropped, valid ones survive (plan 2.5.2)."""
    themes = research_service._validate_theme_set(
        ThemeSet(
            themes=[
                Theme(label="A", summary="s", paper_indexes=[1, 999]),
                Theme(label="B", summary="s", paper_indexes=[0]),  # 1-based: 0 invalid
            ]
        ),
        _papers(3),
    )
    assert len(themes) == 1
    assert themes[0]["paper_ids"] == [1]


def test_theme_without_any_valid_index_is_dropped() -> None:
    """A theme with zero valid paper pointers is removed (plan 4.7)."""
    themes = research_service._validate_theme_set(
        ThemeSet(themes=[Theme(label="X", summary="s", paper_indexes=[50])]),
        _papers(3),
    )
    assert themes == []


def test_theme_paper_ids_are_deduplicated() -> None:
    """Repeated indexes collapse to one paper id."""
    themes = research_service._validate_theme_set(
        ThemeSet(themes=[Theme(label="A", summary="s", paper_indexes=[2, 2, 1])]),
        _papers(3),
    )
    assert themes[0]["paper_ids"] == [2, 1]


def test_theme_list_is_capped_at_five() -> None:
    """More than 5 valid themes are truncated (plan 4.7: 3–5)."""
    many = [Theme(label=f"T{i}", summary="s", paper_indexes=[1]) for i in range(8)]
    themes = research_service._validate_theme_set(ThemeSet(themes=many), _papers(3))
    assert len(themes) == 5


# ------------------------------------------------------------ service behavior


def _write_scholar_fixture(fixture_dir: Path, query: str, payload: dict[str, Any]) -> None:
    """Write one Scholar recording into the per-test fixture dir."""
    from app.integrations.serpapi.client import fixture_file_name

    name = fixture_file_name("google_scholar", query, "recent")
    (fixture_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def _scholar_payload(n: int) -> dict[str, Any]:
    """A Scholar response with ``n`` organic results."""
    return {"organic_results": [_paper(title=f"Paper {i}") for i in range(n)]}


@pytest.fixture()
def _scholar_env(fixture_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point settings at the per-test fixture dir and admin token."""
    monkeypatch.setenv("SERPAPI_FIXTURE_DIR", str(fixture_dir))
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    return fixture_dir


def test_refresh_scholar_stores_papers_and_themes(db_session: Session, _scholar_env: Path) -> None:
    """One run: snapshots + one themes row per subfield, themed batch correct."""
    from app.core.config import get_settings
    from app.integrations.serpapi.client import SerpApiClient

    _write_scholar_fixture(_scholar_env, "quantum error correction", _scholar_payload(6))
    client = SerpApiClient(get_settings(), _session_factory(), fixture_dir=_scholar_env)
    fake = _fake_themes(
        Theme(label="Decoders", summary="Latency work.", paper_indexes=[1, 2]),
        Theme(label="Ghost", summary="Bad index.", paper_indexes=[999]),
    )

    run = research_service.refresh_scholar(db_session, client, fake, ["qec"])

    assert run.status == "done"
    details = run.details or {}
    assert details["papers_stored"] == 6
    assert details["subfields_with_themes"] == 1
    papers = list(db_session.query(PaperSnapshot).all())
    assert len(papers) == 6
    themes = list(db_session.query(ResearchTheme).all())
    assert len(themes) == 1
    assert [t["label"] for t in themes[0].themes] == ["Decoders"]


def _session_factory():
    """Return the SessionLocal callable (kept as a helper for readability)."""
    from app.db.session import SessionLocal

    return SessionLocal


def test_refresh_scholar_empty_result_is_not_an_error(
    db_session: Session, _scholar_env: Path
) -> None:
    """A subfield whose query returns zero papers gets no themes, no error."""
    from app.core.config import get_settings
    from app.integrations.serpapi.client import SerpApiClient

    _write_scholar_fixture(_scholar_env, "quantum error correction", {"organic_results": []})
    client = SerpApiClient(get_settings(), _session_factory(), fixture_dir=_scholar_env)
    fake = _fake_themes(Theme(label="Unused", summary="s", paper_indexes=[1]))

    run = research_service.refresh_scholar(db_session, client, fake, ["qec"])

    assert run.status == "done"
    details = run.details or {}
    assert details["papers_stored"] == 0
    assert details["subfields_with_themes"] == 0
    assert details["errors"] == []
    assert db_session.query(ResearchTheme).count() == 0
    assert fake.call_count == 0  # no papers → no theme call


def test_refresh_scholar_llm_failure_is_recorded_not_raised(
    db_session: Session, _scholar_env: Path
) -> None:
    """A theme-generation failure marks the run partial; papers stay stored."""
    from app.core.config import get_settings
    from app.core.errors import LLMOutputError
    from app.integrations.serpapi.client import SerpApiClient

    _write_scholar_fixture(_scholar_env, "quantum error correction", _scholar_payload(4))
    client = SerpApiClient(get_settings(), _session_factory(), fixture_dir=_scholar_env)
    fake = FakeStructuredLLM([LLMOutputError("invalid output")])

    run = research_service.refresh_scholar(db_session, client, fake, ["qec"])

    assert run.status == "partial"
    assert db_session.query(PaperSnapshot).count() == 4  # papers persisted anyway
    assert db_session.query(ResearchTheme).count() == 0
    assert "llm_output_error" in (run.details or {}).get("errors", [""])[0]


def test_refresh_scholar_missing_fixture_is_recorded(
    db_session: Session, _scholar_env: Path
) -> None:
    """No recording for a subfield → error entry, other subfields unaffected."""
    from app.core.config import get_settings
    from app.integrations.serpapi.client import SerpApiClient

    client = SerpApiClient(get_settings(), _session_factory(), fixture_dir=_scholar_env)
    fake = _fake_themes(Theme(label="T", summary="s", paper_indexes=[1]))

    run = research_service.refresh_scholar(db_session, client, fake)

    details = run.details or {}
    assert run.status == "partial"
    assert details["papers_stored"] == 0
    assert len(details["errors"]) == 6  # every subfield lacks a recording


def test_latest_themes_returns_newest_batch_only(db_session: Session) -> None:
    """Only the most recent batch's themes are served (older ones are history)."""
    db_session.add(
        ResearchTheme(
            subfield_id="qec",
            batch_id="old",
            themes=[{"label": "Old", "summary": "s", "paper_ids": [1]}],
            model="m",
        )
    )
    db_session.commit()
    assert [t["label"] for t in research_service.latest_themes_by_subfield(db_session, "qec")] == [
        "Old"
    ]

    db_session.add(
        ResearchTheme(
            subfield_id="qec",
            batch_id="new",
            themes=[{"label": "New", "summary": "s", "paper_ids": [1]}],
            model="m",
        )
    )
    db_session.commit()
    assert [t["label"] for t in research_service.latest_themes_by_subfield(db_session, "qec")] == [
        "New"
    ]


def test_latest_themes_unknown_subfield_is_empty(db_session: Session) -> None:
    """An unknown subfield simply has no themes (empty state, never an error)."""
    assert research_service.latest_themes_by_subfield(db_session, "nope") == []


# ------------------------------------------------------------------- endpoint


def test_admin_refresh_scholar_endpoint(
    client: TestClient, _scholar_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /admin/refresh/scholar with a fake LLM returns the summary shape."""
    from app.api.deps import get_structured_llm

    _write_scholar_fixture(_scholar_env, "quantum error correction", _scholar_payload(5))
    fake = _fake_themes(Theme(label="Decoders", summary="Fast decoding.", paper_indexes=[1, 2]))
    client.app.dependency_overrides[get_structured_llm] = lambda: fake
    try:
        response = client.post("/api/v1/admin/refresh/scholar", headers=ADMIN_HEADERS)
    finally:
        client.app.dependency_overrides.pop(get_structured_llm, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "scholar"
    assert payload["papers_stored"] == 5
    assert payload["subfields_with_themes"] == 1
    assert payload["serpapi_calls"] == 6


def test_admin_refresh_scholar_rejects_missing_token(client: TestClient) -> None:
    """The Scholar endpoint is admin-guarded like the other admin routes."""
    response = client.post("/api/v1/admin/refresh/scholar")
    assert response.status_code == 401


def test_no_code_computes_trends_from_total_results() -> None:
    """Assert no model or service uses total_results for trends (AGENTS 3.4.9 / plan 2.8).

    Google Scholar total_results is erratic and must never be used to compute
    trend numbers or growth rates. Only qualitative themes are extracted.
    """
    import dataclasses

    from app.integrations.serpapi.parsers import ParsedPaper
    from app.models.research import PaperSnapshot, ResearchTheme

    # 1. ORM models have no total_results column
    assert not hasattr(PaperSnapshot, "total_results")
    assert not hasattr(ResearchTheme, "total_results")

    # 2. ParsedPaper dataclass has no total_results field
    fields = [f.name for f in dataclasses.fields(ParsedPaper)]
    assert "total_results" not in fields

    # 3. Raw Scholar result with search_information.total_results is ignored
    raw_with_total = _paper()
    raw_with_total["search_information"] = {"total_results": 12345}
    parsed = parse_scholar_result(raw_with_total)
    assert parsed is not None
    assert not hasattr(parsed, "total_results")
