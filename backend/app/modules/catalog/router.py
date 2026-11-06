from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.permissions import Permission
from app.modules.auth.model import User
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    LotCreate,
    LotResponse,
    LotUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.modules.catalog.service import CategoryService, LotService, ProductService

categories_router = APIRouter(prefix="/categories", tags=["Catalog - Categories"])
products_router = APIRouter(prefix="/products", tags=["Catalog - Products"])
lots_router = APIRouter(prefix="/lots", tags=["Catalog - Lots"])


@categories_router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await CategoryService(db).create(current_user, data)
    return CategoryResponse.model_validate(category)


@categories_router.get("", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    pagination: PaginationParams = Depends(),
    is_active: bool | None = None,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CategoryResponse]:
    categories, total = await CategoryService(db).list(pagination, is_active=is_active)
    return paginate(
        [CategoryResponse.model_validate(category) for category in categories],
        total,
        pagination,
    )


@categories_router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    return CategoryResponse.model_validate(await CategoryService(db).get(category_id))


@categories_router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await CategoryService(db).update(current_user, category_id, data)
    return CategoryResponse.model_validate(category)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await CategoryService(db).delete(current_user, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@products_router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    product = await ProductService(db).create(current_user, data)
    return ProductResponse.model_validate(product)


@products_router.get("", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    pagination: PaginationParams = Depends(),
    is_active: bool | None = None,
    category_id: UUID | None = None,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProductResponse]:
    products, total = await ProductService(db).list(
        pagination,
        is_active=is_active,
        category_id=category_id,
    )
    return paginate(
        [ProductResponse.model_validate(product) for product in products],
        total,
        pagination,
    )


@products_router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    return ProductResponse.model_validate(await ProductService(db).get(product_id))


@products_router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    product = await ProductService(db).update(current_user, product_id, data)
    return ProductResponse.model_validate(product)


@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await ProductService(db).delete(current_user, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@lots_router.post("", response_model=LotResponse, status_code=status.HTTP_201_CREATED)
async def create_lot(
    data: LotCreate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> LotResponse:
    lot = await LotService(db).create(current_user, data)
    return LotResponse.model_validate(lot)


@lots_router.get("", response_model=PaginatedResponse[LotResponse])
async def list_lots(
    pagination: PaginationParams = Depends(),
    product_id: UUID | None = None,
    is_active: bool | None = None,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[LotResponse]:
    lots, total = await LotService(db).list(
        pagination,
        product_id=product_id,
        is_active=is_active,
    )
    return paginate([LotResponse.model_validate(lot) for lot in lots], total, pagination)


@lots_router.get("/{lot_id}", response_model=LotResponse)
async def get_lot(
    lot_id: UUID,
    _: User = Depends(require_permission(Permission.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
) -> LotResponse:
    return LotResponse.model_validate(await LotService(db).get(lot_id))


@lots_router.patch("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: UUID,
    data: LotUpdate,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> LotResponse:
    lot = await LotService(db).update(current_user, lot_id, data)
    return LotResponse.model_validate(lot)


@lots_router.delete("/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lot(
    lot_id: UUID,
    current_user: User = Depends(require_permission(Permission.CATALOG_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await LotService(db).delete(current_user, lot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
