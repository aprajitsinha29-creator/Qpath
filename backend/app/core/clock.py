"""Project-wide clock: one definition of "now" for timestamps in the database.

Why naive UTC: SQLite's ``DateTime`` columns store ISO strings *without*
offset (the ``timezone=True`` flag is a no-op there), so every value read back
is offset-naive. If some Python code used aware ``datetime.now(UTC)`` values,
comparisons between freshly assigned attributes and DB-loaded ones would raise
"can't compare offset-naive and offset-aware datetimes" (or silently
miscompare). The convention is therefore: **naive UTC in Python, naive UTC in
the database.** Values are UTC because every writer stamps ``utc_now()``.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime (see module docstring).

    Returns:
        ``datetime.now(UTC)`` with ``tzinfo`` stripped — i.e. the wall-clock
        UTC time, comparable with every value SQLite returns.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def utc_day_start() -> datetime:
    """Return midnight UTC of the current day (naive), for daily windows.

    Returns:
        Today's date at 00:00:00.000000 UTC (naive), e.g. for counting the
        day's live SerpApi calls or "new postings today" figures.
    """
    return utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
