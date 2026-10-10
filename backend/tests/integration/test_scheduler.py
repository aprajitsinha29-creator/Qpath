"""Scheduler tests (tests 26-33): registration, failure rows, overlap, cap, shutdown.

No scheduler ever runs against the network: job wrappers are driven with
injected fakes (fake session factory counting sessions, fake client raising,
no-op LLM), and only the registration/lifespan behavior touches a real
BackgroundScheduler instance (cron jobs are inspected, never executed).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import SerpApiCapExceeded
from app.models import RefreshRun
from app.scheduler import jobs as scheduler_jobs

pytestmark = [pytest.mark.usefixtures("_seed_reference_data")]


class FakeClient:
    """Stands in for SerpApiClient; configurable failure for cap/busy tests."""

    def __init__(self, exc: Exception | None = None) -> None:
        self.calls = 0
        self.exc = exc


class FakeLLM:
    """Minimal StructuredLLM stand-in: never called in these tests."""

    def generate_structured(self, prompt: str, schema: Any) -> Any:  # pragma: no cover
        raise AssertionError("LLM must not be called in scheduler tests")


class RecordingSessionFactory:
    """Session factory that opens real sessions AND records how many it opened.

    Backs test 31 (each job uses its own session via the factory).
    """

    def __init__(self, real: sessionmaker[Session]) -> None:
        self._real = real
        self.opened: list[Session] = []

    def __call__(self) -> Session:
        session = self._real()
        self.opened.append(session)
        return session


@pytest.fixture()
def session_recorder(db_session: Session) -> RecordingSessionFactory:
    """A recording factory wrapping the per-test sessionmaker."""
    from app.db.session import get_sessionmaker

    get_sessionmaker.cache_clear()  # bind a fresh maker to this test's DB
    return RecordingSessionFactory(get_sessionmaker())


# ---------------------------------------------------------------------------
# Test 26/27: registration reflects env flags
# ---------------------------------------------------------------------------


def test_scheduler_disabled_by_default(client: TestClient) -> None:
    """Test 26: SCHEDULER_ENABLED=false -> the lifespan creates no scheduler."""
    # `client` runs the real lifespan with _clean_env (no SCHEDULER_ENABLED),
    # so the module-level hook must still be None after startup.
    from app import main as main_module

    assert main_module._scheduler is None


def test_scheduler_registers_three_jobs_from_env(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 27: enabled -> exactly 3 jobs with crons taken from env."""
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("JOBS_DAILY_CRON", "30 2 * * *")
    monkeypatch.setenv("JOBS_INDIA_WEEKLY_CRON", "15 4 * * 1")
    monkeypatch.setenv("SCHOLAR_WEEKLY_CRON", "45 5 * * 1")
    get_settings.cache_clear()
    try:
        with TestClient(client.app) as running:
            from app import main as main_module

            scheduler = main_module._scheduler
            assert scheduler is not None
            job_list = scheduler.get_jobs()
            assert len(job_list) == 3
            by_id = {job.id: job for job in job_list}
            assert set(by_id) == {"jobs_daily_global", "jobs_weekly_india", "scholar_weekly"}
            # "2" (hour) and "30" (minute) from env, not the config default.
            daily_trigger = str(by_id["jobs_daily_global"].trigger)
            assert "hour='2'" in daily_trigger
            assert "minute='30'" in daily_trigger
            assert running is not None
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 28: a job raising writes a failed refresh_runs row, does not propagate
# ---------------------------------------------------------------------------


def test_job_failure_writes_failed_run_row(session_recorder: RecordingSessionFactory) -> None:
    """Test 28: no exception escapes; one failed refresh_runs row appears."""
    boom = RuntimeError("serpapi returned 500 for query qec")

    # The client raises the moment refresh_jobs asks it for a page.
    class ExplodingClient(FakeClient):
        def __getattr__(self, name: str) -> Any:
            raise boom

    scheduler_jobs.scheduled_daily_global_jobs(
        session_recorder, ExplodingClient(), FakeLLM()
    )  # must NOT raise

    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        rows = db.scalars(select(RefreshRun).where(RefreshRun.kind == "jobs")).all()
        assert len(rows) == 1
        assert rows[0].status == "failed"
        assert "serpapi returned 500" in (rows[0].error or "")
        # No secrets in the stored error (test 28 + 25 invariant).
        assert "api_key" not in (rows[0].error or "")


def test_job_failure_error_text_is_scrubbed(session_recorder: RecordingSessionFactory) -> None:
    """Error text containing a key-looking parameter never reaches storage."""
    boom = RuntimeError("GET https://serpapi.com/search.json?api_key=SECRET123&engine=google_jobs")

    class ExplodingClient(FakeClient):
        def __getattr__(self, name: str) -> Any:
            raise boom

    scheduler_jobs.scheduled_weekly_india_jobs(session_recorder, ExplodingClient())
    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        rows = db.scalars(
            select(RefreshRun).where(RefreshRun.kind == "jobs").order_by(RefreshRun.id.desc())
        ).all()
        assert rows, "a failed run row must exist"
        stored = rows[0].error or ""
        assert "SECRET123" not in stored
        assert "https" not in stored


# ---------------------------------------------------------------------------
# Test 29: overlapping runs prevented
# ---------------------------------------------------------------------------


