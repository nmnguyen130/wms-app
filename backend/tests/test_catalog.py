from uuid import uuid4

from httpx import AsyncClient


async def _create_category(client: AsyncClient, headers: dict[str, str], code: str = "CAT-01") -> dict:
    response = await client.post(
        "/api/v1/categories",
        json={"code": code, "name": "Electronics", "description": "Devices"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_product(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    sku: str = "SKU-001",
    category_id: str | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": "Barcode Scanner",
            "category_id": category_id,
            "unit_price": "120.50",
            "reorder_point": "5",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_category_crud_and_soft_delete(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category = await _create_category(client, admin_headers)

    listed = await client.get("/api/v1/categories", headers=admin_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = await client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"name": "Electronic Devices"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Electronic Devices"

    deleted = await client.delete(
        f"/api/v1/categories/{category['id']}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/categories/{category['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["is_active"] is False

    active_only = await client.get(
        "/api/v1/categories?is_active=true",
        headers=admin_headers,
    )
    assert active_only.json()["total"] == 0


async def test_duplicate_category_code_conflicts(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    await _create_category(client, admin_headers)

    duplicate = await client.post(
        "/api/v1/categories",
        json={"code": "CAT-01", "name": "Other"},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409


async def test_product_crud_filters_and_soft_delete(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category = await _create_category(client, admin_headers)
    product = await _create_product(client, admin_headers, category_id=category["id"])

    assert product["category_id"] == category["id"]
    assert product["uom"] == "PCS"
    assert float(product["unit_price"]) == 120.5

    filtered = await client.get(
        f"/api/v1/products?category_id={category['id']}",
        headers=admin_headers,
    )
    assert filtered.json()["total"] == 1

    updated = await client.patch(
        f"/api/v1/products/{product['id']}",
        json={"unit_price": "99.99", "requires_qc": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert float(updated.json()["unit_price"]) == 99.99
    assert updated.json()["requires_qc"] is False

    duplicate_sku = await client.post(
        "/api/v1/products",
        json={"sku": "SKU-001", "name": "Duplicate", "unit_price": "1.00"},
        headers=admin_headers,
    )
    assert duplicate_sku.status_code == 409

    unknown_category = await client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-002",
            "name": "Orphan",
            "unit_price": "1.00",
            "category_id": str(uuid4()),
        },
        headers=admin_headers,
    )
    assert unknown_category.status_code == 400

    deleted = await client.delete(
        f"/api/v1/products/{product['id']}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/products/{product['id']}", headers=admin_headers)
    assert fetched.json()["is_active"] is False


async def _create_supplier(client: AsyncClient, headers: dict[str, str], code: str) -> dict:
    response = await client.post(
        "/api/v1/partners",
        json={"code": code, "name": "Supplier Ltd", "roles": ["SUPPLIER"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_lot_validation_and_soft_delete(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    product = await _create_product(client, admin_headers)
    supplier = await _create_supplier(client, admin_headers, "SUP-01")
    customer = await client.post(
        "/api/v1/partners",
        json={"code": "CUS-01", "name": "Buyer Ltd", "roles": ["CUSTOMER"]},
        headers=admin_headers,
    )
    assert customer.status_code == 201

    created = await client.post(
        "/api/v1/lots",
        json={
            "product_id": product["id"],
            "supplier_id": supplier["id"],
            "lot_number": "LOT-2026-001",
            "manufactured_date": "2026-01-01",
            "expiry_date": "2027-01-01",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    lot = created.json()
    assert lot["qc_status"] == "PASSED"

    duplicate = await client.post(
        "/api/v1/lots",
        json={
            "product_id": product["id"],
            "lot_number": "LOT-2026-001",
        },
        headers=admin_headers,
    )
    assert duplicate.status_code == 409

    invalid_dates = await client.post(
        "/api/v1/lots",
        json={
            "product_id": product["id"],
            "lot_number": "LOT-2026-002",
            "manufactured_date": "2026-05-01",
            "expiry_date": "2026-04-01",
        },
        headers=admin_headers,
    )
    assert invalid_dates.status_code == 400

    wrong_supplier_type = await client.post(
        "/api/v1/lots",
        json={
            "product_id": product["id"],
            "supplier_id": customer.json()["id"],
            "lot_number": "LOT-2026-003",
        },
        headers=admin_headers,
    )
    assert wrong_supplier_type.status_code == 400

    filtered = await client.get(
        f"/api/v1/lots?product_id={product['id']}",
        headers=admin_headers,
    )
    assert filtered.json()["total"] == 1

    dual_role = await client.post(
        "/api/v1/partners",
        json={"code": "BOTH-01", "name": "Both Ltd", "roles": ["CUSTOMER", "SUPPLIER"]},
        headers=admin_headers,
    )
    assert dual_role.status_code == 201

    dual_role_lot = await client.post(
        "/api/v1/lots",
        json={
            "product_id": product["id"],
            "supplier_id": dual_role.json()["id"],
            "lot_number": "LOT-2026-004",
        },
        headers=admin_headers,
    )
    assert dual_role_lot.status_code == 201

    deleted = await client.delete(f"/api/v1/lots/{lot['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    fetched = await client.get(f"/api/v1/lots/{lot['id']}", headers=admin_headers)
    assert fetched.json()["is_active"] is False


async def test_operator_can_read_catalog_but_not_write(
    client: AsyncClient,
    operator_headers: dict[str, str],
) -> None:
    assert (await client.get("/api/v1/categories", headers=operator_headers)).status_code == 200
    assert (await client.get("/api/v1/products", headers=operator_headers)).status_code == 200
    assert (await client.get("/api/v1/lots", headers=operator_headers)).status_code == 200

    forbidden = await client.post(
        "/api/v1/categories",
        json={"code": "CAT-02", "name": "Forbidden"},
        headers=operator_headers,
    )
    assert forbidden.status_code == 403


async def test_update_requires_at_least_one_field(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    category = await _create_category(client, admin_headers)

    response = await client.patch(
        f"/api/v1/categories/{category['id']}",
        json={},
        headers=admin_headers,
    )
    assert response.status_code == 422
