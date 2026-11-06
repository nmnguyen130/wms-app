import uuid
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UUIDPrimaryKeyMixin


class PartnerRole(StrEnum):
    SUPPLIER = "SUPPLIER"
    CUSTOMER = "CUSTOMER"


_ROLE_VALUES = ", ".join(f"'{role.value}'" for role in PartnerRole)


class Partner(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "partners"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )

    role_assignments: Mapped[list["PartnerRoleAssignment"]] = relationship(
        back_populates="partner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def roles(self) -> list[PartnerRole]:
        return sorted(
            (PartnerRole(assignment.role) for assignment in self.role_assignments),
            key=lambda role: role.value,
        )

    def has_role(self, role: PartnerRole) -> bool:
        return any(assignment.role == role.value for assignment in self.role_assignments)


class PartnerRoleAssignment(Base):
    __tablename__ = "partner_roles"
    __table_args__ = (
        CheckConstraint(f"role IN ({_ROLE_VALUES})", name="role_valid"),
    )

    partner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partners.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)

    partner: Mapped[Partner] = relationship(back_populates="role_assignments")
