import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_password_over_bcrypt_limit_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("a" * 73)


def test_access_token_claims() -> None:
    token, jti, _ = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["jti"] == jti
    assert payload["type"] == "access"


def test_reserved_claim_cannot_be_overridden() -> None:
    with pytest.raises(ValueError):
        create_access_token("user-1", {"type": "refresh"})


def test_refresh_token_is_not_accepted_as_access() -> None:
    token, _, _ = create_refresh_token("user-1")
    with pytest.raises(ValueError):
        decode_token(token)
