"""Google Jobs response parsers: raw SerpApi JSON → typed internal objects.

Phase 1 step 1.2. These are pure functions (no DB, no HTTP) so they can be
unit-tested against the *real recorded fixtures* (plan 1.7). They are defensive
by design (AGENTS.md 3.4.7): every response field is optional except what a
parser explicitly requires — for a job that is ``title`` and ``company_name``;
anything else missing becomes a default, and items that lack the required
fields are skipped with a logged warning rather than crashing the ingestion.

The empty-result response (``{"error": "Google hasn't returned any results..."}``,
the committed India QEC fixture) contains no ``jobs_results`` key at all —
:func:`iter_job_results` treats that as zero postings, not an error.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: The only fields a posting must have; everything else is optional (plan 1.5).
_REQUIRED_JOB_FIELDS = ("title", "company_name")

#: \b around the whole group keeps "internal"/"international" from matching:
#: they contain "intern" but \bintern\b cannot match inside those words
#: (plan 1.2.2). Case-insensitive; "interns", "internship", "internships" match.
_INTERNSHIP_PATTERN = re.compile(r"\bintern(ship)?s?\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedJob:
    """Typed internal representation of one posting (raw fields never leave the parser).

    Attributes:
        title: posting title (required).
        company: company name (required, renamed from SerpApi ``company_name``).
        location: free-text location, or None.
        via: aggregator the listing came via (e.g. "LinkedIn"), or None.
        description: full description text, or None.
        apply_url: best apply link (apply_options[0].link → share_link →
            source_link → None — exactly the plan 1.2.1 precedence).
        serp_job_id: opaque SerpApi job id, or None (not used for identity).
        extensions: normalized list of display strings ("3 days ago", "Full–time").
    """

    title: str
    company: str
    location: str | None
    via: str | None
    description: str | None
    apply_url: str | None
    serp_job_id: str | None
    extensions: list[str]


def _as_str(value: Any) -> str | None:
    """Coerce a raw JSON value to a stripped string, or None when absent/empty/non-string.

    Non-string JSON types (numbers, nested objects) are intentionally coerced to
    None instead of str()-ed: a numeric "title" is malformed data and the item
    should fail the required-field check rather than pass with a fake title.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_extensions(raw: Any) -> list[str]:
    """Normalize SerpApi ``extensions`` to a list[str], dropping non-string entries.

    SerpApi usually returns strings ("16 days ago", "Full–time") but contract
    3.4.7 says treat the shape as optional — anything else is dropped.
    """
    if not isinstance(raw, list):
        return []
    return [item for item in (v.strip() for v in raw if isinstance(v, str)) if item]


def _extract_apply_url(raw: dict[str, Any]) -> str | None:
    """Pick the apply URL by the plan 1.2.1 precedence chain.

    Order: first ``apply_options[].link`` (deepest, most specific), then
    ``share_link`` (Google-hosted redirect), then ``source_link`` (original
    page), else None. Every level is validated as a non-empty string.
    """
    apply_options = raw.get("apply_options")
    if isinstance(apply_options, list):
        for option in apply_options:
            if isinstance(option, dict):
                link = _as_str(option.get("link"))
                if link:
                    return link
    return _as_str(raw.get("share_link")) or _as_str(raw.get("source_link"))


def parse_job_result(raw: Any) -> ParsedJob | None:
    """Parse one element of ``jobs_results`` into a :class:`ParsedJob`.

    Args:
        raw: one raw posting dict from SerpApi (or anything else — malformed
            items are logged and skipped, never raised, per AGENTS 3.4.7).

    Returns:
        A ParsedJob, or None when the item is not a dict or lacks a non-empty
        ``title``/``company_name``.

    Side effects:
        Logs a WARNING for every skipped item (so fixture gaps are visible).
    """
    if not isinstance(raw, dict):
        logger.warning("skipping malformed job result (not an object): %r", raw)
        return None

    title = _as_str(raw.get("title"))
    company = _as_str(raw.get("company_name"))
    missing = [
        field
        for field, value in zip(_REQUIRED_JOB_FIELDS, (title, company), strict=True)
        if not value
    ]
    if missing:
        logger.warning("skipping job result missing %s: title=%r", missing, title)
        return None

    return ParsedJob(
        title=title,
        company=company,
        location=_as_str(raw.get("location")),
        via=_as_str(raw.get("via")),
        description=_as_str(raw.get("description")),
        apply_url=_extract_apply_url(raw),
        serp_job_id=_as_str(raw.get("job_id")),
        extensions=_normalize_extensions(raw.get("extensions")),
    )


def iter_job_results(payload: Any) -> list[ParsedJob]:
    """Parse a whole response body into ParsedJobs (empty body → empty list).

    Args:
        payload: a full SerpApi response dict (or None/garbage).

    Returns:
        Parsed postings in order; items missing required fields are dropped.
        A body without ``jobs_results`` (the "no results" error body, or any
        unexpected shape) yields [] — zero postings is a valid outcome.
    """
    if not isinstance(payload, dict):
        return []
    raw_results = payload.get("jobs_results")
    if not isinstance(raw_results, list):
        return []
    jobs: list[ParsedJob] = []
    for raw in raw_results:
        parsed = parse_job_result(raw)
        if parsed is not None:
            jobs.append(parsed)
    return jobs


def detect_internship(title: str | None, extensions: list[str]) -> bool:
    """Return True when the title or any extension mentions an internship.

    Args:
        title: posting title (may be None — callers pass what they have).
        extensions: normalized extension strings (e.g. "Internship", "Full–time").

    Returns:
        True if ``\\bintern(ship)?s?\\b`` (case-insensitive) matches the title
        or any extension. The word boundaries stop "internal tools" and
        "international" from matching (plan 1.2.2).
    """
    for text in [title, *extensions]:
        if text and _INTERNSHIP_PATTERN.search(text):
            return True
    return False


