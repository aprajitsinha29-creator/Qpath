"""Shared FastAPI dependencies: admin-token guard, structured-LLM provider.

Admin endpoints (refresh, extract, scholar) require the ``X-Admin-Token``
header to match ``Settings.admin_token`` compared with ``secrets.compare_digest``
— constant-time, so response timing cannot leak the token character by
character. The dev-only token is typed into the UI and kept in sessionStorage
(AGENTS 3.6.7); it is never stored server-side.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import AppError, ConfigError

if TYPE_CHECKING:
    from app.integrations.gemini.client import StructuredLLM


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


def get_structured_llm() -> StructuredLLM:
    """FastAPI dependency: build the Gemini-backed StructuredLLM for one request.

    Returned as the Protocol type so services never see the concrete class and
    tests can override this dependency with ``FakeStructuredLLM`` (AGENTS 3.5.1
    — the composition root is the only place the real client is constructed).
    A new client per request is fine: ``genai.Client`` construction makes no
    network calls, and admin endpoints run rarely.

    Raises:
        ConfigError: Gemini credentials/model are not configured (HTTP 500,
            code ``config_error`` — a clear, actionable message rather than a
            crash deep inside an LLM call).
    """
    from app.integrations.gemini.client import GeminiStructuredLLM

    settings = get_settings()
    settings.require_gemini()
    return GeminiStructuredLLM(settings)


def get_structured_llm_optional() -> StructuredLLM | None:
    """Dependency: the Gemini client when configured, else None (Phase 4).

    ``GET /profiles/{id}/paths`` and ``POST .../explanation`` must work with
    no Gemini key and no quota (design decision 4): the service turns ``None``
    into deterministic templates instead of failing the request. Tests
    override THIS dependency to inject a fake.

    Returns:
        A :class:`StructuredLLM`, or None when GEMINI_API_KEY/GEMINI_MODEL are
        not configured (ConfigError is expected here, not an HTTP failure).
    """
    try:
        return get_structured_llm()
    except ConfigError:
        return None
