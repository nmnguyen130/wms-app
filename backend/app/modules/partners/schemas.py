from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.modules.partners.model import PartnerRole

_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class PartnerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    roles: set[PartnerRole] = Field(min_length=1)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None


class PartnerUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50, pattern=_CODE_PATTERN)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    roles: set[PartnerRole] | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_update(self) -> "PartnerUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in self.model_fields_set & {"code", "name", "roles", "is_active"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    roles: list[PartnerRole]
    email: str | None
    phone: str | None
    address: str | None
    is_active: bool
