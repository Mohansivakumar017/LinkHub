import hashlib
import secrets

import bcrypt

MAX_BCRYPT_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    plain_password_bytes = plain_password.encode("utf-8")
    if len(plain_password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("password must be at most 72 UTF-8 bytes")
    hashed = bcrypt.hashpw(plain_password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_password_bytes = plain_password.encode("utf-8")
    if len(plain_password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        return False
    hashed_password_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
