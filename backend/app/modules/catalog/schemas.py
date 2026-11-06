from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.catalog.model import LotQCStatus

_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class CategoryCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class CategoryUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50, pattern=_CODE_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_update(self) -> "CategoryUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in self.model_fields_set & {"code", "name", "is_active"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    barcode: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_id: UUID | None = None
    uom: str = Field(default="PCS", min_length=1, max_length=30)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    reorder_point: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    requires_lot: bool = False
    requires_qc: bool = True
    is_sample_eligible: bool = True


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64, pattern=_CODE_PATTERN)
    barcode: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category_id: UUID | None = None
    uom: str | None = Field(default=None, min_length=1, max_length=30)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    reorder_point: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    requires_lot: bool | None = None
    requires_qc: bool | None = None
    is_sample_eligible: bool | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_update(self) -> "ProductUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        non_nullable = {
            "sku",
            "name",
            "uom",
            "unit_price",
            "reorder_point",
            "requires_lot",
            "requires_qc",
            "is_sample_eligible",
            "is_active",
        }
        for field in self.model_fields_set & non_nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    barcode: str | None
    name: str
    description: str | None
    category_id: UUID | None
    uom: str
    unit_price: Decimal
    reorder_point: Decimal
    requires_lot: bool
    requires_qc: bool
    is_sample_eligible: bool
    is_active: bool


class LotCreate(BaseModel):
    product_id: UUID
    supplier_id: UUID | None = None
    lot_number: str = Field(min_length=1, max_length=100)
    manufactured_date: date | None = None
    expiry_date: date | None = None
    qc_status: LotQCStatus = LotQCStatus.PASSED


class LotUpdate(BaseModel):
    supplier_id: UUID | None = None
    lot_number: str | None = Field(default=None, min_length=1, max_length=100)
    manufactured_date: date | None = None
    expiry_date: date | None = None
    qc_status: LotQCStatus | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_update(self) -> "LotUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in self.model_fields_set & {"lot_number", "qc_status", "is_active"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class LotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    supplier_id: UUID | None
    lot_number: str
    manufactured_date: date | None
    expiry_date: date | None
    qc_status: LotQCStatus
    is_active: bool
    created_at: datetime
