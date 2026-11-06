from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "WMS Backend API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    API_V1_STR: str = "/api/v1"

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    POSTGRES_USER: str = "wms_app"
    POSTGRES_PASSWORD: SecretStr | None = None
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "wms"
    DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    JWT_SECRET: SecretStr
    JWT_ISSUER: str = "wms-backend"
    JWT_AUDIENCE: str = "wms-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    MAX_REQUEST_BODY_BYTES: int = 1_048_576

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        if len(self.JWT_SECRET.get_secret_value().encode()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")

        if self.DATABASE_URL:
            if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        else:
            password = self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else ""
            if not password:
                raise ValueError("POSTGRES_PASSWORD is required when DATABASE_URL is not set")
            self.DATABASE_URL = URL.create(
                drivername="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=password,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                database=self.POSTGRES_DB,
            ).render_as_string(hide_password=False)

        if "*" in self.cors_origins:
            raise ValueError("ALLOWED_ORIGINS must not contain '*'")

        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