def make_dedupe_key(title: str, company: str, location: str | None) -> str:
    """Compute the stable posting identity: sha1 of the normalized triple.

    Args:
        title: posting title.
        company: company name.
        location: location string, or None (treated as empty — the same job
            posted with and without a location dedupes together).

    Returns:
        A 40-char hex sha1 of ``title|company|location`` lowercased and stripped
        of every non-alphanumeric character. The SerpApi ``job_id`` is NOT used:
        it can change between fetches (plan 4.3), which would break idempotency.
    """

    def _normalize(text: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", "", (text or "").lower())

    normalized = "|".join((_normalize(title), _normalize(company), _normalize(location)))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def parse_next_page_token(payload: Any) -> str | None:
    """Extract ``serpapi_pagination.next_page_token`` from a response body.

    Args:
        payload: full SerpApi response dict.

    Returns:
        The opaque token string, or None when absent/blank/wrong shape — None
        always means "no further page" (AGENTS 3.4.8: pagination only via this
        token, never a ``start`` offset).
    """
    if not isinstance(payload, dict):
        return None
    pagination = payload.get("serpapi_pagination")
    if not isinstance(pagination, dict):
        return None
    token = pagination.get("next_page_token")
    if not isinstance(token, str) or not token.strip():
        return None
    return token


# =========================================================================
# Google Scholar parsers (Phase 2, plan 2.5.1) — same defensive contract as
# the job parsers: only ``title`` is required, everything else is optional.
# Scholar feeds QUALITATIVE research themes only. ``total_results`` is
# deliberately never read here (it is erratic across re-runs; AGENTS 3.4.9
# forbids computing trends from it).
# =========================================================================


@dataclass(frozen=True)
class ParsedPaper:
    """Typed internal representation of one Scholar organic result.

    Attributes:
        title: paper title (required; everything else may be None/empty).
        snippet: result snippet text (contains a date prefix in real data).
        link: article URL, or None.
        publication_summary: ``publication_info.summary`` free text (authors,
            venue, year — e.g. "J Smith - Phys Rev, 2025 - nature.com").
        year: last 19xx/20xx year found in the summary, else None.
        cited_by: citation count when present, else None. Stored but never
            used for trends (new papers have almost no citations; plan 1.5).
    """

    title: str
    snippet: str | None
    link: str | None
    publication_summary: str | None
    year: int | None
    cited_by: int | None


_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def parse_scholar_year(publication_summary: str | None) -> int | None:
    """Extract the publication year from a Scholar ``publication_info.summary``.

    Args:
        publication_summary: free text like ``"A Smith - Phys Rev, 2025 - nature.com"``.

    Returns:
        The LAST 4-digit year (19xx/20xx) found in the text, or None. The last
        match wins because summaries end with the source site, and some venue
        strings contain unrelated numbers earlier (e.g. "Phys Rev A 98, 012345").
    """
    if not publication_summary:
        return None
    matches = _YEAR_PATTERN.findall(publication_summary)
    if not matches:
        return None
    # findall returns the *group* ("19"/"20") per match; re-scan with spans to
    # recover full year strings, taking the one with the largest position.
    best: int | None = None
    for match in _YEAR_PATTERN.finditer(publication_summary):
        best = int(match.group(0))
    return best


def parse_scholar_result(raw: Any) -> ParsedPaper | None:
    """Parse one element of ``organic_results`` into a :class:`ParsedPaper`.

    Args:
        raw: one raw Scholar result dict (malformed items are logged and
            skipped, never raised — same policy as :func:`parse_job_result`).

    Returns:
        A ParsedPaper, or None when the item is not a dict or has no non-empty
        ``title``.
    """
    if not isinstance(raw, dict):
        logger.warning("skipping malformed scholar result (not an object): %r", raw)
        return None
    title = _as_str(raw.get("title"))
    if not title:
        logger.warning("skipping scholar result without title")
        return None

    publication_info = raw.get("publication_info")
    summary = (
        _as_str(publication_info.get("summary")) if isinstance(publication_info, dict) else None
    )

    inline_links = raw.get("inline_links")
    cited_by_total: int | None = None
    if isinstance(inline_links, dict):
        cited_by = inline_links.get("cited_by")
        if isinstance(cited_by, dict) and isinstance(cited_by.get("total"), int):
            cited_by_total = cited_by["total"]

    return ParsedPaper(
        title=title,
        snippet=_as_str(raw.get("snippet")),
        link=_as_str(raw.get("link")),
        publication_summary=summary,
        year=parse_scholar_year(summary),
        cited_by=cited_by_total,
    )


def iter_scholar_results(payload: Any) -> list[ParsedPaper]:
    """Parse a whole Scholar response body into ParsedPapers (empty → empty list).

    Args:
        payload: a full SerpApi response dict (or None/garbage).

    Returns:
        Parsed papers in order; items without a title are dropped. A body
        without ``organic_results`` (the "no results" error body, or any
        unexpected shape) yields [] — zero papers is a valid outcome.
    """
    if not isinstance(payload, dict):
        return []
    raw_results = payload.get("organic_results")
    if not isinstance(raw_results, list):
        return []
    papers: list[ParsedPaper] = []
    for raw in raw_results:
        parsed = parse_scholar_result(raw)
        if parsed is not None:
            papers.append(parsed)
    return papers
