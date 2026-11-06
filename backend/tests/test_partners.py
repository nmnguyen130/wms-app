from httpx import AsyncClient

from app.core.permissions import Role
from tests.conftest import UserFactory


async def test_partner_crud_filter_and_soft_delete(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    created = await client.post(
        "/api/v1/partners",
        json={
            "code": "SUP-01",
            "name": "Supplier Ltd",
            "roles": ["SUPPLIER"],
            "email": "Sales@Supplier.com",
            "phone": " 0901234567 ",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    partner = created.json()
    assert partner["email"] == "sales@supplier.com"
    assert partner["phone"] == "0901234567"
    assert partner["roles"] == ["SUPPLIER"]

    customer = await client.post(
        "/api/v1/partners",
        json={"code": "CUS-01", "name": "Buyer Ltd", "roles": ["CUSTOMER"]},
        headers=admin_headers,
    )
    assert customer.status_code == 201

    filtered = await client.get(
        "/api/v1/partners?role=SUPPLIER",
        headers=admin_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["code"] == "SUP-01"

    updated = await client.patch(
        f"/api/v1/partners/{partner['id']}",
        json={"name": "Supplier Group", "roles": ["SUPPLIER", "CUSTOMER"]},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Supplier Group"
    assert updated.json()["roles"] == ["CUSTOMER", "SUPPLIER"]

    now_customer = await client.get(
        "/api/v1/partners?role=CUSTOMER",
        headers=admin_headers,
    )
    assert now_customer.json()["total"] == 2

    deleted = await client.delete(f"/api/v1/partners/{partner['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/partners/{partner['id']}", headers=admin_headers)
    assert fetched.json()["is_active"] is False


async def test_partner_can_hold_both_roles(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    created = await client.post(
        "/api/v1/partners",
        json={"code": "BOTH-01", "name": "Both Ltd", "roles": ["CUSTOMER", "SUPPLIER"]},
        headers=admin_headers,
    )
    assert created.status_code == 201
    partner = created.json()
    assert partner["roles"] == ["CUSTOMER", "SUPPLIER"]

    for role in ("CUSTOMER", "SUPPLIER"):
        filtered = await client.get(
            f"/api/v1/partners?role={role}",
            headers=admin_headers,
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["items"]] == [partner["id"]]

    narrowed = await client.patch(
        f"/api/v1/partners/{partner['id']}",
        json={"roles": ["SUPPLIER"]},
        headers=admin_headers,
    )
    assert narrowed.status_code == 200
    assert narrowed.json()["roles"] == ["SUPPLIER"]

    customers = await client.get("/api/v1/partners?role=CUSTOMER", headers=admin_headers)
    assert customers.json()["total"] == 0


async def test_duplicate_partner_code_conflicts(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    payload = {"code": "SUP-01", "name": "Supplier Ltd", "roles": ["SUPPLIER"]}
    first = await client.post("/api/v1/partners", json=payload, headers=admin_headers)
    assert first.status_code == 201

    duplicate = await client.post("/api/v1/partners", json=payload, headers=admin_headers)
    assert duplicate.status_code == 409


async def test_invalid_partner_payload_is_rejected(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    invalid_email = await client.post(
        "/api/v1/partners",
        json={
            "code": "SUP-01",
            "name": "Supplier Ltd",
            "roles": ["SUPPLIER"],
            "email": "not-an-email",
        },
        headers=admin_headers,
    )
    assert invalid_email.status_code == 422

    invalid_role = await client.post(
        "/api/v1/partners",
        json={"code": "SUP-02", "name": "Supplier Ltd", "roles": ["VENDOR"]},
        headers=admin_headers,
    )
    assert invalid_role.status_code == 422

    empty_roles = await client.post(
        "/api/v1/partners",
        json={"code": "SUP-03", "name": "Supplier Ltd", "roles": []},
        headers=admin_headers,
    )
    assert empty_roles.status_code == 422

    null_roles = await client.post(
        "/api/v1/partners",
        json={"code": "SUP-04", "name": "Supplier Ltd", "roles": None},
        headers=admin_headers,
    )
    assert null_roles.status_code == 422


async def test_operator_can_read_but_not_write_partners(
    client: AsyncClient,
    operator_headers: dict[str, str],
) -> None:
    assert (await client.get("/api/v1/partners", headers=operator_headers)).status_code == 200

    response = await client.post(
        "/api/v1/partners",
        json={"code": "SUP-01", "name": "Supplier Ltd", "roles": ["SUPPLIER"]},
        headers=operator_headers,
    )
    assert response.status_code == 403


async def test_partner_permissions_are_independent_of_catalog(
    client: AsyncClient,
    user_factory: UserFactory,
) -> None:
    await user_factory("qc@example.com", "QC-Passw0rd!123", Role.QC_INSPECTOR)

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "qc@example.com", "password": "QC-Passw0rd!123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get("/api/v1/partners", headers=headers)).status_code == 200
    assert (
        await client.post(
            "/api/v1/partners",
            json={"code": "SUP-01", "name": "Supplier Ltd", "roles": ["SUPPLIER"]},
            headers=headers,
        )
    ).status_code == 403

    category = await client.post(
        "/api/v1/categories",
        json={"code": "CAT-QC", "name": "QC Category"},
        headers=headers,
    )
    assert category.status_code == 201
