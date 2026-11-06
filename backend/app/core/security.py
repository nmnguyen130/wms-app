import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_MAX_PASSWORD_BYTES = 72
_MIN_PASSWORD_CHARS = 12
_RESERVED_CLAIMS = frozenset({"sub", "type", "jti", "iat", "exp", "tv", "iss", "aud"})


def validate_password_strength(password: str) -> bytes:
    """Enforce password length, bcrypt byte limit, and character complexity."""
    if len(password) < _MIN_PASSWORD_CHARS:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_CHARS} characters long")

    raw = password.encode("utf-8")
    if len(raw) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {_MAX_PASSWORD_BYTES} UTF-8 bytes")

    if not (
        re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
        and re.search(r"[^A-Za-z0-9]", password)
    ):
        raise ValueError("Password must include uppercase, lowercase, digit, and special character")

    return raw


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with a per-password salt."""
    raw = validate_password_strength(password)
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a plain password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False

    raw = plain_password.encode("utf-8")
    if len(raw) > _MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(raw, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def _encode_token(
    subject: str | UUID,
    token_type: str,
    expires_delta: timedelta,
    token_version: int,
    extra_claims: dict | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expire = now + expires_delta
    jti = uuid4().hex

    payload = {
        "sub": str(subject),
        "type": token_type,
        "tv": token_version,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": expire,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
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
    token_version: int = 1,
) -> tuple[str, str, datetime]:
    """Create a JWT access token. Returns (token, jti, expire_datetime)."""
    return _encode_token(
        subject,
        "access",
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_version,
        extra_claims,
    )


def create_refresh_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
    token_version: int = 1,
) -> tuple[str, str, datetime]:
    """Create a JWT refresh token. Returns (token, jti, expire_datetime)."""
    return _encode_token(
        subject,
        "refresh",
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_version,
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate JWT claims, issuer, audience, and token type."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
        options={"require": ["sub", "type", "tv", "jti", "iat", "exp", "iss", "aud"]},
    )
    if payload.get("type") != expected_type:
        raise ValueError(f"Invalid token type: expected '{expected_type}', got '{payload.get('type')}'")
    return payload
