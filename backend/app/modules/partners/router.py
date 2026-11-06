from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.permissions import Permission
from app.modules.auth.model import User
from app.modules.partners.model import PartnerRole
from app.modules.partners.schemas import PartnerCreate, PartnerResponse, PartnerUpdate
from app.modules.partners.service import PartnerService

router = APIRouter(prefix="/partners", tags=["Partners"])


@router.post("", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_partner(
    data: PartnerCreate,
    current_user: User = Depends(require_permission(Permission.PARTNERS_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    partner = await PartnerService(db).create(current_user, data)
    return PartnerResponse.model_validate(partner)


@router.get("", response_model=PaginatedResponse[PartnerResponse])
async def list_partners(
    pagination: PaginationParams = Depends(),
    role: PartnerRole | None = None,
    is_active: bool | None = None,
    _: User = Depends(require_permission(Permission.PARTNERS_READ)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PartnerResponse]:
    partners, total = await PartnerService(db).list(
        pagination,
        role=role,
        is_active=is_active,
    )
    return paginate(
        [PartnerResponse.model_validate(partner) for partner in partners],
        total,
        pagination,
    )


@router.get("/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: UUID,
    _: User = Depends(require_permission(Permission.PARTNERS_READ)),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    return PartnerResponse.model_validate(await PartnerService(db).get(partner_id))


@router.patch("/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: UUID,
    data: PartnerUpdate,
    current_user: User = Depends(require_permission(Permission.PARTNERS_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    partner = await PartnerService(db).update(current_user, partner_id, data)
    return PartnerResponse.model_validate(partner)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner(
    partner_id: UUID,
    current_user: User = Depends(require_permission(Permission.PARTNERS_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await PartnerService(db).delete(current_user, partner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
