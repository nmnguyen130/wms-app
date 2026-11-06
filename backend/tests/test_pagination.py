from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.utils.pagination import PaginationParams, paginate


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/items")
    async def list_items(params: PaginationParams = Depends()) -> dict:
        return paginate([], 0, params).model_dump()

    return app


async def test_pagination_params_are_wired_as_query_parameters() -> None:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/items?page=2&limit=5")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 2,
        "limit": 5,
        "total_pages": 0,
    }


async def test_pagination_rejects_out_of_range_values() -> None:
    transport = ASGITransport(app=_build_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/items?page=0&limit=101")

    assert response.status_code == 422
