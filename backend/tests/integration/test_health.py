"""Endpoint behavior tests for GET /api/v1/health (Phase 0)."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """Health reports status/env/db ok with a non-empty version on a live temp DB."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["env"] == "development"
    assert body["version"]


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    """404s use the shared {"error": {code, message}} envelope, not FastAPI's default."""
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]
