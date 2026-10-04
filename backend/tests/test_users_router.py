from io import BytesIO
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.dependencies import get_current_user, get_db_session
from app.core.security import hash_password
from app.infrastructure.db.models.user import User
from app.main import app
from app.presentation.api.v1.routers import users as users_router


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_password() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password=hash_password("CorrectPass123!"),
        is_active=True,
    )

    class Session:
        async def commit(self) -> None:
            pass

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: Session()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "WrongPass123!",
                    "new_password": "NewStrong123!",
                },
            )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_avatar_upload_rejects_mismatched_content_type() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password=hash_password("CorrectPass123!"),
        is_active=True,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: None
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/users/me/avatar",
                files={"file": ("avatar.png", b"not-a-png", "image/png")},
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_avatar_upload_rejects_malformed_image_with_valid_signature() -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password=hash_password("CorrectPass123!"),
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: None
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/users/me/avatar",
                files={
                    "file": (
                        "avatar.png",
                        b"\x89PNG\r\n\x1a\nnot-an-image",
                        "image/png",
                    )
                },
            )
        assert response.status_code == 415
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_avatar_upload_stores_image_and_updates_profile(tmp_path, monkeypatch) -> None:
    user = User(
        id=uuid4(),
        email="user@example.com",
        hashed_password=hash_password("CorrectPass123!"),
        avatar_url="/media/avatars/old.png",
        is_active=True,
    )
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()
    old_avatar = avatar_dir / "old.png"
    old_avatar.write_bytes(b"old-avatar")

    class Session:
        committed = False

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            self.committed = True

    session = Session()
    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color="red").save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    monkeypatch.setattr(
        users_router,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"media_dir": str(tmp_path), "media_base_url": "/media"},
        )(),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/users/me/avatar",
                files={
                    "file": (
                        "avatar.png",
                        image_bytes,
                        "image/png",
                    )
                },
            )

        assert response.status_code == 200
        avatar_url = response.json()["avatar_url"]
        saved_avatar = avatar_dir / avatar_url.rsplit("/", 1)[-1]
        assert saved_avatar.read_bytes() == image_bytes
        assert user.avatar_url == avatar_url
        assert session.committed
        assert not old_avatar.exists()
    finally:
        app.dependency_overrides.clear()
