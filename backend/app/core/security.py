from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_MAX_PASSWORD_BYTES = 72
_RESERVED_CLAIMS = frozenset({"sub", "type", "jti", "iat", "exp"})


def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt."""
    raw = password.encode("utf-8")
    if len(raw) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {_MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify plain password against hashed password."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except ValueError:
        return False


def _encode_token(
    subject: str | UUID,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expire = now + expires_delta
    jti = uuid4().hex

    payload = {
        "sub": str(subject),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    if extra_claims:
        reserved = _RESERVED_CLAIMS.intersection(extra_claims)
        if reserved:
            raise ValueError(f"extra_claims must not override reserved claims: {sorted(reserved)}")
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm=_ALGORITHM)
    return token, jti, expire


def create_access_token(
    subject: str | UUID,
    extra_claims: dict | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create JWT access token. Returns (token, jti, expire_datetime)."""
    return _encode_token(
        subject,
        "access",
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims,
    )


def create_refresh_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create JWT refresh token. Returns (token, jti, expire_datetime)."""
    return _encode_token(
        subject,
        "refresh",
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate JWT token claims."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[_ALGORITHM],
        options={"require": ["sub", "type", "jti", "iat", "exp"]},
    )
    if payload.get("type") != expected_type:
        raise ValueError(f"Invalid token type: expected '{expected_type}', got '{payload.get('type')}'")
    return payload
