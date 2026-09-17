from datetime import datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db_session
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.url import URL
from app.infrastructure.db.models.user import User
from app.main import app
from app.presentation.api.v1.routers import admin as admin_module


class FakeAdminRepository:
    def __init__(self, session) -> None:
        self._session = session

    async def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        user = User(
            id=uuid4(),
            email="admin@example.com",
            hashed_password="hashed",
            is_active=True,
            is_platform_admin=True,
        )
        user.full_name = "Platform Admin"
        user.created_at = datetime.utcnow()
        return [user], 1

    async def list_organizations(
        self, offset: int, limit: int
    ) -> tuple[list[Organization], int]:
        org = Organization(
            id=uuid4(),
            name="Acme",
            slug="acme",
            owner_user_id=uuid4(),
        )
        org.created_at = datetime.utcnow()
        return [org], 1

    async def list_urls(self, offset: int, limit: int) -> tuple[list[URL], int]:
        link = URL(
            id=uuid4(),
            short_code="abc123",
            original_url="https://example.com",
            organization_id=uuid4(),
            owner_user_id=uuid4(),
        )
        link.is_archived = False
        link.is_deleted = False
        link.created_at = datetime.utcnow()
        return [link], 1

    async def metrics(self) -> dict[str, int]:
        return {
            "users": 10,
            "active_users": 8,
            "organizations": 3,
            "urls": 42,
            "clicks": 100,
        }

    async def list_audit_logs(
        self,
        offset: int,
        limit: int,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        log = AuditLog(
            id=uuid4(),
            actor_user_id=uuid4(),
            action="auth.logged_in",
            resource_type="user",
            resource_id=str(uuid4()),
            details={"email": "admin@example.com"},
        )
        log.created_at = datetime.utcnow()
        return [log], 1


async def fake_db_session():
    yield None


def _admin_user() -> User:
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_platform_admin=True,
    )


def _regular_user() -> User:
    return User(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        is_active=True,
        is_platform_admin=False,
    )


@pytest.mark.asyncio
async def test_admin_requires_platform_admin(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _regular_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/admin/metrics")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_metrics_for_platform_admin(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/admin/metrics")
        assert response.status_code == 200
        assert response.json() == {
            "users": 10,
            "active_users": 8,
            "organizations": 3,
            "urls": 42,
            "clicks": 100,
        }
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_bootstrap_via_configured_email(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", "bootstrap@example.com")
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid4(),
        email="bootstrap@example.com",
        hashed_password="hashed",
        is_active=True,
        is_platform_admin=False,
    )
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/admin/users")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "admin@example.com"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_admin_list_endpoints_return_paginated_payload(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            users = await client.get("/api/v1/admin/users")
            orgs = await client.get("/api/v1/admin/organizations")
            links = await client.get("/api/v1/admin/links")
            logs = await client.get(
                "/api/v1/admin/audit-logs",
                params={"action": "auth.logged_in", "resource_type": "user"},
            )

        assert users.status_code == 200
        assert users.json()["items"][0]["is_platform_admin"] is True

        assert orgs.status_code == 200
        assert orgs.json()["items"][0]["slug"] == "acme"

        assert links.status_code == 200
        assert links.json()["items"][0]["short_code"] == "abc123"

        assert logs.status_code == 200
        assert logs.json()["items"][0]["action"] == "auth.logged_in"
    finally:
        app.dependency_overrides.clear()
