"""Health endpoint + middleware behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body and body["version"]


def test_health_returns_request_id(client: TestClient) -> None:
    r = client.get("/health")
    assert "x-request-id" in r.headers
    assert len(r.headers["x-request-id"]) > 0


def test_cors_preflight(client: TestClient) -> None:
    # FastAPI/Starlette responds to OPTIONS only when an origin header is set
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # 200 or 204 are both valid CORS preflight responses
    assert r.status_code in (200, 204)
