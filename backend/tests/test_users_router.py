from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db_session
from app.core.security import hash_password
from app.infrastructure.db.models.user import User
from app.main import app


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
