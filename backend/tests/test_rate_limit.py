import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import create_app

ORIGIN = "http://localhost:3000"


def _client_for(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_login_rate_limit_returns_429_with_retry_after_and_cors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN", "2/minute")
    app = create_app()

    async with _client_for(app) as client:
        payload = {"email": "nobody@example.com", "password": "Wrong-Passw0rd!123"}
        for _ in range(2):
            response = await client.post("/api/v1/auth/login", json=payload)
            assert response.status_code == 401
        response = await client.post(
            "/api/v1/auth/login",
            json=payload,
            headers={"Origin": ORIGIN},
        )

    assert response.status_code == 429
    body = response.json()
    assert body["error_code"] == "RATE_LIMITED"
    assert body["request_id"] == response.headers["x-request-id"]
    assert int(response.headers["retry-after"]) >= 1
    assert response.headers["access-control-allow-origin"] == ORIGIN


async def test_health_endpoints_are_exempt_from_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", "1/minute")
    app = create_app()

    async with _client_for(app) as client:
        for _ in range(3):
            response = await client.get("/api/v1/health/live")
            assert response.status_code == 200


async def test_default_rate_limit_applies_to_other_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", "2/minute")
    app = create_app()

    async with _client_for(app) as client:
        first = await client.get("/api/v1/users/me")
        second = await client.get("/api/v1/users/me")
        third = await client.get("/api/v1/users/me")

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


async def test_forwarded_for_header_cannot_bypass_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT", "1/minute")
    app = create_app()

    async with _client_for(app) as client:
        first = await client.get(
            "/api/v1/users/me",
            headers={"X-Forwarded-For": "203.0.113.1"},
        )
        second = await client.get(
            "/api/v1/users/me",
            headers={"X-Forwarded-For": "203.0.113.2"},
        )

    assert first.status_code == 401
    assert second.status_code == 429
