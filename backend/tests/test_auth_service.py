from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.auth_service import (
    AuthService,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidVerificationTokenError,
    UserAlreadyExistsError,
)
from app.core.jwt import create_email_verification_token, create_password_reset_token
from app.core.security import hash_password, hash_token


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class FakeUserRepo:
    def __init__(self) -> None:
        self.users_by_email: dict[str, SimpleNamespace] = {}

    async def get_by_email(self, email: str):
        return self.users_by_email.get(email)

    async def get_by_id(self, user_id):
        for user in self.users_by_email.values():
            if user.id == user_id:
                return user
        return None

    async def create(self, email: str, hashed_password: str, full_name: str | None = None):
        user = SimpleNamespace(
            id=uuid4(),
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_email_verified=False,
        )
        self.users_by_email[email] = user
        return user

    async def mark_email_verified(self, user):
        user.is_email_verified = True

    async def update_password(self, user, hashed_password: str):
        user.hashed_password = hashed_password


class FakeRefreshRepo:
    def __init__(self) -> None:
        self.tokens_by_hash: dict[str, SimpleNamespace] = {}

    async def create(self, user_id, token_hash: str, expires_at: datetime):
        token = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
            replaced_by=None,
        )
        self.tokens_by_hash[token_hash] = token
        return token

    async def get_by_hash(self, token_hash: str):
        return self.tokens_by_hash.get(token_hash)

    async def mark_replaced(self, refresh_token, replacement_id):
        refresh_token.revoked = True
        refresh_token.replaced_by = replacement_id

    async def revoke(self, refresh_token):
        refresh_token.revoked = True

    async def revoke_all_for_user(self, user_id):
        for token in self.tokens_by_hash.values():
            if token.user_id == user_id:
                token.revoked = True


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent_messages: list[SimpleNamespace] = []

    async def send(self, message) -> None:
        self.sent_messages.append(SimpleNamespace(**message.__dict__))


@pytest.mark.asyncio
async def test_register_and_duplicate_registration() -> None:
    session = FakeSession()
    user_repo = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    email_sender = FakeEmailSender()
    service = AuthService(
        session=session,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
        email_sender=email_sender,
    )

    user_id = await service.register(" User@Example.com ", "StrongPass123!")
    assert user_id is not None

    with pytest.raises(UserAlreadyExistsError):
        await service.register("user@example.com", "StrongPass123!")


@pytest.mark.asyncio
async def test_authenticate_and_invalid_credentials() -> None:
    session = FakeSession()
    user_repo = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    email_sender = FakeEmailSender()
    service = AuthService(
        session=session,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
        email_sender=email_sender,
    )

    unverified = await user_repo.create(
        email="user@example.com",
        hashed_password=hash_password("StrongPass123!"),
    )

    with pytest.raises(EmailNotVerifiedError):
        await service.authenticate("user@example.com", "StrongPass123!")

    await user_repo.mark_email_verified(unverified)
    tokens = await service.authenticate("user@example.com", "StrongPass123!")
    assert tokens.access_token
    assert tokens.refresh_token

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("user@example.com", "wrong-pass")


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout() -> None:
    session = FakeSession()
    user_repo = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    email_sender = FakeEmailSender()
    service = AuthService(
        session=session,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
        email_sender=email_sender,
    )

    user = await user_repo.create(
        email="user@example.com",
        hashed_password=hash_password("StrongPass123!"),
    )
    await user_repo.mark_email_verified(user)
    old_raw_refresh = "initial-refresh-token"
    old_hash = hash_token(old_raw_refresh)
    await refresh_repo.create(
        user_id=user.id,
        token_hash=old_hash,
        expires_at=(datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)),
    )

    rotated = await service.refresh(old_raw_refresh)
    assert rotated.access_token
    assert rotated.refresh_token != old_raw_refresh

    old_token = await refresh_repo.get_by_hash(old_hash)
    assert old_token is not None
    assert old_token.revoked is True

    with pytest.raises(InvalidRefreshTokenError):
        await service.refresh(old_raw_refresh)

    await service.logout(rotated.refresh_token)
    new_token = await refresh_repo.get_by_hash(hash_token(rotated.refresh_token))
    assert new_token is not None
    assert new_token.revoked is True


@pytest.mark.asyncio
async def test_email_verification_flow() -> None:
    session = FakeSession()
    user_repo = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    email_sender = FakeEmailSender()
    service = AuthService(
        session=session,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
        email_sender=email_sender,
    )

    user = await user_repo.create(
        email="user@example.com",
        hashed_password=hash_password("StrongPass123!"),
    )

    await service.send_verification_email("user@example.com")
    assert len(email_sender.sent_messages) == 1

    token = create_email_verification_token(subject=str(user.id))
    await service.verify_email(token)
    assert user.is_email_verified is True

    with pytest.raises(InvalidVerificationTokenError):
        await service.verify_email("not-a-valid-token")


@pytest.mark.asyncio
async def test_password_reset_flow() -> None:
    session = FakeSession()
    user_repo = FakeUserRepo()
    refresh_repo = FakeRefreshRepo()
    email_sender = FakeEmailSender()
    service = AuthService(
        session=session,
        user_repo=user_repo,
        refresh_token_repo=refresh_repo,
        email_sender=email_sender,
    )

    user = await user_repo.create(
        email="user@example.com",
        hashed_password=hash_password("StrongPass123!"),
    )
    token = create_password_reset_token(subject=str(user.id))

    old_password_hash = user.hashed_password
    await service.reset_password(token, "NewStrongPass123!")
    assert user.hashed_password != old_password_hash

    with pytest.raises(InvalidVerificationTokenError):
        await service.reset_password("bad-token", "AnyStrongPass123!")
