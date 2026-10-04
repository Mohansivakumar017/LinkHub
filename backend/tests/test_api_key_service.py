from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.api_key_service import ApiKeyNotFoundError, ApiKeyService


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeRepository:
    def __init__(self) -> None:
        self.items = []

    async def create(self, user_id, name, key_prefix, key_hash, organization_id=None):
        item = SimpleNamespace(
            id=uuid4(),
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
            organization_id=organization_id,
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
    assert repository.items[0].is_active is False


@pytest.mark.asyncio
async def test_revoked_api_key_cannot_be_rotated() -> None:
    session = FakeSession()
    repository = FakeRepository()
    service = ApiKeyService(session, repository)
    user_id = uuid4()
    original = await service.create(user_id, "automation")
    await service.revoke(user_id, original.id)

    with pytest.raises(ApiKeyNotFoundError, match="active API key not found"):
        await service.rotate(user_id, original.id)


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


@pytest.mark.asyncio
async def test_revoke_all_for_user_disables_only_active_keys() -> None:
    from datetime import datetime

    from app.infrastructure.repositories.api_key_repository import ApiKeyRepository

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement

        async def flush(self):
            return None

    user_id = uuid4()
    session = Session()

    await ApiKeyRepository(session).revoke_all_for_user(user_id)

    assert session.statement is not None
    compiled = session.statement.compile()
    assert "api_keys.user_id" in str(compiled)
    assert "api_keys.is_active" in str(compiled)
    assert user_id in compiled.params.values()
    assert False in compiled.params.values()
    assert any(
        isinstance(value, datetime) and value.tzinfo is None
        for value in compiled.params.values()
    )


@pytest.mark.asyncio
async def test_revoke_for_member_removal_is_limited_to_active_org_keys() -> None:
    from app.infrastructure.repositories.api_key_repository import ApiKeyRepository

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement

        async def flush(self):
            return None

    user_id = uuid4()
    organization_id = uuid4()
    session = Session()

    await ApiKeyRepository(session).revoke_for_user_in_organization(
        user_id, organization_id
    )

    compiled = session.statement.compile()
    assert "api_keys.user_id" in str(compiled)
    assert "api_keys.organization_id" in str(compiled)
    assert "api_keys.is_active" in str(compiled)
    assert user_id in compiled.params.values()
    assert organization_id in compiled.params.values()
    assert False in compiled.params.values()


@pytest.mark.asyncio
async def test_scoped_key_creation_locks_the_membership_row() -> None:
    from sqlalchemy.dialects import postgresql

    class Result:
        def scalar_one_or_none(self):
            return uuid4()

    class Session(FakeSession):
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    service = ApiKeyService(session, FakeRepository())
    await service.create(uuid4(), "scoped", uuid4())

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert "FOR UPDATE" in str(compiled)
    assert "organization_members.organization_id" in str(compiled)
    assert "organization_members.user_id" in str(compiled)
