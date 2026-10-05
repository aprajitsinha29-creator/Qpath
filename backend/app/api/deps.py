"""Shared FastAPI dependencies: admin-token guard (plan 1.5, AGENTS 3.10.1).

Admin endpoints (refresh, and Phase 2's extract/scholar) require the
``X-Admin-Token`` header to match ``Settings.admin_token`` compared with
``secrets.compare_digest`` — constant-time, so response timing cannot leak
the token character by character. The dev-only token is typed into the UI and
kept in sessionStorage (AGENTS 3.6.7); it is never stored server-side.
"""

from __future__ import annotations

import secrets

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import AppError


class AdminAuthError(AppError):
    """The X-Admin-Token header is missing or wrong (401)."""

    code = "unauthorized"
    status_code = 401


def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """FastAPI dependency: reject the request unless the admin token matches.

    Args:
        x_admin_token: raw header value (None when the header is absent).

    Raises:
        AdminAuthError: header missing or not equal to the configured token
            (HTTP 401, code ``unauthorized``).
    """
    expected = get_settings().admin_token
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise AdminAuthError("Missing or invalid X-Admin-Token header")
