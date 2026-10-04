from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalars().first()

    async def mark_consumed(
        self, token: PasswordResetToken, consumed_at: datetime
    ) -> None:
        token.consumed_at = consumed_at
        await self._session.flush()

    async def delete_expired(self) -> int:
        result = await self._session.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.expires_at
                <= datetime.now(UTC).replace(tzinfo=None)
            )
        )
        await self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)
