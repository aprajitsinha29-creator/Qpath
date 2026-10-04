"""Central error handlers: every failure renders the shared envelope (BUILD_PLAN 4.4)."""

from __future__ import annotations

import json

from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.core.errors import NotFoundError, _app_error_handler, _http_exception_handler


def _make_request(path: str = "/api/v1/test") -> Request:
    """Build a minimal ASGI request so handler signatures can be exercised directly."""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": [],
        }
    )


def test_app_error_handler_maps_domain_error_to_json() -> None:
    """A domain exception becomes its status plus {error: {code, message}}."""
    response = _app_error_handler(_make_request(), NotFoundError("profile not found"))

    assert response.status_code == 404
    assert json.loads(response.body) == {
        "error": {"code": "not_found", "message": "profile not found"}
    }


def test_http_exception_handler_uses_shared_shape() -> None:
    """Starlette HTTP errors (404 route, 405, ...) get a snake_case code too."""
    response = _http_exception_handler(_make_request(), HTTPException(status_code=405))

    assert response.status_code == 405
    body = json.loads(response.body)
    assert body["error"]["code"] == "method_not_allowed"
    assert body["error"]["message"]
