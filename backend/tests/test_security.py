import pytest

from app.core.config import settings
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

VALID_PASSWORD = "Correct-Horse-9-Battery-Staple"
WEAK_PASSWORD = "correct horse battery staple"


def test_password_hash_roundtrip() -> None:
    hashed = hash_password(VALID_PASSWORD)
    assert hashed != VALID_PASSWORD
    assert verify_password(VALID_PASSWORD, hashed)
    assert not verify_password("Wrong-Password-9-Staple", hashed)


def test_password_must_meet_complexity_policy() -> None:
    with pytest.raises(ValueError):
        hash_password(WEAK_PASSWORD)


def test_password_over_bcrypt_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("Aa1!" + "a" * 69)


def test_access_token_claims() -> None:
    token, jti, _ = create_access_token("user-1", token_version=3)
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["type"] == "access"
    assert payload["tv"] == 3
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE


def test_reserved_claim_cannot_be_overridden() -> None:
    with pytest.raises(ValueError):
        create_access_token("user-1", {"type": "refresh"})


def test_refresh_token_is_not_accepted_as_access() -> None:
    token, _, _ = create_refresh_token("user-1")
    with pytest.raises(ValueError):
        decode_token(token)
