"""SerpApi client — the ONLY module allowed to talk to serpapi.com (AGENTS 3.4.1).

Two modes behind one ``search()``:

- **fixture mode** (``SERPAPI_USE_FIXTURES=true``): reads recorded JSON from
  ``backend/tests/fixtures/serpapi/<engine>__<slug>__<variant>.json``;
- **live mode**: ``GET https://serpapi.com/search.json`` with the ``api_key``
  passed only as a query parameter at call time, a 30 s timeout, one retry on
  timeout/5xx and never on 4xx; a body containing ``error`` raises
  :class:`SerpApiError` (except the "no results" message, which logs status
  "empty" and returns the body).

Every call — either mode — writes one ``serpapi_call_log`` row (engine, query,
source, status) which drives the daily cap and the UI's activity panel. The key
is never logged, never stored and never part of a fixture (AGENTS 3.4.5).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import utc_day_start
from app.core.config import Settings
from app.core.errors import FixtureMissingError, SerpApiCapExceeded, SerpApiError
from app.models import SerpApiCallLog

logger = logging.getLogger(__name__)

#: REST endpoint — plan 3.4.2: plain httpx, no SerpApi SDK.
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

#: Timeout in seconds (plan 3.4.6).
REQUEST_TIMEOUT_SECONDS = 30.0

#: Recorded fixtures live in backend/tests/fixtures/serpapi, resolved from this
#: file so it works from any working directory (tests override it with tmp_path).
DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "serpapi"


def slugify_query(query: str) -> str:
    """Turn a query into the fixture-file slug: lowercase, runs of non-alphanumerics become ``-``.

    Args:
        query: raw search text, e.g. ``"quantum error correction"``.

    Returns:
        A filesystem-safe slug, e.g. ``quantum-error-correction``.
    """
    return re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")


def fixture_file_name(engine: str, query: str, variant: str) -> str:
    """Return the fixture file name shared by the client and the recorder.

    Args:
        engine: SerpApi engine id (``google_jobs`` / ``google_scholar``).
        query: raw search text.
        variant: fixture variant (``global_p1``, ``india_p1``, ``recent``, ...).

    Returns:
        ``<engine>__<slug>__<variant>.json`` (plan 4.6 recording plan).
    """
    return f"{engine}__{slugify_query(query)}__{variant}.json"


def scrub_api_key(payload: Any) -> Any:
    """Recursively replace any ``api_key`` value inside a JSON payload with ``***``.

    Applied to everything written to disk (fixtures) so recordings can never
    carry credentials (AGENTS 3.4.5, 3.10.5).
    """
    if isinstance(payload, dict):
        return {
            key: "***" if key == "api_key" else scrub_api_key(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [scrub_api_key(item) for item in payload]
    return payload


def _scrub_text(text: str, api_key: str) -> str:
    """Remove the literal API key from text destined for logs or error messages."""
    if not api_key:
        return text
    return text.replace(api_key, "***")


#: Case-insensitive substring in error body indicating a valid query with no results.
NO_RESULTS_MESSAGE_SUBSTRING = "hasn't returned any results"


def is_empty_result(payload: dict[str, Any]) -> bool:
    """Return True if a SerpApi response body indicates a valid query with no results.

    SerpApi returns an ``error`` field with "Google hasn't returned any results
    for this query." when a query simply matches nothing.

    Args:
        payload: parsed JSON response body.

    Returns:
        True if the payload contains an error indicating no results, False otherwise.
    """
    error = payload.get("error")
    if error is None:
        return False
    return NO_RESULTS_MESSAGE_SUBSTRING in str(error).lower()


class SerpApiClient:
    """Synchronous SerpApi client: fixture mode, live mode, daily cap, call log.

    Args:
        settings: the cached Settings instance.
        db_session_factory: zero-arg callable returning a fresh Session; every
            log row opens and closes its own session (never a request session).
        http_client: optional httpx.Client — tests inject one built on
            ``httpx.MockTransport``; otherwise a client with a 30 s timeout is
            created and owned by this instance.
        fixture_dir: override of the fixtures directory (tests use ``tmp_path``).

    Raises:
        FixtureMissingError: in fixture mode when the recording is absent.
        SerpApiCapExceeded: in live mode when today's cap is spent.
        SerpApiError: live transport, HTTP or API-level failures.
    """

    def __init__(
        self,
        settings: Settings,
        db_session_factory: Callable[[], Session],
        http_client: httpx.Client | None = None,
        fixture_dir: Path | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = db_session_factory
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        self._fixture_dir = fixture_dir or DEFAULT_FIXTURE_DIR

    def close(self) -> None:
        """Close the internal httpx.Client (a client passed in is left to its owner)."""
        if self._owns_http:
            self._http.close()

    def search(
        self, engine: str, params: dict[str, Any], *, fixture_variant: str
    ) -> dict[str, Any]:
        """Run one search in the configured mode and return the raw response body.

        Args:
            engine: SerpApi engine id (``google_jobs`` / ``google_scholar``).
            params: engine parameters such as ``q`` — never contains ``api_key``.
            fixture_variant: fixture file variant (ignored in live mode).

        Returns:
            The parsed response body as a dict.

        Raises:
            FixtureMissingError: fixture mode and the file does not exist —
                callers treat it as "no more data" and log it.
            SerpApiCapExceeded: live mode and today's call cap is spent.
            SerpApiError: transport, HTTP or API-level failure in live mode.
        """
        if self._settings.serpapi_use_fixtures:
            return self._read_fixture(engine, params, fixture_variant)
        return self._live_search(engine, params)

    def search_jobs(
        self,
        query: str,
        *,
        location: str | None = None,
        gl: str | None = None,
        next_page_token: str | None = None,
        fixture_variant: str,
    ) -> dict[str, Any]:
        """Run one Google Jobs search (``engine=google_jobs``).

        Args:
            query: the search text.
            location: human location (e.g. ``"India"``); mutually exclusive with
                ``uule`` — we never send ``uule`` (AGENTS 3.4.8).
            gl: country code paired with ``location``.
            next_page_token: token from ``serpapi_pagination.next_page_token``
                of the previous page — never a ``start`` offset (AGENTS 3.4.8).
            fixture_variant: fixture variant name for fixture mode.

        Returns:
            The parsed Google Jobs response body.
        """
        params: dict[str, Any] = {"q": query, "hl": "en"}
        if location is not None:
            params["location"] = location
        if gl is not None:
            params["gl"] = gl
        if next_page_token is not None:
            params["next_page_token"] = next_page_token
        return self.search("google_jobs", params, fixture_variant=fixture_variant)

    def search_scholar(
        self,
        query: str,
        *,
        num: int = 20,
        recent_only: bool = True,
        fixture_variant: str,
    ) -> dict[str, Any]:
        """Run one Google Scholar search (``engine=google_scholar``).

        Args:
            query: the search text.
            num: results per page (Scholar caps at 20 — plan 1.5).
            recent_only: adds ``scisbd=1`` ("added in the last year, sorted by
                date") for qualitative recency — never used for trend counts.
            fixture_variant: fixture variant name for fixture mode.

        Returns:
            The parsed Google Scholar response body.
        """
        params: dict[str, Any] = {"q": query, "hl": "en", "num": num}
        if recent_only:
            params["scisbd"] = "1"
        return self.search("google_scholar", params, fixture_variant=fixture_variant)

    # ------------------------------------------------------------------ fixture mode

    def _read_fixture(
        self, engine: str, params: dict[str, Any], fixture_variant: str
    ) -> dict[str, Any]:
        """Load a recorded response from disk and log the attempt.

        Raises:
            FixtureMissingError: the recording does not exist.
            SerpApiError: the recording exists but is not a JSON object.
        """
        query = str(params.get("q", ""))
        path = self._fixture_dir / fixture_file_name(engine, query, fixture_variant)
        if not path.is_file():
            self._log_call(engine, query, "fixture", "missing")
            raise FixtureMissingError(f"fixture not found: {path.name}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._log_call(engine, query, "fixture", "error")
            raise SerpApiError(f"fixture {path.name} is not valid JSON") from exc
        if not isinstance(payload, dict):
            self._log_call(engine, query, "fixture", "error")
            raise SerpApiError(f"fixture {path.name} must contain a JSON object")
        self._log_call(engine, query, "fixture", "ok")
        return payload

    # -------------------------------------------------------------------- live mode

    def _ensure_within_daily_cap(self) -> None:
        """Count today's (UTC) live calls and raise when the cap is reached.

        Counting uses the call log, so fixture calls and yesterday's live calls
        never consume credits (plan 3.4.3). Timestamps are naive UTC (see
        app.core.clock), so the naive day_start compares correctly.
        """
        day_start: datetime = utc_day_start()
        with self._session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(SerpApiCallLog)
                .where(
                    SerpApiCallLog.source == "live",
                    SerpApiCallLog.created_at >= day_start,
                )
            )
        spent = int(count or 0)
        cap = self._settings.serpapi_daily_call_cap
        if spent >= cap:
            raise SerpApiCapExceeded(
                f"Daily live SerpApi cap reached: {spent}/{cap} calls today (UTC)"
            )

    def _get_with_retry(self, params: dict[str, Any]) -> httpx.Response:
        """GET the endpoint, retrying once on timeout or 5xx — never on 4xx.

        Args:
            params: full query params including ``engine`` and ``api_key``.

        Returns:
            A successful (2xx/3xx) response.

        Raises:
            SerpApiError: after a second timeout, on any 4xx/5xx, or on
                connection-level failures (no retry).
        """
        for attempt in (1, 2):
            try:
                response = self._http.get(SERPAPI_ENDPOINT, params=params)
            except httpx.TimeoutException as exc:
                if attempt == 1:
                    logger.warning(
                        "serpapi timeout, retrying once (engine=%s)",
                        params.get("engine"),
                    )
                    continue
                raise SerpApiError(
                    f"SerpApi request timed out twice ({REQUEST_TIMEOUT_SECONDS:.0f}s timeout)"
                ) from exc
            except httpx.RequestError as exc:
                # Only the exception type is used: httpx messages can embed the
                # request URL, which would carry the api_key (AGENTS 3.4.5).
                raise SerpApiError(f"SerpApi connection failed ({type(exc).__name__})") from exc

            if response.status_code >= 500:
                if attempt == 1:
                    logger.warning(
                        "serpapi server error %d, retrying once (engine=%s)",
                        response.status_code,
                        params.get("engine"),
                    )
                    continue
                raise SerpApiError(
                    f"SerpApi server error after retry (HTTP {response.status_code})"
                )
            if response.status_code >= 400:
                # Never retry 4xx (AGENTS 3.4.6): the request itself is wrong.
                raise SerpApiError(f"SerpApi rejected the request (HTTP {response.status_code})")
            return response
        raise SerpApiError("SerpApi request failed after retry")  # pragma: no cover

    def _live_search(self, engine: str, params: dict[str, Any]) -> dict[str, Any]:
        """Run a live call: cap check, request, body validation, one log row.

        Raises:
            SerpApiCapExceeded: cap already spent (logged as no call was made).
            SerpApiError: transport/HTTP/API failures (logged with status error).
        """
        # Settings' validator guarantees a key in live mode (fail fast at startup).
        api_key = self._settings.serpapi_api_key
        query = str(params.get("q", ""))
        self._ensure_within_daily_cap()

        response = self._get_with_retry({**params, "engine": engine, "api_key": api_key})
        try:
            body = response.json()
        except ValueError as exc:
            self._log_call(engine, query, "live", "error")
            raise SerpApiError("SerpApi returned a non-JSON body") from exc

        if not isinstance(body, dict):
            self._log_call(engine, query, "live", "error")
            raise SerpApiError("SerpApi returned an unexpected JSON payload")
        if "error" in body:
            if is_empty_result(body):
                self._log_call(engine, query, "live", "empty")
                return body
            message = _scrub_text(str(body["error"]), api_key)
            self._log_call(engine, query, "live", "error")
            raise SerpApiError(f"SerpApi error: {message}")

        self._log_call(engine, query, "live", "ok")
        return body

    # ---------------------------------------------------------------------- logging

    def _log_call(self, engine: str, query: str, source: str, status: str) -> None:
        """Write one ``serpapi_call_log`` row (never the API key, AGENTS 3.4.4/5)."""
        session = self._session_factory()
        try:
            session.add(
                SerpApiCallLog(
                    engine=engine,
                    query=query[:512],
                    source=source,
                    status=status,
                )
            )
            session.commit()
        finally:
            session.close()
