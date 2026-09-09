from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.presentation.api.v1.routers import analytics as analytics_router_module


class FakeAnalyticsService:
    def __init__(self, session) -> None:
        self._session = session

    async def get_overview(self, organization_id, requester_user_id, days=30):
        return {"total_clicks": 10, "unique_clicks": 8, "range_days": days}

    async def get_time_series(self, organization_id, requester_user_id, days=30, granularity="daily"):
        return [{"bucket": "2026-08-04", "count": 5}]

    async def get_top_links(self, organization_id, requester_user_id, days=30, limit=10):
        return [{"url_id": str(uuid4()), "short_code": "acme", "original_url": "https://example.com", "clicks": 5}]


async def fake_db_session():
    yield None


async def fake_current_user():
    return type("User", (), {"id": uuid4(), "is_active": True})()


def test_analytics_router_contract(monkeypatch) -> None:
    monkeypatch.setattr(analytics_router_module, "AnalyticsService", FakeAnalyticsService)
    app.dependency_overrides[analytics_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[analytics_router_module.get_current_user] = fake_current_user
    client = TestClient(app)

    org_id = uuid4()
    overview_res = client.get(f"/api/v1/analytics/organizations/{org_id}/overview?days=30")
    assert overview_res.status_code == 200
    assert overview_res.json()["total_clicks"] == 10

    series_res = client.get(
        f"/api/v1/analytics/organizations/{org_id}/timeseries?days=30&granularity=daily"
    )
    assert series_res.status_code == 200
    assert isinstance(series_res.json(), list)

    top_res = client.get(f"/api/v1/analytics/organizations/{org_id}/top-links?days=30&limit=5")
    assert top_res.status_code == 200
    assert isinstance(top_res.json(), list)

    app.dependency_overrides.clear()
