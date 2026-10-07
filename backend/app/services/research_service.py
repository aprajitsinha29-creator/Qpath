"""Research service: Scholar ingestion + Gemini research themes (plan 2.5).

Phase 2 step 2.5. One ``refresh_scholar`` run walks the
:data:`SCHOLAR_QUERY_PLAN` (one query per subfield, ``scisbd=1``, ``num=20``),
stores the parsed papers as a new ``paper_snapshots`` batch, then asks the
injected :class:`StructuredLLM` for **qualitative themes** over those papers.

Honesty rules (AGENTS 3.4.9 / plan 1.5): ``search_information.total_results``
is never read — Scholar totals are erratic and this project computes **no
counts, growth rates or trends** from Scholar. Themes cite papers by snapshot
id; every theme without at least one valid paper pointer is dropped, and a
subfield with zero results (or a failed theme call) is recorded in the run's
``details["errors"]`` — an empty state, never a raised HTTP error.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import AppError
from app.integrations.gemini.client import StructuredLLM
from app.integrations.gemini.prompts import RESEARCH_THEMES_PROMPT
from app.integrations.gemini.schemas import ThemeSet
from app.integrations.serpapi.client import SerpApiClient
from app.integrations.serpapi.parsers import iter_scholar_results
from app.integrations.serpapi.queries import SCHOLAR_QUERY_PLAN, SCHOLAR_RECENT
from app.models import PaperSnapshot, RefreshRun, ResearchTheme

logger = logging.getLogger(__name__)

#: Papers per theme prompt (plan 4.7: ≤ 20; the query already asks num=20).
THEME_PAPER_LIMIT = 20

#: Valid themes per subfield (plan 4.7: 3–5 asked; keep whatever validates).
MIN_THEMES_PER_SUBFIELD = 3
MAX_THEMES_PER_SUBFIELD = 5


def _generate_batch_id(now: datetime) -> str:
    """Return a fresh opaque batch id (uuid4 hex, 32 chars — fits String(32))."""
    return uuid.uuid4().hex


def _render_papers(papers: list[PaperSnapshot]) -> str:
    """Render papers as ``[index] title — snippet`` blocks (plan 4.7)."""
    lines = []
    for index, paper in enumerate(papers, start=1):
        snippet = (paper.snippet or "").strip()
        if snippet:
            lines.append(f"[{index}] {paper.title} — {snippet}")
        else:
            lines.append(f"[{index}] {paper.title}")
    return "\n".join(lines)


def _resolve_theme_paper_ids(paper_indexes: list[int], papers: list[PaperSnapshot]) -> list[int]:
    """Map 1-based LLM paper indexes onto snapshot ids; drop out-of-range ones.

    Args:
        paper_indexes: indexes as returned by the model (1-based, plan 4.7).
        papers: the batch listing the indexes point into.

    Returns:
        Snapshot ids for every index within ``1..len(papers)``, in given order,
        deduplicated. Invalid indexes are dropped (never crash, AGENTS 3.5.3).
    """
    resolved: list[int] = []
    for index in paper_indexes:
        if not isinstance(index, int) or not 1 <= index <= len(papers):
            continue
        snapshot_id = papers[index - 1].id
        if snapshot_id not in resolved:
            resolved.append(snapshot_id)
    return resolved


def _validate_theme_set(
    theme_set: ThemeSet, papers: list[PaperSnapshot]
) -> list[dict[str, object]]:
    """Apply the plan 4.7 theme post-validation: range-check, drop empty, cap.

    Args:
        theme_set: the schema-validated model output.
        papers: the batch the indexes refer to.

    Returns:
        Theme dicts ``{label, summary, paper_ids}`` ready for the JSON column.
        Themes with no valid paper pointer are dropped; more than
        :data:`MAX_THEMES_PER_SUBFIELD` valid themes are truncated to keep the
        UI contract stable (the prompt asks for 3–5, but is not trusted).
    """
    valid: list[dict[str, object]] = []
    for theme in theme_set.themes:
        paper_ids = _resolve_theme_paper_ids(theme.paper_indexes, papers)
        if not paper_ids:
            logger.info("dropping theme %r: no valid paper indexes", theme.label)
            continue
        valid.append(
            {"label": theme.label.strip(), "summary": theme.summary.strip(), "paper_ids": paper_ids}
        )
    return valid[:MAX_THEMES_PER_SUBFIELD]


def _refresh_one_subfield(
    db: Session,
    client: SerpApiClient,
    llm: StructuredLLM,
    *,
    subfield_id: str,
    query: str,
    batch_id: str,
    now: datetime,
) -> dict[str, object]:
    """Fetch papers for one subfield and generate its themes.

    Args:
        db: the run's session.
        client: SerpApi client in fixture or live mode.
        llm: injected structured LLM.
        subfield_id: subfield this query belongs to.
        query: Scholar query text (from SCHOLAR_QUERY_PLAN).
        batch_id: the run's batch id.
        now: run timestamp stamped on rows.

    Returns:
        ``{"papers": n, "themes": n, "error": str | None}`` — ``themes`` is 0
        when generation failed; ``error`` carries a short reason then.
    """
    try:
        payload = client.search_scholar(
            query, num=THEME_PAPER_LIMIT, fixture_variant=SCHOLAR_RECENT
        )
    except AppError as exc:
        # Fixture missing (no recording for this subfield) or a live API
        # failure: the subfield simply gets no themes this run (plan 2.5.3).
        logger.warning("scholar fetch failed for %s: %s", subfield_id, exc.code)
        return {"papers": 0, "themes": 0, "error": f"{subfield_id}: {exc.code}: {exc.message}"}

    parsed = iter_scholar_results(payload)
    snapshots: list[PaperSnapshot] = []
    for paper in parsed:
        snapshot = PaperSnapshot(
            subfield_id=subfield_id,
            batch_id=batch_id,
            query=query,
            title=paper.title,
            snippet=paper.snippet,
            link=paper.link,
            publication_summary=paper.publication_summary,
            year=paper.year,
            cited_by=paper.cited_by,
            fetched_at=now,
        )
        db.add(snapshot)
        snapshots.append(snapshot)
    db.flush()  # assign snapshot ids before themes reference them
    logger.info("scholar: stored %d papers for %s", len(parsed), subfield_id)

    if not parsed:
        # Zero results is a valid outcome (empty state, not an error).
        return {"papers": 0, "themes": 0, "error": None}

    try:
        theme_set = llm.generate_structured(
            RESEARCH_THEMES_PROMPT.format(papers=_render_papers(snapshots)), ThemeSet
        )
    except Exception as exc:  # noqa: BLE001 - recorded per subfield, run continues
        logger.warning(
            "theme generation failed for %s: %s (%s)", subfield_id, type(exc).__name__, exc
        )
        return {
            "papers": len(parsed),
            "themes": 0,
            "error": f"{subfield_id}: llm_output_error: {exc}",
        }

    themes = _validate_theme_set(theme_set, snapshots)
    db.add(
        ResearchTheme(
            subfield_id=subfield_id,
            batch_id=batch_id,
            themes=themes,
            generated_at=now,
            model=llm_model_name(),
        )
    )
    return {"papers": len(parsed), "themes": len(themes), "error": None}


def llm_model_name() -> str:
    """Return the configured Gemini model name for the research_themes audit column.

    Settings are the only source (AGENTS 3.3.3); empty string when unconfigured
    (can only happen with the fake in tests — the endpoint requires config).
    """
    from app.core.config import get_settings

    return get_settings().gemini_model or "unknown"


def refresh_scholar(
    db: Session,
    client: SerpApiClient,
    llm: StructuredLLM,
    subfield_ids: list[str] | None = None,
) -> RefreshRun:
    """Run one Scholar refresh (papers + themes) and persist a RefreshRun.

    Args:
        db: session for the whole run.
        client: SerpApi client (fixture or live).
        llm: injected structured LLM for theme generation.
        subfield_ids: optional restriction to a subset of subfields.

    Returns:
        The persisted ``refresh_runs`` row (kind="scholar"); ``details`` carries
        ``papers_stored``, ``subfields_refreshed``, ``subfields_with_themes``
        and per-subfield ``errors``.

    Side effects:
        Writes ``paper_snapshots``, up to one ``research_themes`` row per
        subfield, and one ``refresh_runs`` row; commits per subfield so a
        partial failure cannot lose earlier work (same policy as ingestion).
    """
    now = utc_now()
    batch_id = _generate_batch_id(now)

    wanted = set(subfield_ids) if subfield_ids else None
    specs = [spec for spec in SCHOLAR_QUERY_PLAN if wanted is None or spec.subfield_id in wanted]

    papers_total = themes_total = refreshed = with_themes = 0
    errors: list[str] = []
    for spec in specs:
        result = _refresh_one_subfield(
            db,
            client,
            llm,
            subfield_id=spec.subfield_id,
            query=spec.query,
            batch_id=batch_id,
            now=now,
        )
        papers_total += int(result["papers"])
        themes_total += int(result["themes"])
        if result["themes"]:
            with_themes += 1
        if result["error"]:
            errors.append(str(result["error"]))
        else:
            refreshed += 1
        db.commit()

    run = RefreshRun(kind="scholar", mode="weekly", started_at=now, details={})
    run.finished_at = utc_now()
    run.status = "partial" if errors else "done"
    run.serpapi_calls = len(specs)
    run.details = {
        "batch_id": batch_id,
        "papers_stored": papers_total,
        "themes_generated": themes_total,
        "subfields_refreshed": refreshed,
        "subfields_with_themes": with_themes,
        "errors": errors,
    }
    db.add(run)
    db.commit()
    logger.info(
        "refresh_scholar: %d papers, %d themes, %d errors", papers_total, themes_total, len(errors)
    )
    return run


def latest_themes_by_subfield(db: Session, subfield_id: str) -> list[dict[str, object]]:
    """Return the themes of the newest batch for a subfield (empty when none).

    Args:
        db: request session.
        subfield_id: subfield to look up.

    Returns:
        The ``themes`` JSON list of the latest ``research_themes`` row, or [].
        Older batches stay in the table as history but are never served.
    """
    row = db.scalar(
        select(ResearchTheme)
        .where(ResearchTheme.subfield_id == subfield_id)
        .order_by(ResearchTheme.generated_at.desc(), ResearchTheme.id.desc())
        .limit(1)
    )
    return list(row.themes or []) if row else []
