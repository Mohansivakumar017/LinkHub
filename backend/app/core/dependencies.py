from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.jwt import decode_token_with_type
from app.core.security import hash_token
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=True)
optional_bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token_with_type(token, "access")
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, PyJWTError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid access token",
        ) from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found or inactive",
        )
    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User | None:
    """Resolve an optional bearer identity for protected public-link access."""
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        payload = decode_token_with_type(token, "access")
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, PyJWTError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid access token",
        ) from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found or inactive",
        )
    return user


async def get_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require a platform administrator, with env-based bootstrap support."""
    configured_emails = {
        email.strip().lower()
        for email in get_settings().platform_admin_emails.split(",")
        if email.strip()
    }
    if not current_user.is_platform_admin and current_user.email.lower() not in configured_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="platform administrator access required",
        )
    return current_user


async def get_api_key_user(
    raw_api_key: str = Depends(api_key_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Authenticate an active service API key and return its owning user."""
    api_key = await ApiKeyRepository(session).get_active_by_hash(hash_token(raw_api_key))
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid API key",
        )
    user = await UserRepository(session).get_by_id(api_key.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner is inactive",
        )
    await session.commit()
    return user
