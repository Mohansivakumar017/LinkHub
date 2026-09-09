from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.api_key_service import (
    ApiKeyNotFoundError,
    ApiKeyService,
)
from app.core.dependencies import get_current_user
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: CreateApiKeyRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    user_id = UUID(str(current_user.id))
    created = await ApiKeyService(session).create(user_id, payload.name)
    return {
        "id": str(created.id),
        "name": created.name,
        "key": created.key,
        "key_prefix": created.key_prefix,
    }


@router.get("")
async def list_api_keys(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str | int | bool | None]]:
    items = await ApiKeyService(session).list(UUID(str(current_user.id)))
    return [
        {
            "id": str(item.id),
            "name": item.name,
            "key_prefix": item.key_prefix,
            "is_active": item.is_active,
            "last_used_at": item.last_used_at.isoformat()
            if item.last_used_at
            else None,
            "usage_count": item.usage_count,
            "created_at": item.created_at.isoformat(),
            "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
        }
        for item in items
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        await ApiKeyService(session).revoke(UUID(str(current_user.id)), key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{key_id}/rotate", status_code=status.HTTP_201_CREATED)
async def rotate_api_key(
    key_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        rotated = await ApiKeyService(session).rotate(UUID(str(current_user.id)), key_id)
    except ApiKeyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": str(rotated.id),
        "name": rotated.name,
        "key": rotated.key,
        "key_prefix": rotated.key_prefix,
    }
