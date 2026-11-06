import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[1]

os.environ["ENVIRONMENT"] = "testing"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production-0123456789abcdef"
if test_database_url := os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = test_database_url
else:
    os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "wms_test")

import app.models_registry  # noqa: E402,F401  (register every model on Base.metadata)
from app.core.config import settings  # noqa: E402
from app.core.database import Base, async_session_factory, engine  # noqa: E402
from app.core.permissions import Role  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.auth.model import User  # noqa: E402
from app.modules.warehouses.model import Warehouse  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin-Passw0rd!123"
OPERATOR_EMAIL = "operator@example.com"
OPERATOR_PASSWORD = "Operator-Passw0rd!123"


async def _ensure_database_exists() -> None:
    url = make_url(settings.DATABASE_URL)
    admin_engine = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if exists is None:
                await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        await admin_engine.dispose()


def _run_migrations() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncIterator[None]:
    await _ensure_database_exists()
    await asyncio.to_thread(_run_migrations)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_clean(prepare_database: None) -> AsyncIterator[None]:
    table_names = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_user(
    email: str,
    password: str,
    role: Role,
    *,
    full_name: str = "Test User",
    warehouse_ids: list[str] | None = None,
) -> dict[str, str]:
    async with async_session_factory() as session:
        warehouses = []
        if warehouse_ids:
            warehouses = list(
                (
                    await session.scalars(
                        select(Warehouse).where(
                            Warehouse.id.in_([UUID(value) for value in warehouse_ids])
                        )
                    )
                ).all()
            )
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role.value,
            warehouses=warehouses,
        )
        session.add(user)
        await session.commit()
        return {"id": str(user.id), "email": user.email, "password": password}


UserFactory = Callable[..., Awaitable[dict[str, str]]]


@pytest_asyncio.fixture
async def user_factory(db_clean: None) -> UserFactory:
    return _create_user


@pytest_asyncio.fixture
async def admin_user(user_factory: UserFactory) -> dict[str, str]:
    return await user_factory(ADMIN_EMAIL, ADMIN_PASSWORD, Role.ADMIN, full_name="Test Admin")


@pytest_asyncio.fixture
async def operator_user(user_factory: UserFactory) -> dict[str, str]:
    return await user_factory(OPERATOR_EMAIL, OPERATOR_PASSWORD, Role.OPERATOR)


@pytest_asyncio.fixture
async def warehouse(db_clean: None) -> dict[str, str]:
    async with async_session_factory() as session:
        record = Warehouse(code="WH-01", name="Main Warehouse")
        session.add(record)
        await session.commit()
        return {"id": str(record.id), "code": record.code, "name": record.name}


async def _login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, admin_user: dict[str, str]) -> dict[str, str]:
    return await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest_asyncio.fixture
async def operator_headers(client: AsyncClient, operator_user: dict[str, str]) -> dict[str, str]:
    return await _login(client, OPERATOR_EMAIL, OPERATOR_PASSWORD)
