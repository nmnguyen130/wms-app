from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.config import settings
from app.core.exceptions import AppException
from app.utils.pagination import PaginationParams
from app.core.permissions import Role
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.model import RefreshToken, User
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    TokenResponse,
    UserAccessUpdate,
    UserCreate,
    UserProfileUpdate,
)
from app.modules.warehouses.model import Warehouse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_user_by_email(self, email: str, *, lock: bool = False) -> User | None:
        stmt = select(User).where(User.email == email.strip().lower())
        if lock:
            stmt = stmt.with_for_update()
        return await self.db.scalar(stmt)

    async def _get_user(self, user_id: UUID, *, lock: bool = False) -> User:
        stmt = select(User).where(User.id == user_id)
        if lock:
            stmt = stmt.with_for_update()
        user = await self.db.scalar(stmt)
        if user is None:
            raise AppException.not_found("User")
        return user

    async def _resolve_warehouses(self, warehouse_ids: list[UUID]) -> list[Warehouse]:
        unique_ids = list(dict.fromkeys(warehouse_ids))
        if not unique_ids:
            return []

        warehouses = list(
            (await self.db.scalars(select(Warehouse).where(Warehouse.id.in_(unique_ids)))).all()
        )
        if len(warehouses) != len(unique_ids):
            raise AppException.bad_request("One or more warehouses do not exist")
        return warehouses

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token, _, _ = create_access_token(user.id, token_version=user.token_version)
        refresh_token, jti, expires_at = create_refresh_token(
            user.id,
            token_version=user.token_version,
        )
        self.db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
        await self.db.flush()
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    async def _revoke_all_refresh_tokens(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        for token in (await self.db.scalars(stmt)).all():
            token.revoked_at = now
        await self.db.flush()

    async def create_user(self, actor: User, data: UserCreate) -> User:
        email = data.email.strip().lower()
        if await self._get_user_by_email(email) is not None:
            raise AppException.conflict("Email already registered")

        user = User(
            full_name=data.full_name.strip(),
            email=email,
            password_hash=hash_password(data.password),
            role=data.role.value,
            warehouses=await self._resolve_warehouses(data.warehouse_ids),
        )
        self.db.add(user)
        await self.db.flush()
        record_audit(
            self.db,
            actor_id=actor.id,
            action="USER_CREATED",
            entity_type="User",
            entity_id=user.id,
            details=f"role={user.role}",
        )
        return user

    async def list_users(self, pagination: PaginationParams) -> tuple[list[User], int]:
        total = await self.db.scalar(select(func.count()).select_from(User)) or 0
        stmt = (
            select(User)
            .order_by(User.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        return list((await self.db.scalars(stmt)).all()), total

    async def get_user(self, user_id: UUID) -> User:
        return await self._get_user(user_id)

    async def login(self, data: LoginRequest) -> TokenResponse:
        email = data.email.strip().lower()
        user = await self._get_user_by_email(email, lock=True)
        now = datetime.now(UTC)

        if user is not None and user.locked_until is not None and user.locked_until > now:
            retry_after = max(1, int((user.locked_until - now).total_seconds()))
            raise AppException.locked(
                "Account is temporarily locked due to repeated failed login attempts",
                retry_after=retry_after,
            )

        if user is None or not verify_password(data.password, user.password_hash):
            if user is not None:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                    user.locked_until = now + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                # get_db rolls back on exceptions, so persist the counter before raising.
                await self.db.commit()
            raise AppException.unauthorized("Incorrect email or password")

        if not user.is_active:
            raise AppException.forbidden("User account is inactive")

        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.flush()
        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
            user_id = UUID(payload["sub"])
            jti = str(payload["jti"])
            token_version = int(payload["tv"])
        except Exception:
            raise AppException.unauthorized("Invalid or expired refresh token") from None

        user = await self.db.scalar(select(User).where(User.id == user_id).with_for_update())
        if user is None or not user.is_active or user.token_version != token_version:
            raise AppException.unauthorized("Invalid or expired refresh token")

        record = await self.db.get(RefreshToken, jti, with_for_update=True)
        now = datetime.now(UTC)
        if record is None or record.expires_at <= now:
            raise AppException.unauthorized("Invalid or expired refresh token")

        if record.revoked_at is not None:
            await self._revoke_all_refresh_tokens(user.id)
            # Persist the security response before raising; get_db rolls back on errors.
            await self.db.commit()
            raise AppException.unauthorized("Refresh token reuse detected; all sessions revoked")

        record.revoked_at = now
        await self.db.flush()
        return await self._issue_tokens(user)

    async def logout(self, user: User, data: LogoutRequest | None) -> dict[str, str]:
        if data is not None and data.refresh_token:
            try:
                payload = decode_token(data.refresh_token, expected_type="refresh")
                jti = str(payload["jti"])
            except Exception:
                jti = None

            if jti is not None:
                record = await self.db.get(RefreshToken, jti)
                if (
                    record is not None
                    and record.user_id == user.id
                    and record.revoked_at is None
                ):
                    record.revoked_at = datetime.now(UTC)
                    await self.db.flush()

        return {"status": "logged_out"}

    async def change_password(self, user: User, data: PasswordChangeRequest) -> User:
        locked_user = await self._get_user(user.id, lock=True)
        if not verify_password(data.current_password, locked_user.password_hash):
            raise AppException.unauthorized("Current password is incorrect")

        locked_user.password_hash = hash_password(data.new_password)
        locked_user.token_version += 1
        await self._revoke_all_refresh_tokens(locked_user.id)
        record_audit(
            self.db,
            actor_id=locked_user.id,
            action="USER_PASSWORD_CHANGED",
            entity_type="User",
            entity_id=locked_user.id,
        )
        await self.db.flush()
        return locked_user

    async def update_profile(self, user: User, data: UserProfileUpdate) -> User:
        locked_user = await self._get_user(user.id, lock=True)
        locked_user.full_name = data.full_name.strip()
        record_audit(
            self.db,
            actor_id=locked_user.id,
            action="USER_PROFILE_UPDATED",
            entity_type="User",
            entity_id=locked_user.id,
        )
        await self.db.flush()
        return locked_user

    async def update_access(
        self,
        actor: User,
        target_user_id: UUID,
        data: UserAccessUpdate,
    ) -> User:
        target = await self._get_user(target_user_id, lock=True)
        target_is_admin = target.role == Role.ADMIN.value
        demoting_admin = target_is_admin and data.role is not None and data.role != Role.ADMIN
        deactivating_admin = target_is_admin and data.is_active is False

        if target.id == actor.id and (demoting_admin or deactivating_admin):
            raise AppException.bad_request("Admin cannot demote or deactivate their own account")

        if demoting_admin or deactivating_admin:
            active_admins = (
                await self.db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
                )
                or 0
            )
            if active_admins <= 1:
                raise AppException.conflict("Cannot demote or deactivate the last active admin")

        if data.role is not None:
            target.role = data.role.value
        if data.warehouse_ids is not None:
            target.warehouses = await self._resolve_warehouses(data.warehouse_ids)
        if data.is_active is not None:
            target.is_active = data.is_active

        target.token_version += 1
        await self._revoke_all_refresh_tokens(target.id)
        record_audit(
            self.db,
            actor_id=actor.id,
            action="USER_ACCESS_UPDATED",
            entity_type="User",
            entity_id=target.id,
            details=f"role={target.role}, active={target.is_active}",
        )
        await self.db.flush()
        return target
