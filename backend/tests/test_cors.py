import pytest
from httpx import AsyncClient

from app.core.config import settings

ORIGIN = "http://localhost:3000"


async def test_payload_too_large_keeps_cors_headers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 10)

    response = await client.post(
        "/api/v1/health/live",
        content=b"01234567890",
        headers={"Origin": ORIGIN},
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == ORIGIN


async def test_cors_exposes_retry_after_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"Origin": ORIGIN})

    exposed = {
        value.strip().lower()
        for value in response.headers["access-control-expose-headers"].split(",")
    }
    assert {"x-request-id", "retry-after"} <= exposed


async def test_cors_does_not_allow_credentials_by_default(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"Origin": ORIGIN})

    assert "access-control-allow-credentials" not in response.headers


async def test_cors_preflight_allows_auth_headers(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-request-id",
        },
    )

    assert response.status_code == 200
    allowed = {
        value.strip().lower()
        for value in response.headers["access-control-allow-headers"].split(",")
    }
    assert {"authorization", "content-type", "x-request-id"} <= allowed


async def test_cors_preflight_rejects_unknown_headers(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-not-allowed",
        },
    )

    assert response.status_code == 400
