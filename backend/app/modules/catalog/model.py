import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class LotQCStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


_QC_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in LotQCStatus)


class ProductCategory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "product_categories"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )


class Product(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint("reorder_point >= 0", name="reorder_point_non_negative"),
    )

    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    uom: Mapped[str] = mapped_column(
        String(30),
        default="PCS",
        server_default="PCS",
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        default=Decimal("0"),
        server_default=text("0"),
        nullable=False,
    )
    requires_lot: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    requires_qc: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    is_sample_eligible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )


class ProductLot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "product_lots"
    __table_args__ = (
        UniqueConstraint("product_id", "lot_number"),
        CheckConstraint(
            "expiry_date IS NULL OR manufactured_date IS NULL OR expiry_date >= manufactured_date",
            name="expiry_after_manufactured",
        ),
        CheckConstraint(f"qc_status IN ({_QC_STATUS_VALUES})", name="qc_status_valid"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    manufactured_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qc_status: Mapped[str] = mapped_column(
        String(30),
        default=LotQCStatus.PASSED.value,
        server_default=LotQCStatus.PASSED.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
