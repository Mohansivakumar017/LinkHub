from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infrastructure.repositories import admin_repository as admin_module


@pytest.mark.asyncio
async def test_deactivation_revokes_refresh_tokens_and_api_keys(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class UserRepository:
        def __init__(self, _session) -> None:
            pass

        async def set_active(self, _user, is_active: bool) -> None:
            calls.append(("active", is_active))

    class ApiKeyRepository:
        def __init__(self, _session) -> None:
            pass

        async def revoke_all_for_user(self, user_id) -> None:
            calls.append(("api_keys", user_id))

    class RefreshTokenRepository:
        def __init__(self, _session) -> None:
            pass

        async def revoke_all_for_user(self, user_id) -> None:
            calls.append(("refresh_tokens", user_id))

    monkeypatch.setattr(admin_module, "UserRepository", UserRepository)
    monkeypatch.setattr(admin_module, "ApiKeyRepository", ApiKeyRepository)
    monkeypatch.setattr(
        admin_module, "RefreshTokenRepository", RefreshTokenRepository
    )
    user_id = uuid4()
    repository = admin_module.AdminRepository(object())

    await repository.set_user_active(SimpleNamespace(id=user_id), False)

    assert calls == [
        ("active", False),
        ("api_keys", user_id),
        ("refresh_tokens", user_id),
    ]
