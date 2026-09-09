from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.presentation.api.v1.routers import urls as urls_router_module


class FakeURLService:
    def __init__(self, session) -> None:
        self._session = session

    async def create_url(self, **kwargs):
        return type(
            "URL",
            (),
            {
                "id": uuid4(),
                "organization_id": kwargs["organization_id"],
                "owner_user_id": kwargs["owner_user_id"],
                "original_url": kwargs["original_url"],
                "short_code": kwargs.get("custom_alias") or "abc12345",
                "custom_alias": kwargs.get("custom_alias"),
                "title": kwargs.get("title"),
                "expires_at": kwargs.get("expires_at"),
                "one_time": kwargs.get("one_time", False),
                "click_limit": kwargs.get("click_limit"),
                "is_private": kwargs.get("is_private", False),
                "is_archived": False,
            },
        )()

    async def list_urls(self, organization_id, requester_user_id, **kwargs):
        return []

    async def update_url(self, organization_id, requester_user_id, url_id, **changes):
        return type(
            "URL",
            (),
            {
                "id": url_id,
                "organization_id": organization_id,
                "owner_user_id": requester_user_id,
                "original_url": changes.get("original_url", "https://example.com"),
                "short_code": changes.get("custom_alias", "abc12345"),
                "custom_alias": changes.get("custom_alias"),
                "title": changes.get("title", "Updated"),
                "expires_at": None,
                "one_time": False,
                "click_limit": None,
                "is_private": False,
                "is_archived": False,
            },
        )()

    async def delete_url(self, organization_id, requester_user_id, url_id):
        return None

    async def archive_url(self, organization_id, requester_user_id, url_id):
        return None

    async def restore_url(self, organization_id, requester_user_id, url_id):
        return None

    async def duplicate_url(self, organization_id, requester_user_id, url_id):
        return await self.create_url(
            organization_id=organization_id,
            owner_user_id=requester_user_id,
            original_url="https://example.com",
        )

    async def bulk_create(self, organization_id, requester_user_id, rows):
        created = [
            await self.create_url(
                organization_id=organization_id,
                owner_user_id=requester_user_id,
                original_url=row["original_url"],
            )
            for row in rows
        ]
        return created, []

    async def bulk_delete(self, organization_id, requester_user_id, ids):
        return len(ids)


class FakeAnalyticsService:
    def __init__(self, session) -> None:
        self._session = session

    async def track_click(self, short_code: str, context, password=None):
        return {"short_code": short_code, "original_url": "https://example.com"}


async def fake_db_session():
    yield None


async def fake_current_user():
    return type("User", (), {"id": uuid4(), "is_active": True})()


def test_urls_router_contract(monkeypatch) -> None:
    monkeypatch.setattr(urls_router_module, "URLService", FakeURLService)
    monkeypatch.setattr(urls_router_module, "AnalyticsService", FakeAnalyticsService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)

    org_id = str(uuid4())
    url_id = str(uuid4())

    create_res = client.post(
        "/api/v1/urls",
        json={
            "organization_id": org_id,
            "original_url": "https://example.com",
            "custom_alias": "acme",
            "title": "Acme",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert create_res.status_code == 201

    list_res = client.get(f"/api/v1/urls/organizations/{org_id}")
    assert list_res.status_code == 200

    resolve_res = client.get("/api/v1/urls/resolve/acme")
    assert resolve_res.status_code == 200

    redirect_res = client.get("/api/v1/urls/r/acme", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://example.com"

    update_res = client.patch(
        f"/api/v1/urls/{url_id}?organization_id={org_id}",
        json={"title": "Updated"},
    )
    assert update_res.status_code == 200

    archive_res = client.post(f"/api/v1/urls/{url_id}/archive?organization_id={org_id}")
    assert archive_res.status_code == 204

    restore_res = client.post(f"/api/v1/urls/{url_id}/restore?organization_id={org_id}")
    assert restore_res.status_code == 204

    duplicate_res = client.post(f"/api/v1/urls/{url_id}/duplicate?organization_id={org_id}")
    assert duplicate_res.status_code == 201

    bulk_create_res = client.post(
        "/api/v1/urls/bulk/create",
        json={
            "organization_id": org_id,
            "rows": [{"organization_id": org_id, "original_url": "https://example.com/a"}],
        },
    )
    assert bulk_create_res.status_code == 201

    bulk_delete_res = client.request(
        method="DELETE",
        url="/api/v1/urls/bulk/delete",
        json={"organization_id": org_id, "ids": [url_id]},
    )
    assert bulk_delete_res.status_code == 200

    delete_res = client.delete(f"/api/v1/urls/{url_id}?organization_id={org_id}")
    assert delete_res.status_code == 204

    app.dependency_overrides.clear()
