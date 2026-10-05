"""SerpApi query plans: which searches run for which subfield (plan 4.6).

One source of truth shared by the client, the ingestion services (Phase 1+) and
the fixture recorder. Query strings are reviewed by the owner in manual task
M-07 — they are data, not configuration, so they live here rather than in env.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Fixture variant names (file suffix) agreed in plan 0.4.3.
JOB_GLOBAL_P1 = "global_p1"
JOB_GLOBAL_P2 = "global_p2"
JOB_INDIA_P1 = "india_p1"
SCHOLAR_RECENT = "recent"


@dataclass(frozen=True)
class QuerySpec:
    """One Google Jobs search: a subfield tag plus the query text.

    ``tier`` separates the daily core query per subfield from extra queries
    that only run in bootstrap/manual full refreshes (plan 4.6).
    """

    subfield_id: str
    query: str
    tier: Literal["core", "extended"]


@dataclass(frozen=True)
class ScholarQuerySpec:
    """One Google Scholar search per subfield (weekly, recent papers only).

    Scholar is used for qualitative research themes — never for trend counts
    (``total_results`` is erratic; plan 1.5, AGENTS 3.4.9).
    """

    subfield_id: str
    query: str


@dataclass(frozen=True)
class FixtureSpec:
    """One file the fixture recorder should capture (plan 4.6).

    Attributes:
        engine: SerpApi engine id.
        query: search text.
        variant: fixture variant appended to the file name (region/page).
        location: Google Jobs ``location`` param (India runs only).
        gl: Google Jobs country code; ``location`` and ``uule`` are mutually
            exclusive (AGENTS 3.4.8) and we never send ``uule``.
        follow_next_page: after recording, follow
            ``serpapi_pagination.next_page_token`` and record one more page —
            the old ``start`` offset is discontinued (AGENTS 3.4.8).
        next_page_variant: variant name for that follow-up file.
    """

    engine: Literal["google_jobs", "google_scholar"]
    query: str
    variant: str
    location: str | None = None
    gl: str | None = None
    follow_next_page: bool = False
    next_page_variant: str | None = None


#: Core = daily runs; extended = bootstrap/manual full refresh only (plan 4.6).
JOB_QUERY_PLAN: tuple[QuerySpec, ...] = (
    QuerySpec("qec", "quantum error correction", "core"),
    QuerySpec("qec", "fault tolerant quantum computing", "extended"),
    QuerySpec("hardware", "quantum hardware engineer", "core"),
    QuerySpec("hardware", "superconducting qubit", "extended"),
    QuerySpec("hardware", "trapped ion quantum", "extended"),
    QuerySpec("hardware", "neutral atom quantum", "extended"),
    QuerySpec("software", "quantum software engineer", "core"),
    QuerySpec("software", "quantum compiler", "extended"),
    QuerySpec("algorithms", "quantum algorithms", "core"),
    QuerySpec("algorithms", "quantum applications scientist", "extended"),
    QuerySpec("qml", "quantum machine learning", "core"),
    QuerySpec("crypto_net", "post-quantum cryptography", "core"),
    QuerySpec("crypto_net", "quantum key distribution", "extended"),
    QuerySpec("crypto_net", "quantum networking", "extended"),
)

SCHOLAR_QUERY_PLAN: tuple[ScholarQuerySpec, ...] = (
    ScholarQuerySpec("qec", "quantum error correction"),
    ScholarQuerySpec("hardware", "quantum computing hardware qubits"),
    ScholarQuerySpec("software", "quantum compiler transpilation"),
    ScholarQuerySpec("algorithms", "quantum algorithms"),
    ScholarQuerySpec("qml", "quantum machine learning"),
    ScholarQuerySpec("crypto_net", "quantum key distribution OR post-quantum cryptography"),
)

# Subfields whose core query is also recorded for India (plan 4.6: 2 India queries).
_FIXTURE_INDIA_SUBFIELDS = ("qec", "software")

#: Google Jobs region parameter pairs (plan 1.3.1): global = no location,
#: India = location + gl. ``location`` and ``uule`` are mutually exclusive
#: (AGENTS 3.4.8) and we never send ``uule``.
REGION_PARAMS: dict[str, dict[str, str | None]] = {
    "global": {"location": None, "gl": None},
    "india": {"location": "India", "gl": "in"},
}

_FIXTURE_JOB_GLOBAL = tuple(
    FixtureSpec(
        engine="google_jobs",
        query=spec.query,
        variant=JOB_GLOBAL_P1,
        # One pagination recording: page 2 of the QEC query via next_page_token.
        follow_next_page=spec.subfield_id == "qec",
        next_page_variant=JOB_GLOBAL_P2 if spec.subfield_id == "qec" else None,
    )
    for spec in JOB_QUERY_PLAN
    if spec.tier == "core"
)

_FIXTURE_JOB_INDIA = tuple(
    FixtureSpec(
        engine="google_jobs",
        query=spec.query,
        variant=JOB_INDIA_P1,
        location="India",
        gl="in",
    )
    for spec in JOB_QUERY_PLAN
    if spec.tier == "core" and spec.subfield_id in _FIXTURE_INDIA_SUBFIELDS
)

_FIXTURE_SCHOLAR = tuple(
    FixtureSpec(engine="google_scholar", query=spec.query, variant=SCHOLAR_RECENT)
    for spec in SCHOLAR_QUERY_PLAN
)

#: What ``make record-fixtures`` captures: 6 core global jobs (page 1), 2 India
#: jobs, 6 Scholar queries — plus one automatic page-2 follow-up (plan 4.6).
FIXTURE_PLAN: tuple[FixtureSpec, ...] = _FIXTURE_JOB_GLOBAL + _FIXTURE_JOB_INDIA + _FIXTURE_SCHOLAR


def estimate_fixture_calls() -> int:
    """Return how many live SerpApi credits a full fixture recording costs."""
    return len(FIXTURE_PLAN) + sum(1 for spec in FIXTURE_PLAN if spec.follow_next_page)


def job_fixture_variant(region: str, page: int) -> str:
    """Return the fixture variant for a jobs query of ``region`` and 1-based ``page``.

    Args:
        region: ``global`` or ``india``.
        page: 1-based page number.

    Returns:
        ``global_p1``/``global_p2``/``india_p1``-style variant name. Recordings
        only exist for the plan 4.6 set (global pages 1-2 for qec, page 1
        elsewhere; india page 1 for qec+software), so higher pages naturally
        produce missing-fixture terminations — that is the intended
        "no more data" signal in fixture mode, not an error.

    Raises:
        ValueError: for an unknown region (a programming error, not runtime data).
    """
    if region not in REGION_PARAMS:
        raise ValueError(f"unknown region: {region!r}")
    return f"{region}_p{page}"
