import os
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production-0123456789abcdef"
os.environ["POSTGRES_PASSWORD"] = "test-only-password"

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
