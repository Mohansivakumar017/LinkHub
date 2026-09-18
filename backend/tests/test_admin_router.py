from datetime import datetime
from uuid import UUID, uuid4

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

MISSING_UUID = UUID("00000000-0000-0000-0000-000000000000")
TARGET_UUID = UUID("11111111-1111-1111-1111-111111111111")
ACTIVE_LINK_UUID = UUID("22222222-2222-2222-2222-222222222222")
DELETED_LINK_UUID = UUID("33333333-3333-3333-3333-333333333333")


class FakeAdminRepository:
    def __init__(self, session) -> None:
        self._session = session
        self.audit_calls: list[tuple] = []

    def _new_user(self, user_id: UUID, email: str = "admin@example.com",
                  is_platform_admin: bool = True) -> User:
        user = User(
            id=user_id,
            email=email,
            hashed_password="hashed",
            is_active=True,
            is_platform_admin=is_platform_admin,
        )
        user.full_name = "User Name"
        user.created_at = datetime.utcnow()
        return user

    async def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        return [self._new_user(uuid4())], 1

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
        log.ip_address = "203.0.113.5"
        return [log], 1

    async def get_user(self, user_id: UUID) -> User | None:
        if user_id == MISSING_UUID:
            return None
        if user_id == TARGET_UUID:
            user = User(
                id=user_id,
                email="target@example.com",
                hashed_password="hashed",
                is_active=True,
                is_platform_admin=False,
            )
            user.full_name = "Target User"
            return user
        return self._new_user(user_id, "self@example.com", True)

    async def set_user_active(self, user: User, is_active: bool) -> None:
        user.is_active = is_active

    async def set_user_platform_admin(
        self, user: User, is_platform_admin: bool
    ) -> None:
        user.is_platform_admin = is_platform_admin

    async def get_url(self, url_id: UUID) -> URL | None:
        if url_id == MISSING_UUID:
            return None
        if url_id == DELETED_LINK_UUID:
            url = URL(
                id=url_id,
                short_code="deleted-code",
                original_url="https://example.com/deleted",
                organization_id=uuid4(),
                owner_user_id=uuid4(),
            )
            url.is_deleted = True
            url.is_archived = False
            url.created_at = datetime.utcnow()
            return url
        url = URL(
            id=url_id,
            short_code="active-code",
            original_url="https://example.com/active",
            organization_id=uuid4(),
            owner_user_id=uuid4(),
        )
        url.is_deleted = False
        url.is_archived = False
        url.created_at = datetime.utcnow()
        return url

    async def restore_url(self, url: URL) -> None:
        url.is_deleted = False
        url.deleted_at = None

    async def hard_delete_url(self, url: URL) -> None:
        return None

    async def record_audit(
        self,
        actor_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.audit_calls.append((actor_user_id, action, resource_type, resource_id, details))


class _FakeSession:
    async def commit(self) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


async def fake_db_session():
    yield _FakeSession()


def _admin_user(admin_id: UUID | None = None) -> User:
    uid = admin_id or uuid4()
    user = User(
        id=uid,
        email="admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_platform_admin=True,
    )
    user.full_name = "Platform Admin"
    return user


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
        assert logs.json()["items"][0]["ip_address"] == "203.0.113.5"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_set_user_active_bans_user(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    admin_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _admin_user(admin_id)
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/users/{TARGET_UUID}/active",
                json={"is_active": False},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(TARGET_UUID)
        assert body["is_active"] is False
        assert body["is_platform_admin"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_set_user_active_prevents_self_deactivate(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    admin_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _admin_user(admin_id)
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/users/{admin_id}/active",
                json={"is_active": False},
            )
        assert response.status_code == 400
        assert "own account" in response.json()["error"]["message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_set_user_active_missing_user_is_404(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/users/{MISSING_UUID}/active",
                json={"is_active": True},
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_set_user_platform_admin_promotes_user(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    admin_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _admin_user(admin_id)
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/users/{TARGET_UUID}/platform-admin",
                json={"is_platform_admin": True},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(TARGET_UUID)
        assert body["is_platform_admin"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_set_user_platform_admin_prevents_self_revoke(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    admin_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: _admin_user(admin_id)
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/users/{admin_id}/platform-admin",
                json={"is_platform_admin": False},
            )
        assert response.status_code == 400
        assert "own platform admin" in response.json()["error"]["message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_action_endpoints_require_admin(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _regular_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            ban = await client.patch(
                f"/api/v1/admin/users/{TARGET_UUID}/active",
                json={"is_active": False},
            )
            promote = await client.patch(
                f"/api/v1/admin/users/{TARGET_UUID}/platform-admin",
                json={"is_platform_admin": True},
            )
            restore = await client.patch(
                f"/api/v1/admin/links/{DELETED_LINK_UUID}/restore"
            )
            hard_del = await client.delete(
                f"/api/v1/admin/links/{ACTIVE_LINK_UUID}"
            )
        assert ban.status_code == 403
        assert promote.status_code == 403
        assert restore.status_code == 403
        assert hard_del.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_restore_deleted_link(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/links/{DELETED_LINK_UUID}/restore"
            )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(DELETED_LINK_UUID)
        assert body["is_deleted"] is False
        assert body["short_code"] == "deleted-code"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_restore_active_link_is_400(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/admin/links/{ACTIVE_LINK_UUID}/restore"
            )
        assert response.status_code == 400
        assert "not deleted" in response.json()["error"]["message"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_hard_delete_link_returns_204(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/admin/links/{ACTIVE_LINK_UUID}"
            )
        assert response.status_code == 204
        assert response.content == b""
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_hard_delete_missing_link_is_404(monkeypatch) -> None:
    monkeypatch.setattr(admin_module, "AdminRepository", FakeAdminRepository)
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/admin/links/{MISSING_UUID}"
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
