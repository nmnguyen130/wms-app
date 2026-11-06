from datetime import timedelta

from httpx import AsyncClient

from app.utils.security import create_access_token
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    OPERATOR_EMAIL,
    OPERATOR_PASSWORD,
)


async def test_login_returns_token_pair(client: AsyncClient, admin_user: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_rejects_wrong_password(
    client: AsyncClient,
    admin_user: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": "Wrong-Passw0rd!123"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_account_locks_after_repeated_failures(
    client: AsyncClient,
    admin_user: dict[str, str],
) -> None:
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": "Wrong-Passw0rd!123"},
        )
        assert response.status_code == 401

    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )

    assert locked.status_code == 423
    assert locked.json()["error_code"] == "ACCOUNT_LOCKED"
    assert int(locked.headers["Retry-After"]) > 0


async def test_refresh_rotation_and_reuse_detection(
    client: AsyncClient,
    admin_user: dict[str, str],
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    first_refresh = login.json()["refresh_token"]

    rotated = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert rotated.status_code == 200
    second_refresh = rotated.json()["refresh_token"]
    assert second_refresh != first_refresh

    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reused.status_code == 401

    revoked_family = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_refresh},
    )
    assert revoked_family.status_code == 401


async def test_logout_revokes_refresh_token(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: dict[str, str],
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=admin_headers,
    )
    assert logout.status_code == 200

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


async def test_change_password_invalidates_existing_sessions(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: dict[str, str],
) -> None:
    changed = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "New-Admin-Passw0rd!456",
        },
        headers=admin_headers,
    )
    assert changed.status_code == 204

    stale = await client.get("/api/v1/users/me", headers=admin_headers)
    assert stale.status_code == 401
    assert stale.json()["error_code"] == "UNAUTHORIZED"

    relogin = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": "New-Admin-Passw0rd!456"},
    )
    assert relogin.status_code == 200


async def test_admin_creates_user_with_warehouse(
    client: AsyncClient,
    admin_headers: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    payload = {
        "full_name": "New User",
        "email": "New.User@Example.com",
        "password": "New-User-Passw0rd!123",
        "role": "INVENTORY_CLERK",
        "warehouse_ids": [warehouse["id"]],
    }

    created = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "new.user@example.com"
    assert body["role"] == "INVENTORY_CLERK"
    assert body["warehouse_ids"] == [warehouse["id"]]

    duplicate = await client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert duplicate.status_code == 409

    invalid_warehouse = await client.post(
        "/api/v1/users",
        json={
            **payload,
            "email": "other@example.com",
            "warehouse_ids": ["00000000-0000-0000-0000-000000000000"],
        },
        headers=admin_headers,
    )
    assert invalid_warehouse.status_code == 400


async def test_non_admin_cannot_manage_users(
    client: AsyncClient,
    operator_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/users", headers=operator_headers)
    assert response.status_code == 403


async def test_admin_cannot_deactivate_own_account(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: dict[str, str],
) -> None:
    response = await client.patch(
        f"/api/v1/users/{admin_user['id']}/access",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400


async def test_access_update_revokes_target_sessions(
    client: AsyncClient,
    admin_headers: dict[str, str],
    operator_headers: dict[str, str],
    operator_user: dict[str, str],
) -> None:
    updated = await client.patch(
        f"/api/v1/users/{operator_user['id']}/access",
        json={"role": "WAREHOUSE_MANAGER"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "WAREHOUSE_MANAGER"

    stale = await client.get("/api/v1/users/me", headers=operator_headers)
    assert stale.status_code == 401
    assert stale.json()["error_code"] == "UNAUTHORIZED"


async def test_inactive_user_cannot_login(
    client: AsyncClient,
    admin_headers: dict[str, str],
    operator_user: dict[str, str],
) -> None:
    deactivated = await client.patch(
        f"/api/v1/users/{operator_user['id']}/access",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": OPERATOR_EMAIL, "password": OPERATOR_PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


async def test_inactive_user_access_token_is_rejected(
    client: AsyncClient,
    admin_headers: dict[str, str],
    operator_headers: dict[str, str],
    operator_user: dict[str, str],
) -> None:
    deactivated = await client.patch(
        f"/api/v1/users/{operator_user['id']}/access",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200

    response = await client.get("/api/v1/users/me", headers=operator_headers)
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_expired_access_token_returns_token_expired(
    client: AsyncClient,
    admin_user: dict[str, str],
) -> None:
    token, _, _ = create_access_token(admin_user["id"], expires_delta=timedelta(seconds=-1))

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "TOKEN_EXPIRED"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_malformed_access_token_returns_token_invalid(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_refresh_token_is_rejected_as_access_token(
    client: AsyncClient,
    admin_user: dict[str, str],
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"


async def test_openapi_exposes_bearer_auth(client: AsyncClient) -> None:
    schema = (await client.get("/api/v1/openapi.json")).json()

    scheme = schema["components"]["securitySchemes"]["HTTPBearer"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert {"HTTPBearer": []} in schema["paths"]["/api/v1/users/me"]["get"]["security"]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
