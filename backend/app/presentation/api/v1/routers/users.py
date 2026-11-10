import warnings
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.security import hash_password_async, verify_password_async
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])
MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
AVATAR_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password_byte_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 UTF-8 bytes")
        return value


@router.get("/me")
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> dict[str, str | bool | None]:
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "is_email_verified": current_user.is_email_verified,
        "is_platform_admin": current_user.is_platform_admin,
        "created_at": current_user.created_at.isoformat(),
    }


@router.patch("/me")
async def update_profile(
    payload: UpdateProfileRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | bool | None]:
    changes = payload.model_dump(exclude_unset=True)
    if "full_name" in changes:
        current_user.full_name = changes["full_name"]
    await UserRepository(session).update_profile(
        current_user, current_user.full_name, current_user.avatar_url
    )
    await session.commit()
    return await get_profile(current_user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    if not await verify_password_async(
        payload.current_password, str(current_user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current password is incorrect",
        )
    await UserRepository(session).update_password(
        current_user, await hash_password_async(payload.new_password)
    )
    await RefreshTokenRepository(session).revoke_all_for_user(UUID(str(current_user.id)))
    await session.commit()


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Store a bounded avatar upload using a generated server-side filename."""
    suffix = ALLOWED_AVATAR_TYPES.get(file.content_type or "")
    if suffix is None:
        raise HTTPException(status_code=415, detail="unsupported avatar image type")

    content = await file.read(MAX_AVATAR_BYTES + 1)
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="avatar exceeds 5 MiB limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                if image.format != AVATAR_FORMATS[file.content_type or ""]:
                    raise ValueError("avatar format does not match content type")
                image.verify()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        SyntaxError,
        ValueError,
        UnidentifiedImageError,
    ) as exc:
        raise HTTPException(
            status_code=415, detail="avatar content does not match image type"
        ) from exc

    settings = get_settings()
    avatar_dir = Path(settings.media_dir) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    destination = avatar_dir / filename
    destination.write_bytes(content)

    avatar_url = f"{settings.media_base_url}/avatars/{filename}"
    previous_avatar_url = current_user.avatar_url
    await UserRepository(session).update_profile(
        current_user, current_user.full_name, avatar_url
    )
    await session.commit()
    if previous_avatar_url and previous_avatar_url.startswith(
        f"{settings.media_base_url}/avatars/"
    ):
        avatar_root = (Path(settings.media_dir) / "avatars").resolve()
        previous_path = (
            avatar_root / previous_avatar_url.rsplit("/", 1)[-1]
        ).resolve()
        if previous_path.parent == avatar_root:
            previous_path.unlink(missing_ok=True)
    return {"avatar_url": avatar_url}
