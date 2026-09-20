from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.infrastructure.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        query = (
            select(RefreshToken).options(lazyload(RefreshToken.user))
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalars().first()

    async def revoke(self, refresh_token: RefreshToken) -> None:
        refresh_token.revoked = True
        refresh_token.last_used_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        query = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True, last_used_at=datetime.now(UTC).replace(tzinfo=None))
        )
        await self._session.execute(query)
        await self._session.flush()

    async def mark_replaced(self, refresh_token: RefreshToken, replacement_id: UUID) -> None:
        refresh_token.replaced_by = replacement_id
        refresh_token.revoked = True
        refresh_token.last_used_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

    async def delete_expired(self) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await self._session.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now))
        await self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)
