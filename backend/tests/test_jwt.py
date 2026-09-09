import pytest
from jwt import PyJWTError

from app.core.jwt import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_token,
    decode_token_with_type,
)


def test_jwt_create_and_decode():
    token = create_access_token(subject="12345", expires_minutes=5)
    payload = decode_token(token)
    assert payload["sub"] == "12345"
    assert payload["type"] == "access"


def test_token_type_validation():
    verify_token = create_email_verification_token(subject="12345")
    payload = decode_token_with_type(verify_token, "verify_email")
    assert payload["sub"] == "12345"

    reset_token = create_password_reset_token(subject="12345")
    with pytest.raises(PyJWTError):
        decode_token_with_type(reset_token, "verify_email")
