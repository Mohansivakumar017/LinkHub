from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import PyJWTError

from app.core.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    expiry = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_exp_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expiry,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def create_email_verification_token(subject: str) -> str:
    return create_access_token(
        subject=subject,
        expires_minutes=settings.verify_email_token_exp_minutes,
        extra_claims={"type": "verify_email"},
    )


def create_password_reset_token(subject: str) -> str:
    return create_access_token(
        subject=subject,
        expires_minutes=settings.reset_password_token_exp_minutes,
        extra_claims={"type": "reset_password"},
    )


def decode_token_with_type(token: str, expected_type: str) -> dict[str, Any]:
    payload = decode_token(token)
    token_type = payload.get("type")
    if token_type != expected_type:
        raise PyJWTError("invalid token type")
    return payload
