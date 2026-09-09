from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.jwt import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    decode_token_with_type,
)
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.infrastructure.email.sender import (
    BackgroundEmailSender,
    EmailMessage,
    EmailSender,
)
from app.infrastructure.repositories.audit_repository import AuditRepository
from app.infrastructure.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository


class AuthError(Exception):
    pass


class UserAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class EmailNotVerifiedError(AuthError):
    pass


class InvalidRefreshTokenError(AuthError):
    pass


class InvalidVerificationTokenError(AuthError):
    pass


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository | None = None,
        refresh_token_repo: RefreshTokenRepository | None = None,
        email_sender: EmailSender | None = None,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._session = session
        self._users = user_repo or UserRepository(session)
        self._refresh_tokens = refresh_token_repo or RefreshTokenRepository(session)
        self._email_sender = email_sender or BackgroundEmailSender()
        self._audit = audit_repo or (
            AuditRepository(session) if isinstance(session, AsyncSession) else None
        )

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> UUID:
        email = email.strip().lower()
        existing_user = await self._users.get_by_email(email)
        if existing_user is not None:
            raise UserAlreadyExistsError("email already registered")

        user = await self._users.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        await self._record_audit(user.id, "auth.registered", "user", str(user.id))
        await self._session.commit()
        return user.id

    async def authenticate(self, email: str, password: str) -> AuthTokens:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("invalid credentials")
        if not getattr(user, "is_email_verified", False):
            raise EmailNotVerifiedError("email verification required")

        access_token = create_access_token(subject=str(user.id))
        refresh_token = generate_refresh_token()
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            days=get_settings().refresh_token_exp_days
        )
        await self._refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
        await self._record_audit(user.id, "auth.logged_in", "user", str(user.id))
        await self._session.commit()
        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def refresh(self, raw_refresh_token: str) -> AuthTokens:
        hashed_token = hash_token(raw_refresh_token)
        token = await self._refresh_tokens.get_by_hash(hashed_token)
        now = datetime.now(UTC).replace(tzinfo=None)
        if token is None or token.revoked or token.expires_at <= now:
            raise InvalidRefreshTokenError("invalid refresh token")
        user = await self._users.get_by_id(token.user_id)
        if (
            user is None
            or not getattr(user, "is_active", True)
            or not getattr(user, "is_email_verified", False)
        ):
            raise InvalidRefreshTokenError("invalid refresh token")

        new_refresh_token = generate_refresh_token()
        new_expires_at = now + timedelta(
            days=get_settings().refresh_token_exp_days
        )
        replacement = await self._refresh_tokens.create(
            user_id=token.user_id,
            token_hash=hash_token(new_refresh_token),
            expires_at=new_expires_at,
        )
        await self._refresh_tokens.mark_replaced(token, replacement.id)
        await self._record_audit(token.user_id, "auth.token_refreshed", "user", str(token.user_id))
        await self._session.commit()

        access_token = create_access_token(subject=str(token.user_id))
        return AuthTokens(access_token=access_token, refresh_token=new_refresh_token)

    async def logout(self, raw_refresh_token: str) -> None:
        hashed_token = hash_token(raw_refresh_token)
        token = await self._refresh_tokens.get_by_hash(hashed_token)
        if token is None:
            return
        await self._refresh_tokens.revoke(token)
        await self._record_audit(token.user_id, "auth.logged_out", "user", str(token.user_id))
        await self._session.commit()

    async def send_verification_email(self, email: str) -> None:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        if user is None or user.is_email_verified:
            return

        token = create_email_verification_token(subject=str(user.id))
        await self._email_sender.send(
            EmailMessage(
                to_email=user.email,
                subject="Verify your LinkHub email",
                body=f"Use this token to verify your email: {token}",
            )
        )

    async def verify_email(self, verification_token: str) -> None:
        try:
            payload = decode_token_with_type(verification_token, "verify_email")
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError, PyJWTError) as exc:
            raise InvalidVerificationTokenError("invalid verification token") from exc

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise InvalidVerificationTokenError("invalid verification token")

        await self._users.mark_email_verified(user)
        await self._record_audit(user.id, "auth.email_verified", "user", str(user.id))
        await self._session.commit()

    async def request_password_reset(self, email: str) -> None:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        if user is None:
            return

        token = create_password_reset_token(subject=str(user.id))
        await self._email_sender.send(
            EmailMessage(
                to_email=user.email,
                subject="LinkHub password reset",
                body=f"Use this token to reset your password: {token}",
            )
        )

    async def reset_password(self, reset_token: str, new_password: str) -> None:
        try:
            payload = decode_token_with_type(reset_token, "reset_password")
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError, PyJWTError) as exc:
            raise InvalidVerificationTokenError("invalid reset token") from exc

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise InvalidVerificationTokenError("invalid reset token")

        await self._users.update_password(user, hash_password(new_password))
        await self._refresh_tokens.revoke_all_for_user(user_id=user.id)
        await self._record_audit(user.id, "auth.password_reset", "user", str(user.id))
        await self._session.commit()

    async def _record_audit(
        self,
        actor_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
    ) -> None:
        if self._audit is not None:
            await self._audit.record(
                actor_user_id, action, resource_type, resource_id
            )
