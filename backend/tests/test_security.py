import pytest

from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_and_verify():
    pw = "S3cur3P@ssw0rd"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)


def test_bcrypt_password_byte_limit_is_enforced_without_truncation():
    accepted = "a" * 72
    hashed = hash_password(accepted)

    assert verify_password(accepted, hashed)
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password("a" * 73)
    assert not verify_password("a" * 73, hashed)


def test_bcrypt_password_byte_limit_counts_utf8_bytes():
    accepted = "é" * 36
    hashed = hash_password(accepted)

    assert verify_password(accepted, hashed)
    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password("é" * 37)


def test_refresh_token_and_hash():
    t = generate_refresh_token()
    assert isinstance(t, str) and len(t) > 40
    h = hash_token(t)
    assert isinstance(h, str) and len(h) == 64
