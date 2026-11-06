from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_permission
from app.utils.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.permissions import Permission
from app.modules.auth.model import User
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
    UserAccessUpdate,
    UserCreate,
    UserProfileUpdate,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])
users_router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await AuthService(db).login(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await AuthService(db).refresh(data.refresh_token)


@router.post("/logout", response_model=dict[str, str])
async def logout(
    data: LogoutRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await AuthService(db).logout(current_user, data)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await AuthService(db).change_password(current_user, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@users_router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await AuthService(db).update_profile(current_user, data)
    return UserResponse.model_validate(user)


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_permission(Permission.USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await AuthService(db).create_user(current_user, data)
    return UserResponse.model_validate(user)


@users_router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    _: User = Depends(require_permission(Permission.USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    users, total = await AuthService(db).list_users(pagination)
    return paginate([UserResponse.model_validate(user) for user in users], total, pagination)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    _: User = Depends(require_permission(Permission.USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return UserResponse.model_validate(await AuthService(db).get_user(user_id))


@users_router.patch("/{user_id}/access", response_model=UserResponse)
async def update_user_access(
    user_id: UUID,
    data: UserAccessUpdate,
    current_user: User = Depends(require_permission(Permission.USERS_MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await AuthService(db).update_access(current_user, user_id, data)
    return UserResponse.model_validate(user)
