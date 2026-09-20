import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.url_service import URLNotFoundError
from app.core.security import verify_password
from app.infrastructure.cache.url_cache import RedisURLCache, URLCache
from app.infrastructure.repositories.click_repository import ClickRepository
from app.infrastructure.repositories.organization_repository import (
    OrganizationMemberRepository,
)
from app.infrastructure.repositories.url_repository import URLRepository


@dataclass(frozen=True)
class ClickContext:
    ip_address: str | None
    user_agent: str | None
    referrer: str | None
    country: str | None = None
    city: str | None = None


class AnalyticsPermissionDeniedError(Exception):
    pass


class URLAccessDeniedError(Exception):
    pass


class URLExpiredError(URLNotFoundError):
    pass


class URLClickLimitReachedError(URLNotFoundError):
    pass


class AnalyticsService:
    def __init__(
        self,
        session: AsyncSession,
        click_repo: ClickRepository | None = None,
        url_repo: URLRepository | None = None,
        org_member_repo: OrganizationMemberRepository | None = None,
        cache: URLCache | None = None,
    ) -> None:
        self._session = session
        self._clicks = click_repo or ClickRepository(session)
        self._urls = url_repo or URLRepository(session)
        self._members = org_member_repo or OrganizationMemberRepository(session)
        self._cache = cache or RedisURLCache()

    async def track_click(
        self,
        short_code: str,
        context: ClickContext,
        password: str | None = None,
        requester_user_id: UUID | None = None,
    ) -> dict:
        cached = await self._cache.get(short_code)
        url: Any = None
        if cached is not None and cached.get("cacheable", False):
            try:
                url = SimpleNamespace(
                    id=UUID(cached["id"]),
                    organization_id=UUID(cached["organization_id"]),
                    short_code=cached["short_code"],
                    original_url=cached["original_url"],
                    is_private=cached["is_private"],
                    expires_at=(
                        datetime.fromisoformat(cached["expires_at"])
                        if cached["expires_at"]
                        else None
                    ),
                    one_time=cached["one_time"],
                    click_limit=cached["click_limit"],
                    password_hash=None,
                    is_archived=False,
                    is_deleted=False,
                )
            except (KeyError, TypeError, ValueError):
                await self._cache.delete(short_code)
        if url is None:
            get_for_update = getattr(
                self._urls, "get_by_short_code_for_update", self._urls.get_by_short_code
            )
            url = await get_for_update(short_code)
        if url is None or url.is_deleted:
            raise URLNotFoundError("url not found")
        if url.expires_at and url.expires_at <= datetime.now(UTC).replace(tzinfo=None):
            raise URLExpiredError("url expired")
        password_hash = getattr(url, "password_hash", None)
        if password_hash and (
            password is None or not verify_password(password, password_hash)
        ):
            raise URLAccessDeniedError("link password required")
        if getattr(url, "is_private", False):
            if requester_user_id is None:
                raise URLAccessDeniedError("private link requires authentication")
            membership = await self._members.get_membership(
                url.organization_id, requester_user_id
            )
            if membership is None:
                raise URLAccessDeniedError("private link access denied")

        click_count = await self._clicks.count_for_url(url.id)
        if url.is_archived:
            if url.one_time and click_count >= 1:
                raise URLClickLimitReachedError("one-time link already used")
            if url.click_limit and click_count >= url.click_limit:
                raise URLClickLimitReachedError("click limit reached")
            raise URLNotFoundError("url not found")
        if url.one_time and click_count >= 1:
            raise URLClickLimitReachedError("one-time link already used")
        if url.click_limit and click_count >= url.click_limit:
            raise URLClickLimitReachedError("click limit reached")

        visitor_key = self._make_visitor_key(context.ip_address, context.user_agent)
        browser, os_name, device = self._parse_user_agent(context.user_agent)
        await self._clicks.create_click(
            url_id=url.id,
            organization_id=url.organization_id,
            visitor_key=visitor_key,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            referrer=context.referrer,
            browser=browser,
            os=os_name,
            device=device,
            country=context.country,
            city=context.city,
        )

        should_archive = url.one_time or (url.click_limit is not None and click_count + 1 >= url.click_limit)
        if should_archive:
            await self._urls.update(url, is_archived=True, archived_at=datetime.now(UTC).replace(tzinfo=None))
            await self._cache.delete(short_code)
        elif (
            not getattr(url, "password_hash", None)
            and not url.is_private
            and not url.one_time
            and url.click_limit is None
        ):
            await self._cache.set(
                short_code,
                {
                    "id": str(url.id),
                    "organization_id": str(url.organization_id),
                    "short_code": url.short_code,
                    "original_url": url.original_url,
                    "is_private": url.is_private,
                    "expires_at": url.expires_at.isoformat() if url.expires_at else None,
                    "one_time": url.one_time,
                    "click_limit": url.click_limit,
                    "cacheable": True,
                },
            )

        await self._session.commit()
        return {
            "short_code": url.short_code,
            "original_url": url.original_url,
            "is_private": url.is_private,
            "one_time": url.one_time,
            "click_limit": url.click_limit,
        }

    async def get_overview(self, organization_id: UUID, requester_user_id: UUID, days: int = 30) -> dict:
        await self._require_membership(organization_id, requester_user_id)
        return await self._clicks.get_org_overview(organization_id, days=days)

    async def get_time_series(
        self,
        organization_id: UUID,
        requester_user_id: UUID,
        days: int = 30,
        granularity: str = "daily",
    ) -> list[dict]:
        await self._require_membership(organization_id, requester_user_id)
        return await self._clicks.get_time_series(organization_id, days=days, granularity=granularity)

    async def get_top_links(
        self,
        organization_id: UUID,
        requester_user_id: UUID,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict]:
        await self._require_membership(organization_id, requester_user_id)
        return await self._clicks.get_top_links(organization_id, days=days, limit=limit)

    async def get_breakdown(
        self,
        organization_id: UUID,
        requester_user_id: UUID,
        dimension: str,
        days: int = 30,
        limit: int = 20,
    ) -> list[dict]:
        await self._require_membership(organization_id, requester_user_id)
        return await self._clicks.get_breakdown(
            organization_id, dimension=dimension, days=days, limit=limit
        )

    async def _require_membership(self, organization_id: UUID, user_id: UUID) -> None:
        membership = await self._members.get_membership(organization_id, user_id)
        if membership is None:
            raise AnalyticsPermissionDeniedError("organization access denied")

    @staticmethod
    def _make_visitor_key(ip_address: str | None, user_agent: str | None) -> str:
        raw = f"{ip_address or '-'}|{user_agent or '-'}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_user_agent(user_agent: str | None) -> tuple[str | None, str | None, str | None]:
        if not user_agent:
            return None, None, None
        browser = (
            "Edge" if "Edg/" in user_agent
            else "Chrome" if "Chrome/" in user_agent
            else "Firefox" if "Firefox/" in user_agent
            else "Safari" if "Safari/" in user_agent
            else "Other"
        )
        os_name = (
            "Android" if "Android" in user_agent
            else "iOS" if re.search(r"iPhone|iPad|iPod", user_agent)
            else "Windows" if "Windows" in user_agent
            else "macOS" if "Mac OS X" in user_agent
            else "Linux" if "Linux" in user_agent
            else "Other"
        )
        device = (
            "Mobile" if re.search(r"Mobile|Android|iPhone|iPad|iPod", user_agent)
            else "Desktop"
        )
        return browser, os_name, device
