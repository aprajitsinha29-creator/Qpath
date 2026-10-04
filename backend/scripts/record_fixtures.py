"""One-off live recorder for SerpApi fixtures (plan step 0.5, manual task M-06).

Run from the repo root with ``make record-fixtures`` (add ``ARGS=--force`` to
overwrite). It walks ``FIXTURE_PLAN`` against the **live** API — so it requires
``SERPAPI_USE_FIXTURES=false`` and ``SERPAPI_API_KEY`` in ``backend/.env`` and
refuses otherwise. It prints a credit estimate, asks ``y/N``, saves each
response pretty-printed under ``backend/tests/fixtures/serpapi/`` using the
same file naming as the client, scrubs ``api_key`` from everything it writes,
skips existing files unless ``--force``, and summarizes at the end.

Output goes through ``logging`` (AGENTS.md 3.3.6 forbids ``print``); the
``input()`` prompt is the only direct stdout write.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import setup_logging
from app.db.session import SessionLocal, init_db
from app.integrations.serpapi.client import (
    SerpApiClient,
    fixture_file_name,
    is_empty_result,
    scrub_api_key,
)
from app.integrations.serpapi.queries import FIXTURE_PLAN, FixtureSpec, estimate_fixture_calls

logger = logging.getLogger(__name__)

#: Where recordings are written — the same directory the client reads in
#: fixture mode (backend/tests/fixtures/serpapi), resolved from this file.
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "serpapi"


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line argument parser for the recorder."""
    parser = argparse.ArgumentParser(
        description="Record live SerpApi fixtures for offline development (spends credits)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite fixture files that already exist",
    )
    return parser


def _next_page_token(payload: dict[str, Any] | None, path: Path) -> str | None:
    """Extract ``serpapi_pagination.next_page_token`` from a fresh or saved page 1.

    Args:
        payload: the just-recorded response, or None when the file was skipped.
        path: page-1 fixture file, read when the payload is unavailable.

    Returns:
        The token, or None when pagination offers no next page (AGENTS 3.4.8:
        the old ``start`` offset must never be used).
    """
    source = payload
    if source is None and path.is_file():
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.error("could not re-read %s to follow pagination", path.name)
            return None
    if not isinstance(source, dict):
        return None
    pagination = source.get("serpapi_pagination")
    if not isinstance(pagination, dict):
        return None
    token = pagination.get("next_page_token")
    return str(token) if token else None


def _record_one(
    client: SerpApiClient,
    spec: FixtureSpec,
    *,
    variant: str,
    next_page_token: str | None,
    force: bool,
) -> tuple[str, dict[str, Any] | None, Path]:
    """Record (or skip) one fixture file for the given plan entry.

    Args:
        client: live-mode SerpApiClient (every call is logged to the DB).
        spec: the plan entry providing engine/query/location.
        variant: fixture variant for this file (``global_p1`` or ``global_p2``).
        next_page_token: token for follow-up pages, else None.
        force: overwrite an existing file.

    Returns:
        ``(status, payload, path)`` with status
        ``recorded``/``recorded (empty)``/``skipped``/``failed``;
        payload is only present when freshly recorded.
    """
    path = FIXTURE_DIR / fixture_file_name(spec.engine, spec.query, variant)
    if path.is_file() and not force:
        logger.info("skip (exists): %s", path.name)
        return "skipped", None, path
    try:
        if spec.engine == "google_jobs":
            payload = client.search_jobs(
                spec.query,
                location=spec.location,
                gl=spec.gl,
                next_page_token=next_page_token,
                fixture_variant=variant,
            )
        else:
            payload = client.search_scholar(spec.query, fixture_variant=variant)
    except AppError as exc:
        logger.error("failed: %s (%s: %s)", path.name, type(exc).__name__, exc)
        return "failed", None, path

    path.parent.mkdir(parents=True, exist_ok=True)
    # Scrub defensively: recordings must never contain credentials (AGENTS 3.4.5).
    path.write_text(
        json.dumps(scrub_api_key(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if is_empty_result(payload):
        logger.info("saved (empty): %s", path.name)
        return "recorded (empty)", payload, path
    logger.info("saved: %s", path.name)
    return "recorded", payload, path


def main(argv: list[str] | None = None) -> int:
    """CLI entry: record every missing fixture in ``FIXTURE_PLAN``.

    Args:
        argv: argument list; defaults to ``sys.argv[1:]``.

    Returns:
        Exit code — 0 on success or user abort, 1 on refusal or failed entries.
    """
    args = build_parser().parse_args(argv)
    try:
        settings = get_settings()
    except ValidationError as exc:
        # Settings' live-mode fail-fast (e.g. fixtures off with an empty key).
        logger.error("configuration problem: %s", exc)
        return 1
    setup_logging(settings.log_level)

    if settings.serpapi_use_fixtures or not settings.serpapi_api_key:
        logger.error(
            "refusing to record: live mode required — set SERPAPI_USE_FIXTURES=false "
            "and SERPAPI_API_KEY in backend/.env (manual task M-03), then rerun"
        )
        return 1

    logger.info(
        "credit estimate: up to %d live SerpApi calls in this run",
        estimate_fixture_calls(),
    )
    if input("Proceed? [y/N] ").strip().lower() not in {"y", "yes"}:
        logger.info("aborted — nothing recorded")
        return 0

    init_db()  # serpapi_call_log must exist: every live call is logged (AGENTS 3.4.4)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    client = SerpApiClient(settings, SessionLocal, fixture_dir=FIXTURE_DIR)
    counts: dict[str, int] = {
        "recorded": 0,
        "recorded (empty)": 0,
        "skipped": 0,
        "failed": 0,
    }
    try:
        for spec in FIXTURE_PLAN:
            status, payload, path = _record_one(
                client, spec, variant=spec.variant, next_page_token=None, force=args.force
            )
            counts[status] += 1
            if not spec.follow_next_page or not spec.next_page_variant:
                continue
            token = _next_page_token(payload, path)
            if token is None:
                logger.warning(
                    "no next_page_token for %r — skipping %s page 2",
                    spec.query,
                    spec.variant,
                )
                continue
            page_status, _, _ = _record_one(
                client,
                spec,
                variant=spec.next_page_variant,
                next_page_token=token,
                force=args.force,
            )
            counts[page_status] += 1
    finally:
        client.close()

    logger.info(
        "summary: %d recorded, %d recorded (empty), %d skipped (already present), %d failed",
        counts["recorded"],
        counts["recorded (empty)"],
        counts["skipped"],
        counts["failed"],
    )
    if counts["failed"]:
        logger.error("some recordings failed — rerun after fixing; existing files are skipped")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
