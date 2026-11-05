import pytest
from httpx import AsyncClient

from app.core.config import settings


async def test_request_id_is_sanitized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "bad<id>"})
    request_id = response.headers["x-request-id"]
    assert request_id != "bad<id>"
    assert len(request_id) == 36


async def test_valid_request_id_is_preserved(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "client.trace-123"})
    assert response.headers["x-request-id"] == "client.trace-123"
    assert "strict-transport-security" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_oversized_content_length_is_rejected(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_REQUEST_BODY_BYTES", 10)
    response = await client.post("/api/v1/health/live", content=b"01234567890")
    assert response.status_code == 413
    assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["x-request-id"]
