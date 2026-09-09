from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.url import URL


class URLRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **kwargs) -> URL:
        item = URL(**kwargs)
        self._session.add(item)
        await self._session.flush()
        return item

    async def get_by_id(self, url_id: UUID) -> URL | None:
        result = await self._session.execute(select(URL).where(URL.id == url_id))
        return result.scalars().first()

    async def get_by_id_for_update(self, url_id: UUID) -> URL | None:
        result = await self._session.execute(
            select(URL).where(URL.id == url_id).with_for_update()
        )
        return result.scalars().first()

    async def get_by_short_code(self, short_code: str) -> URL | None:
        result = await self._session.execute(select(URL).where(URL.short_code == short_code))
        return result.scalars().first()

    async def get_by_short_code_for_update(self, short_code: str) -> URL | None:
        result = await self._session.execute(
            select(URL).where(URL.short_code == short_code).with_for_update()
        )
        return result.scalars().first()

    async def list_for_org(
        self,
        organization_id: UUID,
        include_deleted: bool = False,
        search: str | None = None,
        archived: bool | None = None,
        offset: int = 0,
        limit: int = 50,
        sort: str = "created_at",
        descending: bool = True,
    ) -> list[URL]:
        query = select(URL).where(URL.organization_id == organization_id)
        if not include_deleted:
            query = query.where(URL.is_deleted.is_(False))
        if search:
            pattern = f"%{search}%"
            query = query.where(
                URL.short_code.ilike(pattern) | URL.title.ilike(pattern)
            )
        if archived is not None:
            query = query.where(URL.is_archived.is_(archived))
        sort_columns = {
            "created_at": URL.created_at,
            "updated_at": URL.updated_at,
            "short_code": URL.short_code,
        }
        sort_column = sort_columns[sort]
        query = query.order_by(
            sort_column.desc() if descending else sort_column.asc()
        )
        result = await self._session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def update(self, item: URL, **changes) -> URL:
        for key, value in changes.items():
            setattr(item, key, value)
        await self._session.flush()
        return item

    async def soft_delete(self, item: URL) -> None:
        item.is_deleted = True
        item.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await self._session.flush()

    async def bulk_soft_delete(self, organization_id: UUID, ids: list[UUID]) -> int:
        count = 0
        for url_id in ids:
            item = await self.get_by_id(url_id)
            if item and item.organization_id == organization_id and not item.is_deleted:
                await self.soft_delete(item)
                count += 1
        return count

    async def is_alias_taken(self, alias: str) -> bool:
        result = await self._session.execute(
            select(URL.id).where(and_(URL.short_code == alias, URL.is_deleted.is_(False)))
        )
        return result.scalar_one_or_none() is not None

    async def archive_expired(self) -> int:
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await self._session.execute(
            update(URL)
            .where(URL.expires_at.is_not(None), URL.expires_at <= now, URL.is_deleted.is_(False))
            .values(is_archived=True, archived_at=now)
        )
        await self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_expired_short_codes(self) -> list[str]:
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await self._session.execute(
            select(URL.short_code).where(
                URL.expires_at.is_not(None),
                URL.expires_at <= now,
                URL.is_deleted.is_(False),
                URL.is_archived.is_(False),
            )
        )
        return list(result.scalars().all())
