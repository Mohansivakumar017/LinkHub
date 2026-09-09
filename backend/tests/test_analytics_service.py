from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.analytics_service import (
    AnalyticsPermissionDeniedError,
    AnalyticsService,
    ClickContext,
    URLAccessDeniedError,
)
from app.application.services.url_service import URLNotFoundError
from app.core.security import hash_password


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeClickRepo:
    def __init__(self) -> None:
        self.counts: dict = {}
        self.created = 0

    async def create_click(self, **kwargs):
        self.created += 1
        url_id = kwargs["url_id"]
        self.counts[url_id] = self.counts.get(url_id, 0) + 1
        return SimpleNamespace(**kwargs)

    async def count_for_url(self, url_id):
        return self.counts.get(url_id, 0)

    async def get_org_overview(self, organization_id, days=30):
        return {"total_clicks": 5, "unique_clicks": 4, "range_days": days}

    async def get_time_series(self, organization_id, days=30, granularity="daily"):
        return [{"bucket": "2026-08-04", "count": 3}]

    async def get_top_links(self, organization_id, days=30, limit=10):
        return [{"url_id": str(uuid4()), "short_code": "abc123", "original_url": "https://x", "clicks": 3}]


class FakeURLRepo:
    def __init__(self, url_obj) -> None:
        self.url = url_obj
        self.updated = False

    async def get_by_short_code(self, short_code: str):
        return self.url if self.url and self.url.short_code == short_code else None

    async def update(self, item, **changes):
        for k, v in changes.items():
            setattr(item, k, v)
        self.updated = True
        return item


class FakeOrgMemberRepo:
    def __init__(self, allow=True) -> None:
        self.allow = allow

    async def get_membership(self, organization_id, user_id):
        if not self.allow:
            return None
        return SimpleNamespace(id=uuid4(), role="owner")


class FakeCache:
    def __init__(self) -> None:
        self.deleted = []

    async def get(self, short_code):
        return None

    async def set(self, short_code, payload):
        return None

    async def delete(self, short_code):
        self.deleted.append(short_code)


class CachedURLCache(FakeCache):
    def __init__(self, payload) -> None:
        super().__init__()
        self.payload = payload

    async def get(self, short_code):
        return self.payload


@pytest.mark.asyncio
async def test_track_click_and_archive_on_limit() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="acme",
        original_url="https://example.com",
        is_deleted=False,
        is_archived=False,
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        one_time=False,
        click_limit=1,
        is_private=False,
    )
    click_repo = FakeClickRepo()
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=click_repo,
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=FakeCache(),
    )
    result = await service.track_click("acme", ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None))
    assert result["short_code"] == "acme"
    assert click_repo.created == 1

    with pytest.raises(URLNotFoundError):
        await service.track_click("acme", ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None))


@pytest.mark.asyncio
async def test_track_click_uses_cached_public_url() -> None:
    url_id = uuid4()
    organization_id = uuid4()
    cache = CachedURLCache(
        {
            "id": str(url_id),
            "organization_id": str(organization_id),
            "short_code": "cached",
            "original_url": "https://example.com/cached",
            "is_private": False,
            "expires_at": None,
            "one_time": False,
            "click_limit": None,
            "cacheable": True,
        }
    )
    click_repo = FakeClickRepo()
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=click_repo,
        url_repo=FakeURLRepo(None),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=cache,
    )

    result = await service.track_click(
        "cached", ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None)
    )

    assert result["original_url"] == "https://example.com/cached"
    assert click_repo.created == 1


@pytest.mark.asyncio
async def test_non_cacheable_cached_payload_falls_back_to_database() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="protected",
        original_url="https://example.com/protected",
        is_deleted=False,
        is_archived=False,
        expires_at=None,
        one_time=False,
        click_limit=None,
        is_private=False,
        password_hash=hash_password("correct-password"),
    )
    cache = CachedURLCache(
        {
            "id": str(url.id),
            "organization_id": str(url.organization_id),
            "short_code": "protected",
            "original_url": "https://attacker.example",
            "is_private": False,
            "expires_at": None,
            "one_time": False,
            "click_limit": None,
            "cacheable": False,
        }
    )
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=FakeClickRepo(),
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=cache,
    )

    with pytest.raises(URLAccessDeniedError):
        await service.track_click(
            "protected",
            ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None),
        )


@pytest.mark.asyncio
async def test_malformed_cache_payload_is_ignored() -> None:
    from app.infrastructure.cache import url_cache as cache_module

    class Redis:
        async def get(self, key):
            return "{malformed"

    cache = cache_module.RedisURLCache()
    cache._redis = Redis()
    assert await cache.get("broken") is None


@pytest.mark.asyncio
async def test_structurally_invalid_cached_url_falls_back_to_database() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="invalid-cache",
        original_url="https://example.com/database",
        is_deleted=False,
        is_archived=False,
        expires_at=None,
        one_time=False,
        click_limit=None,
        is_private=False,
        password_hash=None,
    )
    cache = CachedURLCache({"cacheable": True, "id": "not-a-uuid"})
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=FakeClickRepo(),
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=cache,
    )

    result = await service.track_click(
        "invalid-cache",
        ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None),
    )
    assert result["original_url"] == "https://example.com/database"


@pytest.mark.asyncio
async def test_analytics_membership_guard() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="acme",
        original_url="https://example.com",
        is_deleted=False,
        is_archived=False,
        expires_at=None,
        one_time=False,
        click_limit=None,
        is_private=False,
    )
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=FakeClickRepo(),
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(False),
        cache=FakeCache(),
    )
    with pytest.raises(AnalyticsPermissionDeniedError):
        await service.get_overview(url.organization_id, uuid4())


@pytest.mark.asyncio
async def test_password_protected_link_requires_valid_password() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="secret",
        original_url="https://example.com",
        is_deleted=False,
        is_archived=False,
        expires_at=None,
        one_time=False,
        click_limit=None,
        is_private=False,
        password_hash=hash_password("correct-password"),
    )
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=FakeClickRepo(),
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=FakeCache(),
    )
    context = ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None)

    with pytest.raises(URLAccessDeniedError):
        await service.track_click("secret", context)
    with pytest.raises(URLAccessDeniedError):
        await service.track_click("secret", context, password="wrong-password")

    result = await service.track_click("secret", context, password="correct-password")
    assert result["original_url"] == "https://example.com"


@pytest.mark.asyncio
async def test_private_link_requires_an_organization_member() -> None:
    url = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        short_code="private",
        original_url="https://example.com/private",
        is_deleted=False,
        is_archived=False,
        expires_at=None,
        one_time=False,
        click_limit=None,
        is_private=True,
        password_hash=None,
    )
    member_id = uuid4()
    service = AnalyticsService(
        session=FakeSession(),
        click_repo=FakeClickRepo(),
        url_repo=FakeURLRepo(url),
        org_member_repo=FakeOrgMemberRepo(True),
        cache=FakeCache(),
    )
    context = ClickContext(ip_address="1.1.1.1", user_agent="ua", referrer=None)

    with pytest.raises(URLAccessDeniedError):
        await service.track_click("private", context)
    result = await service.track_click(
        "private", context, requester_user_id=member_id
    )
    assert result["original_url"] == "https://example.com/private"


def test_user_agent_dimensions_are_parsed() -> None:
    browser, os_name, device = AnalyticsService._parse_user_agent(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1"
    )
    assert (browser, os_name, device) == ("Safari", "iOS", "Mobile")
