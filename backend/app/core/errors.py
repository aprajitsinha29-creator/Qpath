"""Domain exceptions and central FastAPI handlers (AGENTS.md 3.3.5).

Every failure — domain error, validation error or HTTP error — is rendered as
``{"error": {"code": "<snake_case>", "message": "<human readable>"}}`` with the
status mapped per exception class (BUILD_PLAN 4.4). Nothing here touches the DB
or external services; handlers only log and shape the response.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all domain errors.

    Attributes:
        code: stable ``snake_case`` error code sent to clients.
        status_code: HTTP status the handler should return.
        message: human-readable message sent to clients (never contains secrets).
    """

    code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    """A requested entity does not exist (404)."""

    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    """The request conflicts with existing state, e.g. a uniqueness violation (409)."""

    code = "conflict"
    status_code = 409


class SerpApiError(AppError):
    """SerpApi returned an error body, a 4xx/5xx, or an unreadable payload (502)."""

    code = "serpapi_error"
    status_code = 502


class SerpApiCapExceeded(AppError):
    """Today's live call count reached SERPAPI_DAILY_CALL_CAP (429)."""

    code = "serpapi_cap_exceeded"
    status_code = 429


class FixtureMissingError(AppError):
    """Fixture mode was asked for a recording that does not exist (404).

    Callers treat this as "no more data" and usually catch it themselves.
    """

    code = "fixture_missing"
    status_code = 404


class LLMOutputError(AppError):
    """Gemini returned output that failed schema/domain validation after one retry (502)."""

    code = "llm_output_error"
    status_code = 502


class GeminiDailyQuotaExhausted(LLMOutputError):
    """Every transport attempt failed with HTTP 429 — treat as quota exhaustion.

    Subclass of :class:`LLMOutputError` so existing handlers keep working, but
    distinct so callers that CAN fall back without waiting (the Phase 4
    explanation service) can skip further retries entirely (design decision 1).
    """

    code = "gemini_quota_exhausted"


class ConfigError(AppError):
    """A feature was invoked with missing/invalid configuration (500)."""

    code = "config_error"
    status_code = 500


class SeedDataError(AppError):
    """A reference data file in app/data/ is invalid; startup must fail loudly (500)."""

    code = "seed_data_error"
    status_code = 500


class QuizContentError(AppError):
    """The quiz cannot be served: some scored subfield has < 3 servable questions (503).

    503 rather than 404: the endpoint exists and works, but the content
    configuration is not ready (e.g. verified bank missing and unverified
    questions disallowed). Serving a lopsided quiz would silently bias scores.
    """

    code = "quiz_insufficient_questions"
    status_code = 503


class InvalidAssessmentError(AppError):
    """Assessment answers are semantically invalid: unknown question id or a
    duplicate answer (422)."""

    code = "invalid_assessment"
    status_code = 422


class AssessmentRequiredError(ConflictError):
    """The profile has no diagnostic submission yet, so paths cannot be ranked (409).

    409 (not 404): the profile exists — the request conflicts with its current
    state (plan 4.3: code ``assessment_required``).
    """

    code = "assessment_required"


class InvalidSkillsError(AppError):
    """Declared skill ids are not in the controlled vocabulary (422).

    The vocabulary is the contract for every downstream skill computation, so
    unknown ids are rejected at the API boundary (plan 4.5).
    """

    code = "invalid_skills"
    status_code = 422


class InvalidPathError(AppError):
    """A referenced career path id does not exist in the seeded taxonomy (422).

    422 rather than 404: the path collection is a fixed reference set, so an
    unknown id means the client sent an invalid value (plan 5.1).
    """

    code = "invalid_path"
    status_code = 422


class PathRequiredError(ConflictError):
    """The profile has not tracked a career path yet (409 ``path_required``).

    409 (not 404): the profile exists — the request conflicts with its current
    state (plan 5.1), same reasoning as ``AssessmentRequiredError``.
    """

    code = "path_required"


# HTTP errors raised by FastAPI/Starlette itself get a snake_case code too.
_HTTP_ERROR_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "too_many_requests",
}


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build the shared JSON error response for the given status/code/message."""
    payload = ErrorResponse(error={"code": code, "message": message})
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Render a domain exception; 5xx logs at ERROR, 4xx at WARNING."""
    log = logger.error if exc.status_code >= 500 else logger.warning
    log(
        "domain error: code=%s status=%s path=%s message=%s",
        exc.code,
        exc.status_code,
        request.url.path,
        exc.message,
    )
    return _error_response(exc.status_code, exc.code, exc.message)


def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Render FastAPI/Starlette HTTP errors (404 route not found, 405, ...) in the shared shape."""
    code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    logger.warning("http error: status=%s path=%s", exc.status_code, request.url.path)
    return _error_response(exc.status_code, code, message)


def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render request validation failures as one readable message in the shared shape.

    Only the first error is surfaced (full error contexts can embed raw input);
    the field path still tells the client where to look.
    """
    errors = exc.errors()
    first = errors[0] if errors else {}
    location = ".".join(str(part) for part in first.get("loc", ()))
    detail = str(first.get("message", "invalid value"))
    if location:
        message = f"Validation failed for '{location}': {detail}"
    else:
        message = f"Validation failed: {detail}"
    logger.warning("validation error: path=%s detail=%s", request.url.path, message)
    return _error_response(422, "validation_error", message)


def register_error_handlers(app: FastAPI) -> None:
    """Attach the central handlers to the app (called once from ``create_app``).

    Starlette walks the exception MRO, so the ``AppError`` handler covers every
    subclass without registering each one separately.
    """
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
