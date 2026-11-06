from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.permissions import Role
from app.core.security import validate_password_strength


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2048)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=2048)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=72)

    @model_validator(mode="after")
    def check_new_password(self) -> "PasswordChangeRequest":
        if self.new_password == self.current_password:
            raise ValueError("new_password must be different from current_password")
        validate_password_strength(self.new_password)
        return self


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)
    role: Role = Role.OPERATOR
    warehouse_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_password_policy(self) -> "UserCreate":
        validate_password_strength(self.password)
        return self


class UserAccessUpdate(BaseModel):
    role: Role | None = None
    warehouse_ids: list[UUID] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "UserAccessUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class UserProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    role: Role
    warehouse_ids: list[UUID]
    is_active: bool
    created_at: datetime