def test_overlapping_runs_prevented() -> None:
    """Test 29: while a run holds its claim, a second invocation is skipped."""
    job_id = "jobs_daily_global"
    scheduler_jobs.release_job_run(job_id)  # clean slate
    try:
        assert scheduler_jobs.claim_job_run(job_id) is True
        assert scheduler_jobs.claim_job_run(job_id) is False  # held by the lock
    finally:
        scheduler_jobs.release_job_run(job_id)
    assert scheduler_jobs.claim_job_run(job_id) is True  # released -> claimable
    scheduler_jobs.release_job_run(job_id)
    assert not scheduler_jobs._OVERLAP_LOCKS


# ---------------------------------------------------------------------------
# Test 30: daily cap reached -> no live calls, run recorded
# ---------------------------------------------------------------------------


def test_job_stops_at_daily_cap(
    session_recorder: RecordingSessionFactory, db_session: Session
) -> None:
    """Test 30: SerpApiCapExceeded stops the job with NO live SerpApi calls
    (cap enforced pre-call) and a refresh_runs row records the outcome."""
    from app.db.session import get_sessionmaker

    class CapAwareClient(FakeClient):
        """Raises cap-exceeded before every call once the budget is spent."""

        def __init__(self) -> None:
            super().__init__()

        def __getattr__(self, name: str) -> Any:
            # A prior run left the daily call budget spent (60 == default cap).
            raise SerpApiCapExceeded("daily call cap reached (60/60)")

    with get_sessionmaker()() as db:
        db.add(
            RefreshRun(
                kind="jobs",
                mode="daily",
                status="partial",
                serpapi_calls=60,
                finished_at=datetime(2026, 1, 1, 3, 0, 0),
            )
        )
        db.commit()

    # The job must complete WITHOUT propagating: ingestion collects the
    # per-query cap failures, records a partial run with zero serpapi_calls
    # (the cap is enforced pre-call), and no LLM extraction happens on empty data.
    scheduler_jobs.scheduled_daily_global_jobs(session_recorder, CapAwareClient(), FakeLLM())

    with get_sessionmaker()() as db:
        runs = db.scalars(
            select(RefreshRun).order_by(RefreshRun.started_at.desc(), RefreshRun.id.desc())
        ).all()
        today_runs = [r for r in runs if r.started_at.year == 2026 and r.serpapi_calls == 0]
        assert today_runs, "a zero-call run must be recorded"
        # The cap errors are captured in the run details, never raised out.
        joined = " ".join(str(e) for r in today_runs for e in (r.details or {}).get("errors", []))
        assert "cap" in joined


# ---------------------------------------------------------------------------
# Test 31: each job opens its OWN session via the given factory
# ---------------------------------------------------------------------------


def test_job_uses_distinct_sessions_from_factory(
    session_recorder: RecordingSessionFactory,
) -> None:
    """Test 31: the wrapper and the failure recorder each open fresh sessions."""

    class QuietClient(FakeClient):
        def __getattr__(self, name: str) -> Any:
            raise RuntimeError("x")

    before = len(session_recorder.opened)
    scheduler_jobs.scheduled_daily_global_jobs(session_recorder, QuietClient(), FakeLLM())
    after_main = len(session_recorder.opened)
    scheduler_jobs.scheduled_weekly_scholar(session_recorder, QuietClient(), FakeLLM())
    after_scholar = len(session_recorder.opened)
    # At least: the jobs' work session + one failure-recording session each.
    assert after_main - before >= 2
    assert after_scholar - after_main >= 2
    # All opened sessions are distinct objects (never a shared/request one).
    assert len({id(s) for s in session_recorder.opened}) == len(session_recorder.opened)


# ---------------------------------------------------------------------------
# Test 32: app shutdown stops the scheduler cleanly
# ---------------------------------------------------------------------------


def test_app_shutdown_stops_scheduler(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test 32: TestClient context exit runs scheduler.shutdown()."""
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    get_settings.cache_clear()
    from app import main as main_module

    stopped: list[bool] = []

    class SpyScheduler:
        def start(self) -> None:
            pass

        def shutdown(self, wait: bool = False) -> None:
            stopped.append(True)

        def get_jobs(self) -> list[Any]:
            return []

    import app.scheduler.jobs as jobs_module

    real_build = jobs_module.build_scheduler
    try:
        jobs_module.build_scheduler = lambda *a, **k: SpyScheduler()  # type: ignore[assignment]
        main_module._scheduler = None
        with TestClient(client.app):
            pass
        assert stopped == [True]
        assert main_module._scheduler is None
    finally:
        jobs_module.build_scheduler = real_build  # type: ignore[assignment]
        main_module._scheduler = None
        get_settings.cache_clear()


def test_cron_fields_are_parsed_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cron strings come from Settings only; malformed input raises."""
    monkeypatch.setenv("JOBS_DAILY_CRON", "30 2 * * *")
    get_settings.cache_clear()
    try:
        parsed = scheduler_jobs._fmt_cron(get_settings().jobs_daily_cron)
        assert parsed == {
            "minute": "30",
            "hour": "2",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }
    finally:
        get_settings.cache_clear()
    with pytest.raises(ValueError):
        scheduler_jobs._fmt_cron("0 3 * *")  # 4 fields is malformed
