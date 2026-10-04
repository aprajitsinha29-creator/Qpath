"""Logging setup — the single place that configures logging (AGENTS.md 3.3.6: no prints).

Modules obtain loggers with ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once, at the level requested by ``Settings.log_level``.

    Args:
        level: A level name such as ``"INFO"`` or ``"DEBUG"``.

    httpx/httpcore are pinned to WARNING because httpx logs full request URLs at
    DEBUG — in live mode that URL carries the SerpApi ``api_key`` query parameter,
    which must never be logged (AGENTS.md 3.4.5).
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
