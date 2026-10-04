from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.dependencies import ApiKeyPrincipal
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


class UsedOneTimeAnalyticsService(FakeAnalyticsService):
    async def track_click(self, short_code: str, context, *args, **kwargs):
        from app.application.services.analytics_service import URLClickLimitReachedError

        raise URLClickLimitReachedError("one-time link already used")


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
    assert resolve_res.headers["cache-control"] == "private, no-store"

    redirect_res = client.get("/api/v1/urls/r/acme", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://example.com"
    assert redirect_res.headers["cache-control"] == "private, no-store"

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


def test_used_link_responses_are_not_cacheable(monkeypatch) -> None:
    monkeypatch.setattr(urls_router_module, "AnalyticsService", UsedOneTimeAnalyticsService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    client = TestClient(app)
    try:
        resolve_res = client.get("/api/v1/urls/resolve/used-link")
        assert resolve_res.status_code == 410
        assert resolve_res.headers["cache-control"] == "private, no-store"

        redirect_res = client.get("/api/v1/urls/r/used-link", follow_redirects=False)
        assert redirect_res.status_code == 410
        assert redirect_res.headers["cache-control"] == "private, no-store"
    finally:
        app.dependency_overrides.clear()


def test_scoped_api_key_cannot_read_another_organization(monkeypatch) -> None:
    monkeypatch.setattr(urls_router_module, "URLService", FakeURLService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    user = type("User", (), {"id": uuid4(), "is_active": True})()
    scoped_org = uuid4()
    app.dependency_overrides[urls_router_module.get_api_key_principal] = (
        lambda: ApiKeyPrincipal(user=user, organization_id=scoped_org)
    )
    client = TestClient(app)
    try:
        response = client.get(f"/api/v1/urls/api/organizations/{uuid4()}")
        assert response.status_code == 403
        assert (
            response.json()["error"]["message"]
            == "API key is not scoped to this organization"
        )
    finally:
        app.dependency_overrides.clear()


def test_scoped_api_key_can_read_its_organization(monkeypatch) -> None:
    monkeypatch.setattr(urls_router_module, "URLService", FakeURLService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    user = type("User", (), {"id": uuid4(), "is_active": True})()
    scoped_org = uuid4()
    app.dependency_overrides[urls_router_module.get_api_key_principal] = (
        lambda: ApiKeyPrincipal(user=user, organization_id=scoped_org)
    )
    client = TestClient(app)
    try:
        response = client.get(f"/api/v1/urls/api/organizations/{scoped_org}")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_csv_upload_converts_validated_urls_to_strings(monkeypatch) -> None:
    captured: dict = {}

    class UploadService(FakeURLService):
        async def bulk_create(self, organization_id, requester_user_id, rows):
            captured["rows"] = rows
            return [], []

    monkeypatch.setattr(urls_router_module, "URLService", UploadService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/urls/bulk/upload?organization_id={uuid4()}",
            files={
                "file": (
                    "links.csv",
                    "original_url,title\nhttps://example.com/products,Products\n",
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        assert captured["rows"][0]["original_url"] == "https://example.com/products"
        assert isinstance(captured["rows"][0]["original_url"], str)
    finally:
        app.dependency_overrides.clear()


def test_csv_upload_rejects_oversized_file(monkeypatch) -> None:
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/urls/bulk/upload?organization_id={uuid4()}",
            files={
                "file": (
                    "oversized.csv",
                    b"x" * (5 * 1024 * 1024 + 1),
                    "text/csv",
                )
            },
        )
        assert response.status_code == 413
    finally:
        app.dependency_overrides.clear()


def test_csv_upload_reports_extra_fields_instead_of_importing_row(monkeypatch) -> None:
    captured: dict = {}

    class UploadService(FakeURLService):
        async def bulk_create(self, organization_id, requester_user_id, rows):
            captured["rows"] = rows
            return [], []

    monkeypatch.setattr(urls_router_module, "URLService", UploadService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/urls/bulk/upload?organization_id={uuid4()}",
            files={
                "file": (
                    "malformed.csv",
                    "original_url,title\nhttps://example.com,Product,unexpected\n",
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        assert captured["rows"] == []
        assert response.json()["failed"] == [
            {
                "index": 0,
                "reason": "row contains more fields than the CSV header",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_csv_upload_maps_service_failures_to_original_row_indices(monkeypatch) -> None:
    class UploadService(FakeURLService):
        async def bulk_create(self, organization_id, requester_user_id, rows):
            return [], [type("Failure", (), {"index": 0, "reason": "alias already taken"})()]

    monkeypatch.setattr(urls_router_module, "URLService", UploadService)
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/urls/bulk/upload?organization_id={uuid4()}",
            files={
                "file": (
                    "row-indices.csv",
                    "original_url\nnot-a-url\nhttps://example.com\n",
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        failures = response.json()["failed"]
        assert [failure["index"] for failure in failures] == [0, 1]
        assert "valid URL" in failures[0]["reason"]
        assert failures[1]["reason"] == "alias already taken"
    finally:
        app.dependency_overrides.clear()


def test_csv_upload_rejects_duplicate_headers(monkeypatch) -> None:
    app.dependency_overrides[urls_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[urls_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/urls/bulk/upload?organization_id={uuid4()}",
            files={
                "file": (
                    "duplicate-headers.csv",
                    "original_url,original_url\nhttps://example.com,https://other.example\n",
                    "text/csv",
                )
            },
        )
        assert response.status_code == 400
        assert "unique" in response.json()["error"]["message"]
    finally:
        app.dependency_overrides.clear()
