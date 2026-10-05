"""Engine/session wiring: WAL SQLite, lazily created engine, FastAPI ``get_db`` dependency.

Sync everywhere (AGENTS.md 3.3.2): one synchronous engine and sessionmaker per
process. The engine is created on first use so tests can repoint ``DATABASE_URL``
(clearing the caches) before anything binds. Background jobs must open their own
session — never reuse a request session inside a thread (AGENTS.md 3.3.8).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Create the directory of a file-based SQLite URL before connecting.

    SQLite cannot create missing parent directories, so a fresh clone without
    ``backend/data/`` (which is gitignored) would otherwise fail at startup with
    the unhelpful "unable to open database file".
    """
    if not database_url.startswith("sqlite"):
        return
    # sqlite:///relative.db | sqlite:////absolute.db | sqlite:///:memory:
    path_text = database_url.split("///", 1)[-1]
    if not path_text or path_text == ":memory:":
        return
    Path(path_text).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide engine, created on first use from Settings."""
    settings = get_settings()
    _ensure_sqlite_parent_dir(settings.database_url)
    engine = create_engine(
        settings.database_url,
        # FastAPI runs sync endpoints in a worker thread, so SQLite handles must
        # be shareable across threads (AGENTS.md 3.3.8).
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
        """Apply per-connection pragmas: WAL, busy timeout and foreign keys."""
        # connection_record is unused; it is part of SQLAlchemy's connect-event signature.
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            # WAL allows concurrent readers with one writer, but a second
            # writer (e.g. the client's call-log session) must wait instead of
            # failing instantly with 'database is locked' when a refresh is
            # mid-transaction. 5 s covers every write in this app.
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    """Return the sessionmaker bound to :func:`get_engine` (cached with the engine)."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:
    """Create a session for non-request contexts (integrations, jobs, scripts).

    The caller owns the session: use ``with SessionLocal() as db:`` or call
    ``close()`` in a ``finally`` block.
    """
    return get_sessionmaker()()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: exactly one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that do not exist yet.

    Migrations are an intentional non-goal (AGENTS.md 3.3.8): schema changes are
    applied by dropping the dev database or by re-seeding.
    """
    # Importing the models registers them on Base.metadata before create_all.
    from app import models  # noqa: F401
    from app.db.base import Base

    Base.metadata.create_all(bind=get_engine())
