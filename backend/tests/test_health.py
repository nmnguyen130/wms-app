from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.api.deps import get_db
from app.main import app


class _UnavailableSession:
    async def execute(self, *args: object, **kwargs: object) -> None:
        raise OSError("database unavailable")

    async def rollback(self) -> None:
        return None


@pytest.fixture
def failing_database() -> AsyncIterator[None]:
    async def _get_db() -> AsyncIterator[_UnavailableSession]:
        yield _UnavailableSession()

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "WMS Backend API"
    assert "version" in data


@pytest.mark.asyncio
async def test_liveness_check(client: AsyncClient):
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data
    assert "x-request-id" in response.headers
    assert "x-process-time-ms" in response.headers


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_is_unavailable(client: AsyncClient, failing_database: None):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database"] is False
