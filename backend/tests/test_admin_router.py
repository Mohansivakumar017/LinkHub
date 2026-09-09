from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db_session
from app.infrastructure.db.models.user import User
from app.main import app


@pytest.mark.asyncio
async def test_admin_requires_platform_admin(monkeypatch) -> None:
    user = User(id=uuid4(), email="user@example.com", is_active=True, is_platform_admin=False)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/admin/metrics")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
