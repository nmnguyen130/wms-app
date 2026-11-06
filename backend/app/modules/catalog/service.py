from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.exceptions import AppException
from app.utils.pagination import PaginationParams
from app.modules.auth.model import User
from app.modules.catalog.model import Product, ProductCategory, ProductLot
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    LotCreate,
    LotUpdate,
    ProductCreate,
    ProductUpdate,
)
from app.modules.partners.model import Partner, PartnerRole


def _code(value: str) -> str:
    return value.strip()


def _validate_lot_dates(manufactured_date: date | None, expiry_date: date | None) -> None:
    if manufactured_date is not None and expiry_date is not None and expiry_date < manufactured_date:
        raise AppException.bad_request("expiry_date must be on or after manufactured_date")


class CategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get(self, category_id: UUID, *, lock: bool = False) -> ProductCategory:
        stmt = select(ProductCategory).where(ProductCategory.id == category_id)
        if lock:
            stmt = stmt.with_for_update()
        category = await self.db.scalar(stmt)
        if category is None:
            raise AppException.not_found("Category")
        return category

    async def _ensure_code_available(
        self,
        code: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(ProductCategory.id).where(ProductCategory.code == code)
        if exclude_id is not None:
            stmt = stmt.where(ProductCategory.id != exclude_id)
        if await self.db.scalar(stmt) is not None:
            raise AppException.conflict("Category code already exists")

    async def create(self, actor: User, data: CategoryCreate) -> ProductCategory:
        code = _code(data.code)
        await self._ensure_code_available(code)
        category = ProductCategory(
            code=code,
            name=data.name.strip(),
            description=data.description,
        )
        self.db.add(category)
        await self.db.flush()
        record_audit(
            self.db,
            actor_id=actor.id,
            action="CATEGORY_CREATED",
            entity_type="ProductCategory",
            entity_id=category.id,
        )
        return category

    async def list(
        self,
        pagination: PaginationParams,
        *,
        is_active: bool | None = None,
    ) -> tuple[list[ProductCategory], int]:
        conditions = []
        if is_active is not None:
            conditions.append(ProductCategory.is_active.is_(is_active))
        total = (
            await self.db.scalar(select(func.count()).select_from(ProductCategory).where(*conditions))
            or 0
        )
        stmt = (
            select(ProductCategory)
            .where(*conditions)
            .order_by(ProductCategory.name)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        return list((await self.db.scalars(stmt)).all()), total

    async def get(self, category_id: UUID) -> ProductCategory:
        return await self._get(category_id)

    async def update(self, actor: User, category_id: UUID, data: CategoryUpdate) -> ProductCategory:
        category = await self._get(category_id, lock=True)
        updates = data.model_dump(exclude_unset=True)

        if updates.get("code") is not None:
            code = _code(updates["code"])
            await self._ensure_code_available(code, exclude_id=category.id)
            category.code = code
        if updates.get("name") is not None:
            category.name = updates["name"].strip()
        if "description" in updates:
            category.description = updates["description"]
        if updates.get("is_active") is not None:
            category.is_active = updates["is_active"]

        record_audit(
            self.db,
            actor_id=actor.id,
            action="CATEGORY_UPDATED",
            entity_type="ProductCategory",
            entity_id=category.id,
        )
        await self.db.flush()
        return category

    async def delete(self, actor: User, category_id: UUID) -> None:
        category = await self._get(category_id, lock=True)
        category.is_active = False
        record_audit(
            self.db,
            actor_id=actor.id,
            action="CATEGORY_DEACTIVATED",
            entity_type="ProductCategory",
            entity_id=category.id,
        )
        await self.db.flush()


class ProductService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get(self, product_id: UUID, *, lock: bool = False) -> Product:
        stmt = select(Product).where(Product.id == product_id)
        if lock:
            stmt = stmt.with_for_update()
        product = await self.db.scalar(stmt)
        if product is None:
            raise AppException.not_found("Product")
        return product

    async def _ensure_category(self, category_id: UUID | None) -> None:
        if category_id is None:
            return
        if await self.db.get(ProductCategory, category_id) is None:
            raise AppException.bad_request("Product category does not exist")

    async def _ensure_unique(
        self,
        *,
        sku: str | None = None,
        barcode: str | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        for column, value, message in (
            (Product.sku, sku, "Product SKU already exists"),
            (Product.barcode, barcode, "Product barcode already exists"),
        ):
            if value is None:
                continue
            stmt = select(Product.id).where(column == value)
            if exclude_id is not None:
                stmt = stmt.where(Product.id != exclude_id)
            if await self.db.scalar(stmt) is not None:
                raise AppException.conflict(message)

    async def create(self, actor: User, data: ProductCreate) -> Product:
        sku = _code(data.sku)
        barcode = data.barcode.strip() if data.barcode else None
        await self._ensure_unique(sku=sku, barcode=barcode)
        await self._ensure_category(data.category_id)

        product = Product(
            sku=sku,
            barcode=barcode,
            name=data.name.strip(),
            description=data.description,
            category_id=data.category_id,
            uom=data.uom.strip(),
            unit_price=data.unit_price,
            reorder_point=data.reorder_point,
            requires_lot=data.requires_lot,
            requires_qc=data.requires_qc,
            is_sample_eligible=data.is_sample_eligible,
        )
        self.db.add(product)
        await self.db.flush()
        record_audit(
            self.db,
            actor_id=actor.id,
            action="PRODUCT_CREATED",
            entity_type="Product",
            entity_id=product.id,
        )
        return product

    async def list(
        self,
        pagination: PaginationParams,
        *,
        is_active: bool | None = None,
        category_id: UUID | None = None,
    ) -> tuple[list[Product], int]:
        conditions = []
        if is_active is not None:
            conditions.append(Product.is_active.is_(is_active))
        if category_id is not None:
            conditions.append(Product.category_id == category_id)

        total = (
            await self.db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
        )
        stmt = (
            select(Product)
            .where(*conditions)
            .order_by(Product.sku)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        return list((await self.db.scalars(stmt)).all()), total

    async def get(self, product_id: UUID) -> Product:
        return await self._get(product_id)

    async def update(self, actor: User, product_id: UUID, data: ProductUpdate) -> Product:
        product = await self._get(product_id, lock=True)
        updates = data.model_dump(exclude_unset=True)

        sku = _code(updates["sku"]) if updates.get("sku") is not None else None
        barcode = updates["barcode"].strip() if updates.get("barcode") is not None else None
        await self._ensure_unique(
            sku=sku,
            barcode=barcode,
            exclude_id=product.id,
        )
        if "category_id" in updates:
            await self._ensure_category(updates["category_id"])

        if sku is not None:
            product.sku = sku
        if "barcode" in updates:
            product.barcode = barcode
        if updates.get("name") is not None:
            product.name = updates["name"].strip()
        if "description" in updates:
            product.description = updates["description"]
        if "category_id" in updates:
            product.category_id = updates["category_id"]
        if updates.get("uom") is not None:
            product.uom = updates["uom"].strip()
        if updates.get("unit_price") is not None:
            product.unit_price = updates["unit_price"]
        if updates.get("reorder_point") is not None:
            product.reorder_point = updates["reorder_point"]
        if updates.get("requires_lot") is not None:
            product.requires_lot = updates["requires_lot"]
        if updates.get("requires_qc") is not None:
            product.requires_qc = updates["requires_qc"]
        if updates.get("is_sample_eligible") is not None:
            product.is_sample_eligible = updates["is_sample_eligible"]
        if updates.get("is_active") is not None:
            product.is_active = updates["is_active"]

        record_audit(
            self.db,
            actor_id=actor.id,
            action="PRODUCT_UPDATED",
            entity_type="Product",
            entity_id=product.id,
        )
        await self.db.flush()
        return product

    async def delete(self, actor: User, product_id: UUID) -> None:
        product = await self._get(product_id, lock=True)
        product.is_active = False
        record_audit(
            self.db,
            actor_id=actor.id,
            action="PRODUCT_DEACTIVATED",
            entity_type="Product",
            entity_id=product.id,
        )
        await self.db.flush()


class LotService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get(self, lot_id: UUID, *, lock: bool = False) -> ProductLot:
        stmt = select(ProductLot).where(ProductLot.id == lot_id)
        if lock:
            stmt = stmt.with_for_update()
        lot = await self.db.scalar(stmt)
        if lot is None:
            raise AppException.not_found("Lot")
        return lot

    async def _ensure_product(self, product_id: UUID) -> None:
        if await self.db.get(Product, product_id) is None:
            raise AppException.bad_request("Product does not exist")

    async def _ensure_supplier(self, supplier_id: UUID | None) -> None:
        if supplier_id is None:
            return
        partner = await self.db.get(Partner, supplier_id)
        if partner is None:
            raise AppException.bad_request("Supplier partner does not exist")
        if not partner.has_role(PartnerRole.SUPPLIER):
            raise AppException.bad_request("supplier_id must reference a SUPPLIER partner")

    async def _ensure_lot_number_available(
        self,
        product_id: UUID,
        lot_number: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(ProductLot.id).where(
            ProductLot.product_id == product_id,
            ProductLot.lot_number == lot_number,
        )
        if exclude_id is not None:
            stmt = stmt.where(ProductLot.id != exclude_id)
        if await self.db.scalar(stmt) is not None:
            raise AppException.conflict("Lot number already exists for this product")

    async def create(self, actor: User, data: LotCreate) -> ProductLot:
        lot_number = _code(data.lot_number)
        await self._ensure_product(data.product_id)
        await self._ensure_supplier(data.supplier_id)
        await self._ensure_lot_number_available(data.product_id, lot_number)
        _validate_lot_dates(data.manufactured_date, data.expiry_date)

        lot = ProductLot(
            product_id=data.product_id,
            supplier_id=data.supplier_id,
            lot_number=lot_number,
            manufactured_date=data.manufactured_date,
            expiry_date=data.expiry_date,
            qc_status=data.qc_status.value,
        )
        self.db.add(lot)
        await self.db.flush()
        record_audit(
            self.db,
            actor_id=actor.id,
            action="LOT_CREATED",
            entity_type="ProductLot",
            entity_id=lot.id,
        )
        return lot

    async def list(
        self,
        pagination: PaginationParams,
        *,
        product_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[ProductLot], int]:
        conditions = []
        if product_id is not None:
            conditions.append(ProductLot.product_id == product_id)
        if is_active is not None:
            conditions.append(ProductLot.is_active.is_(is_active))

        total = (
            await self.db.scalar(select(func.count()).select_from(ProductLot).where(*conditions))
            or 0
        )
        stmt = (
            select(ProductLot)
            .where(*conditions)
            .order_by(ProductLot.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        return list((await self.db.scalars(stmt)).all()), total

    async def get(self, lot_id: UUID) -> ProductLot:
        return await self._get(lot_id)

    async def update(self, actor: User, lot_id: UUID, data: LotUpdate) -> ProductLot:
        lot = await self._get(lot_id, lock=True)
        updates = data.model_dump(exclude_unset=True)

        lot_number = _code(updates["lot_number"]) if updates.get("lot_number") is not None else None
        if lot_number is not None:
            await self._ensure_lot_number_available(
                lot.product_id,
                lot_number,
                exclude_id=lot.id,
            )
        if "supplier_id" in updates:
            await self._ensure_supplier(updates["supplier_id"])

        manufactured_date = (
            updates["manufactured_date"] if "manufactured_date" in updates else lot.manufactured_date
        )
        expiry_date = updates["expiry_date"] if "expiry_date" in updates else lot.expiry_date
        _validate_lot_dates(manufactured_date, expiry_date)

        if lot_number is not None:
            lot.lot_number = lot_number
        if "supplier_id" in updates:
            lot.supplier_id = updates["supplier_id"]
        if "manufactured_date" in updates:
            lot.manufactured_date = updates["manufactured_date"]
        if "expiry_date" in updates:
            lot.expiry_date = updates["expiry_date"]
        if updates.get("qc_status") is not None:
            lot.qc_status = updates["qc_status"].value
        if updates.get("is_active") is not None:
            lot.is_active = updates["is_active"]

        record_audit(
            self.db,
            actor_id=actor.id,
            action="LOT_UPDATED",
            entity_type="ProductLot",
            entity_id=lot.id,
        )
        await self.db.flush()
        return lot

    async def delete(self, actor: User, lot_id: UUID) -> None:
        lot = await self._get(lot_id, lock=True)
        lot.is_active = False
        record_audit(
            self.db,
            actor_id=actor.id,
            action="LOT_DEACTIVATED",
            entity_type="ProductLot",
            entity_id=lot.id,
        )
        await self.db.flush()
