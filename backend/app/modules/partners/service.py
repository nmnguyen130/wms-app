from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.exceptions import AppException
from app.core.pagination import PaginationParams
from app.modules.auth.model import User
from app.modules.partners.model import Partner, PartnerRole, PartnerRoleAssignment
from app.modules.partners.schemas import PartnerCreate, PartnerUpdate


def _role_values(roles: Iterable[PartnerRole]) -> str:
    return ",".join(sorted(role.value for role in roles))


def _sync_roles(partner: Partner, roles: set[PartnerRole]) -> None:
    desired = {role.value for role in roles}
    current = {assignment.role: assignment for assignment in partner.role_assignments}
    for role_value, assignment in current.items():
        if role_value not in desired:
            partner.role_assignments.remove(assignment)
    for role_value in desired - current.keys():
        partner.role_assignments.append(PartnerRoleAssignment(role=role_value))


class PartnerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get(self, partner_id: UUID, *, lock: bool = False) -> Partner:
        stmt = select(Partner).where(Partner.id == partner_id)
        if lock:
            stmt = stmt.with_for_update()
        partner = await self.db.scalar(stmt)
        if partner is None:
            raise AppException.not_found("Partner")
        return partner

    async def _ensure_code_available(self, code: str, *, exclude_id: UUID | None = None) -> None:
        stmt = select(Partner.id).where(Partner.code == code)
        if exclude_id is not None:
            stmt = stmt.where(Partner.id != exclude_id)
        if await self.db.scalar(stmt) is not None:
            raise AppException.conflict("Partner code already exists")

    async def create(self, actor: User, data: PartnerCreate) -> Partner:
        code = data.code.strip()
        await self._ensure_code_available(code)
        partner = Partner(
            code=code,
            name=data.name.strip(),
            email=str(data.email).lower() if data.email else None,
            phone=data.phone.strip() if data.phone else None,
            address=data.address,
        )
        _sync_roles(partner, data.roles)
        self.db.add(partner)
        await self.db.flush()
        record_audit(
            self.db,
            actor_id=actor.id,
            action="PARTNER_CREATED",
            entity_type="Partner",
            entity_id=partner.id,
            details=f"roles={_role_values(data.roles)}",
        )
        return partner

    async def list(
        self,
        pagination: PaginationParams,
        *,
        role: PartnerRole | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Partner], int]:
        conditions = []
        if role is not None:
            conditions.append(
                Partner.role_assignments.any(PartnerRoleAssignment.role == role.value)
            )
        if is_active is not None:
            conditions.append(Partner.is_active.is_(is_active))

        total = (
            await self.db.scalar(select(func.count()).select_from(Partner).where(*conditions)) or 0
        )
        stmt = (
            select(Partner)
            .where(*conditions)
            .order_by(Partner.code)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        return list((await self.db.scalars(stmt)).all()), total

    async def get(self, partner_id: UUID) -> Partner:
        return await self._get(partner_id)

    async def update(self, actor: User, partner_id: UUID, data: PartnerUpdate) -> Partner:
        partner = await self._get(partner_id, lock=True)
        updates = data.model_dump(exclude_unset=True)

        if updates.get("code") is not None:
            code = updates["code"].strip()
            await self._ensure_code_available(code, exclude_id=partner.id)
            partner.code = code
        if updates.get("name") is not None:
            partner.name = updates["name"].strip()
        if "email" in updates:
            partner.email = str(updates["email"]).lower() if updates["email"] else None
        if "phone" in updates:
            partner.phone = updates["phone"].strip() if updates["phone"] else None
        if "address" in updates:
            partner.address = updates["address"]
        if updates.get("is_active") is not None:
            partner.is_active = updates["is_active"]
        if updates.get("roles") is not None:
            _sync_roles(partner, updates["roles"])

        record_audit(
            self.db,
            actor_id=actor.id,
            action="PARTNER_UPDATED",
            entity_type="Partner",
            entity_id=partner.id,
            details=f"roles={_role_values(partner.roles)}",
        )
        await self.db.flush()
        return partner

    async def delete(self, actor: User, partner_id: UUID) -> None:
        partner = await self._get(partner_id, lock=True)
        partner.is_active = False
        record_audit(
            self.db,
            actor_id=actor.id,
            action="PARTNER_DEACTIVATED",
            entity_type="Partner",
            entity_id=partner.id,
        )
        await self.db.flush()
