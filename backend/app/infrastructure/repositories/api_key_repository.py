from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.api_key import ApiKey


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, user_id: UUID, name: str, key_prefix: str, key_hash: str
    ) -> ApiKey:
        item = ApiKey(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_user(self, user_id: UUID) -> list[ApiKey]:
        result = await self._session.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars())

    async def get_for_user(self, key_id: UUID, user_id: UUID) -> ApiKey | None:
        result = await self._session.execute(
            select(ApiKey)
            .where(ApiKey.id == key_id, ApiKey.user_id == user_id)
            .with_for_update()
        )
        return result.scalars().first()

    async def get_active_by_hash(self, key_hash: str) -> ApiKey | None:
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        )
        item = result.scalars().first()
        if item is not None:
            now = datetime.now(UTC).replace(tzinfo=None)
            await self._session.execute(
                update(ApiKey)
                .where(ApiKey.id == item.id, ApiKey.is_active.is_(True))
                .values(last_used_at=now, usage_count=ApiKey.usage_count + 1)
            )
            item.last_used_at = now
            if not isinstance(self._session, AsyncSession):
                item.usage_count += 1
            await self._session.flush()
        return item

    async def revoke(self, item: ApiKey) -> None:
        item.is_active = False
        item.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()
