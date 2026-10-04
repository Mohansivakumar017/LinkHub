from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.infrastructure.repositories.user_repository import UserRepository


class FakeSession:
    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_password_update_increments_auth_version() -> None:
    user = SimpleNamespace(hashed_password="old-hash", auth_version=4)

    await UserRepository(FakeSession()).update_password(user, "new-hash")

    assert user.hashed_password == "new-hash"
    assert user.auth_version == 5


@pytest.mark.asyncio
async def test_deactivation_increments_auth_version_but_reactivation_does_not() -> None:
    user = SimpleNamespace(is_active=True, auth_version=2)
    repository = UserRepository(FakeSession())

    await repository.set_active(user, False)
    assert user.is_active is False
    assert user.auth_version == 3

    await repository.set_active(user, True)
    assert user.is_active is True
    assert user.auth_version == 3


@pytest.mark.asyncio
async def test_get_by_id_for_update_locks_user_row() -> None:
    class Result:
        def scalars(self):
            return self

        def first(self):
            return None

    class Session(FakeSession):
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    await UserRepository(session).get_by_id_for_update(uuid4())

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert "FOR UPDATE" in str(compiled)
    assert "users.id" in str(compiled)
