from collections.abc import AsyncIterator, Callable
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import get_current_context
from app.core.database import async_session_factory
from app.core.exceptions import AppException
from app.core.permissions import Permission, enforce_permission
from app.core.security import decode_token
from app.modules.auth.model import User

oauth2_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Provide a transactional asynchronous database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    auth: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if auth is None:
        raise AppException.unauthorized()

    try:
        payload = decode_token(auth.credentials, expected_type="access")
        user_id = UUID(payload["sub"])
        token_version = int(payload["tv"])
    except jwt.ExpiredSignatureError:
        raise AppException.unauthorized("Access token has expired", error_code="TOKEN_EXPIRED")
    except Exception:
        raise AppException.unauthorized("Invalid access token")

    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise AppException.unauthorized("User is inactive or session invalidated")

    ctx = get_current_context()
    if ctx is not None:
        ctx.user_id = user.id

    return user


def require_permission(permission: Permission) -> Callable[..., User]:
    async def _guard(current_user: User = Depends(get_current_user)) -> User:
        enforce_permission(current_user.role, permission)
        return current_user

    return _guard
