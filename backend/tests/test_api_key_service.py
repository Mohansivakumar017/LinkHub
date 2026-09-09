from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.api_key_service import ApiKeyService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeRepository:
    def __init__(self) -> None:
        self.items = []

    async def create(self, user_id, name, key_prefix, key_hash):
        item = SimpleNamespace(
            id=uuid4(),
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        self.items.append(item)
        return item

    async def list_for_user(self, user_id):
        return self.items

    async def get_for_user(self, key_id, user_id):
        return next((item for item in self.items if item.id == key_id), None)

    async def revoke(self, item):
        item.is_active = False


@pytest.mark.asyncio
async def test_api_key_is_returned_only_on_creation() -> None:
    session = FakeSession()
    repository = FakeRepository()
    service = ApiKeyService(session, repository)

    created = await service.create(uuid4(), "automation")

    assert created.key.startswith("lhk_")
    assert created.key_prefix == created.key[:12]
    assert (await service.list(uuid4())) == repository.items


@pytest.mark.asyncio
async def test_api_key_rotation_revokes_old_key_and_returns_replacement() -> None:
    session = FakeSession()
    repository = FakeRepository()
    service = ApiKeyService(session, repository)
    user_id = uuid4()
    original = await service.create(user_id, "automation")

    rotated = await service.rotate(user_id, original.id)

    assert rotated.key.startswith("lhk_")
    assert rotated.key != original.key


@pytest.mark.asyncio
async def test_api_key_usage_updates_last_used_and_count() -> None:
    from datetime import datetime

    from app.infrastructure.repositories.api_key_repository import ApiKeyRepository

    class Result:
        def scalars(self):
            return self

        def first(self):
            return item

    class Session:
        async def execute(self, _query):
            return Result()

        async def flush(self):
            return None

    item = SimpleNamespace(id=uuid4(), is_active=True, usage_count=0, last_used_at=None)
    found = await ApiKeyRepository(Session()).get_active_by_hash("hash")

    assert found is item
    assert item.usage_count == 1
    assert isinstance(item.last_used_at, datetime)
    assert item.last_used_at.tzinfo is None
