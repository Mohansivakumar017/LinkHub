from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.url_service import URLNotFoundError, URLService


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeMemberRepo:
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow

    async def get_membership(self, organization_id, user_id):
        if not self.allow:
            return None
        return SimpleNamespace(role="owner")


class FakeURLRepo:
    def __init__(self) -> None:
        self.items: dict = {}

    async def create(self, **kwargs):
        item = SimpleNamespace(id=uuid4(), is_deleted=False, is_archived=False, archived_at=None, **kwargs)
        self.items[item.id] = item
        return item

    async def get_by_id(self, url_id):
        return self.items.get(url_id)

    async def list_for_org(self, organization_id, include_deleted=False):
        return [i for i in self.items.values() if i.organization_id == organization_id and (include_deleted or not i.is_deleted)]

    async def update(self, item, **changes):
        for k, v in changes.items():
            setattr(item, k, v)
        return item

    async def soft_delete(self, item):
        item.is_deleted = True

    async def bulk_soft_delete(self, organization_id, ids):
        count = 0
        for i in ids:
            item = self.items.get(i)
            if item and item.organization_id == organization_id and not item.is_deleted:
                item.is_deleted = True
                count += 1
        return count

    async def is_alias_taken(self, alias: str):
        return any(i.short_code == alias and not i.is_deleted for i in self.items.values())


class FakeCache:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    async def get(self, short_code: str):
        return self.items.get(short_code)

    async def set(self, short_code: str, payload: dict):
        self.items[short_code] = payload

    async def delete(self, short_code: str):
        self.items.pop(short_code, None)


@pytest.mark.asyncio
async def test_url_lifecycle_and_bulk() -> None:
    session = FakeSession()
    repo = FakeURLRepo()
    cache = FakeCache()
    service = URLService(session=session, url_repo=repo, membership_repo=FakeMemberRepo(True), cache=cache)
    org_id = uuid4()
    user_id = uuid4()

    created = await service.create_url(
        organization_id=org_id,
        owner_user_id=user_id,
        original_url="https://example.com",
        custom_alias="acme-home",
        title="Acme",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
    )
    assert created.short_code == "acme-home"

    updated = await service.update_url(org_id, user_id, created.id, title="New Title")
    assert updated.title == "New Title"

    renamed = await service.update_url(
        org_id, user_id, created.id, custom_alias="new-home"
    )
    assert renamed.short_code == "new-home"
    assert renamed.custom_alias == "new-home"

    duplicate = await service.duplicate_url(org_id, user_id, created.id)
    assert duplicate.id != created.id

    await service.archive_url(org_id, user_id, created.id)
    assert created.is_archived is True

    await service.restore_url(org_id, user_id, created.id)
    assert created.is_archived is False

    deleted_count = await service.bulk_delete(org_id, user_id, [created.id, duplicate.id])
    assert deleted_count == 2
    assert "acme-home" not in cache.items


@pytest.mark.asyncio
async def test_not_found_raises() -> None:
    session = FakeSession()
    repo = FakeURLRepo()
    service = URLService(session=session, url_repo=repo, membership_repo=FakeMemberRepo(True), cache=FakeCache())
    with pytest.raises(URLNotFoundError):
        await service.delete_url(uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_resolve_uses_cache() -> None:
    session = FakeSession()
    repo = FakeURLRepo()
    cache = FakeCache()
    service = URLService(session=session, url_repo=repo, membership_repo=FakeMemberRepo(True), cache=cache)
    org_id = uuid4()
    user_id = uuid4()

    created = await service.create_url(
        organization_id=org_id,
        owner_user_id=user_id,
        original_url="https://example.com/x",
        custom_alias="route-x",
    )
    first = await service.resolve_short_code(created.short_code)
    assert first["original_url"] == "https://example.com/x"

    repo.items.pop(created.id)
    second = await service.resolve_short_code(created.short_code)
    assert second["short_code"] == created.short_code
