from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.click import Click
from app.infrastructure.db.models.url import URL


class ClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_click(
        self,
        url_id: UUID,
        organization_id: UUID,
        visitor_key: str,
        ip_address: str | None,
        user_agent: str | None,
        referrer: str | None,
        browser: str | None = None,
        os: str | None = None,
        device: str | None = None,
        country: str | None = None,
        city: str | None = None,
    ) -> Click:
        click = Click(
            url_id=url_id,
            organization_id=organization_id,
            visitor_key=visitor_key,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer,
            browser=browser,
            os=os,
            device=device,
            country=country,
            city=city,
        )
        self._session.add(click)
        await self._session.flush()
        return click

    async def count_for_url(self, url_id: UUID) -> int:
        result = await self._session.execute(select(func.count(Click.id)).where(Click.url_id == url_id))
        return int(result.scalar() or 0)

    async def get_org_overview(self, organization_id: UUID, days: int = 30) -> dict:
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        total = await self._session.execute(
            select(func.count(Click.id)).where(
                Click.organization_id == organization_id, Click.created_at >= since
            )
        )
        unique = await self._session.execute(
            select(func.count(func.distinct(Click.visitor_key))).where(
                Click.organization_id == organization_id, Click.created_at >= since
            )
        )
        return {
            "total_clicks": int(total.scalar() or 0),
            "unique_clicks": int(unique.scalar() or 0),
            "range_days": days,
        }

    async def get_time_series(self, organization_id: UUID, days: int = 30, granularity: str = "daily") -> list[dict]:
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        fmt = "%Y-%m-%d" if granularity == "daily" else "%Y-%W"
        bucket = func.to_char(Click.created_at, fmt)
        query = (
            select(bucket.label("bucket"), func.count(Click.id).label("count"))
            .where(Click.organization_id == organization_id, Click.created_at >= since)
            .group_by(bucket)
            .order_by(bucket)
        )
        result = await self._session.execute(query)
        return [
            {"bucket": row.bucket, "count": int(row._mapping["count"])}
            for row in result.all()
        ]

    async def get_top_links(self, organization_id: UUID, days: int = 30, limit: int = 10) -> list[dict]:
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        query = (
            select(URL.id, URL.short_code, URL.original_url, func.count(Click.id).label("count"))
            .join(Click, Click.url_id == URL.id)
            .where(Click.organization_id == organization_id, Click.created_at >= since)
            .group_by(URL.id, URL.short_code, URL.original_url)
            .order_by(func.count(Click.id).desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [
            {
                "url_id": str(row.id),
                "short_code": row.short_code,
                "original_url": row.original_url,
                "clicks": int(row._mapping["count"]),
            }
            for row in result.all()
        ]

    async def get_breakdown(
        self, organization_id: UUID, dimension: str, days: int = 30, limit: int = 20
    ) -> list[dict[str, str | int]]:
        columns = {
            "browser": Click.browser,
            "device": Click.device,
            "country": Click.country,
            "city": Click.city,
            "referrer": Click.referrer,
            "os": Click.os,
        }
        column = columns[dimension]
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
        query = (
            select(column.label("value"), func.count(Click.id).label("count"))
            .where(
                Click.organization_id == organization_id,
                Click.created_at >= since,
                column.is_not(None),
            )
            .group_by(column)
            .order_by(func.count(Click.id).desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return [
            {"value": str(row.value), "count": int(row._mapping["count"])}
            for row in result.all()
        ]

    async def delete_older_than(self, retention_days: int) -> int:
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention_days)
        result = await self._session.execute(delete(Click).where(Click.created_at < cutoff))
        await self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)
