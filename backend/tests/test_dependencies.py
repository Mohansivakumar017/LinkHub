from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import dependencies
from app.core.jwt import create_access_token


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("validator", "version"),
    [
        (dependencies.get_current_user, 2),
        (dependencies.get_optional_current_user, 2),
    ],
)
async def test_access_token_with_old_auth_version_is_rejected(
    monkeypatch, validator, version
) -> None:
    user_id = uuid4()

    class FakeUserRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_by_id(self, _user_id):
            return SimpleNamespace(id=user_id, is_active=True, auth_version=3)

    monkeypatch.setattr(dependencies, "UserRepository", FakeUserRepository)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(
            str(user_id),
            extra_claims={"auth_version": version},
        ),
    )

    with pytest.raises(HTTPException) as error:
        await validator(credentials=credentials, session=object())

    assert error.value.status_code == 401
    assert error.value.detail == "access token has been revoked"


@pytest.mark.asyncio
async def test_access_token_without_auth_version_remains_compatible(monkeypatch) -> None:
    user_id = uuid4()

    class FakeUserRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_by_id(self, _user_id):
            return SimpleNamespace(id=user_id, is_active=True, auth_version=0)

    monkeypatch.setattr(dependencies, "UserRepository", FakeUserRepository)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(str(user_id)),
    )

    user = await dependencies.get_current_user(
        credentials=credentials,
        session=object(),
    )

    assert user.id == user_id
