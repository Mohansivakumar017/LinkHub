import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.infrastructure.cache.url_cache import RedisURLCache, URLCache
from app.infrastructure.repositories.audit_repository import AuditRepository
from app.infrastructure.repositories.organization_repository import (
    OrganizationMemberRepository,
)
from app.infrastructure.repositories.url_repository import URLRepository


class URLServiceError(Exception):
    pass


class URLNotFoundError(URLServiceError):
    pass


class URLPermissionDeniedError(URLServiceError):
    pass


class URLAliasConflictError(URLServiceError):
    pass


@dataclass(frozen=True)
class BulkCreateFailure:
    index: int
    reason: str


class URLService:
    def __init__(
        self,
        session: AsyncSession,
        url_repo: URLRepository | None = None,
        membership_repo: OrganizationMemberRepository | None = None,
        cache: URLCache | None = None,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._session = session
        self._urls = url_repo or URLRepository(session)
        self._members = membership_repo or OrganizationMemberRepository(session)
        self._cache = cache or RedisURLCache()
        self._audit = audit_repo or (
            AuditRepository(session) if isinstance(session, AsyncSession) else None
        )

    async def create_url(
        self,
        organization_id: UUID,
        owner_user_id: UUID,
        original_url: str,
        custom_alias: str | None = None,
        title: str | None = None,
        expires_at: datetime | None = None,
        one_time: bool = False,
        password: str | None = None,
        click_limit: int | None = None,
        is_private: bool = False,
    ):
        await self._require_membership(organization_id, owner_user_id)
        short_code = await self._resolve_short_code(custom_alias)
        try:
            item = await self._urls.create(
                organization_id=organization_id,
                owner_user_id=owner_user_id,
                original_url=original_url,
                short_code=short_code,
                custom_alias=custom_alias,
                title=title,
                expires_at=expires_at,
                one_time=one_time,
                password_hash=hash_password(password) if password else None,
                click_limit=click_limit,
                is_private=is_private,
            )
        except IntegrityError as exc:
            await self._session.rollback()
            raise URLAliasConflictError("alias already taken") from exc
        await self._record_audit(owner_user_id, "url.created", "url", str(item.id))
        await self._session.commit()
        if self._cacheable(item):
            await self._cache.set(short_code, self._to_cache_payload(item))
        return item

    async def update_url(self, organization_id: UUID, requester_user_id: UUID, url_id: UUID, **changes):
        await self._require_membership(organization_id, requester_user_id)
        get_for_update = getattr(self._urls, "get_by_id_for_update", self._urls.get_by_id)
        item = await get_for_update(url_id)
        if item is None or item.organization_id != organization_id or item.is_deleted:
            raise URLNotFoundError("url not found")
        old_code = item.short_code
        if "custom_alias" in changes:
            raw_alias = changes["custom_alias"]
            if raw_alias is None:
                changes.pop("custom_alias")
            else:
                alias = self._sanitize_alias(raw_alias)
                if alias != item.short_code and await self._urls.is_alias_taken(alias):
                    raise URLAliasConflictError("alias already taken")
                changes["custom_alias"] = alias
                changes["short_code"] = alias
        if "password" in changes:
            raw = changes.pop("password")
            changes["password_hash"] = hash_password(raw) if raw else None
        if "expires_at" in changes:
            changes["expiration_notified_at"] = None
        try:
            updated = await self._urls.update(item, **changes)
        except IntegrityError as exc:
            await self._session.rollback()
            raise URLAliasConflictError("alias already taken") from exc
        await self._record_audit(
            requester_user_id, "url.updated", "url", str(item.id)
        )
        await self._session.commit()
        await self._cache.delete(old_code)
        if self._cacheable(updated):
            await self._cache.set(updated.short_code, self._to_cache_payload(updated))
        return updated

    async def delete_url(self, organization_id: UUID, requester_user_id: UUID, url_id: UUID) -> None:
        await self._require_membership(organization_id, requester_user_id)
        item = await self._urls.get_by_id(url_id)
        if item is None or item.organization_id != organization_id or item.is_deleted:
            raise URLNotFoundError("url not found")
        await self._urls.soft_delete(item)
        await self._record_audit(requester_user_id, "url.deleted", "url", str(item.id))
        await self._session.commit()
        await self._cache.delete(item.short_code)

    async def archive_url(self, organization_id: UUID, requester_user_id: UUID, url_id: UUID) -> None:
        await self._require_membership(organization_id, requester_user_id)
        item = await self._urls.get_by_id(url_id)
        if item is None or item.organization_id != organization_id or item.is_deleted:
            raise URLNotFoundError("url not found")
        await self._urls.update(item, is_archived=True, archived_at=datetime.now(UTC).replace(tzinfo=None))
        await self._record_audit(requester_user_id, "url.archived", "url", str(item.id))
        await self._session.commit()
        await self._cache.delete(item.short_code)

    async def restore_url(self, organization_id: UUID, requester_user_id: UUID, url_id: UUID) -> None:
        await self._require_membership(organization_id, requester_user_id)
        item = await self._urls.get_by_id(url_id)
        if item is None or item.organization_id != organization_id or item.is_deleted:
            raise URLNotFoundError("url not found")
        await self._urls.update(item, is_archived=False, archived_at=None)
        await self._record_audit(requester_user_id, "url.restored", "url", str(item.id))
        await self._session.commit()
        if self._cacheable(item):
            await self._cache.set(item.short_code, self._to_cache_payload(item))

    async def duplicate_url(self, organization_id: UUID, requester_user_id: UUID, url_id: UUID):
        await self._require_membership(organization_id, requester_user_id)
        original = await self._urls.get_by_id(url_id)
        if original is None or original.organization_id != organization_id or original.is_deleted:
            raise URLNotFoundError("url not found")
        code = await self._resolve_short_code(None)
        duplicate = await self._urls.create(
            organization_id=original.organization_id,
            owner_user_id=requester_user_id,
            original_url=original.original_url,
            short_code=code,
            custom_alias=None,
            title=f"{original.title or 'Link'} (copy)",
            expires_at=original.expires_at,
            one_time=original.one_time,
            password_hash=original.password_hash,
            click_limit=original.click_limit,
            is_private=original.is_private,
        )
        await self._record_audit(
            requester_user_id, "url.duplicated", "url", str(duplicate.id),
            {"source_url_id": str(original.id)},
        )
        await self._session.commit()
        if self._cacheable(duplicate):
            await self._cache.set(duplicate.short_code, self._to_cache_payload(duplicate))
        return duplicate

    async def bulk_create(self, organization_id: UUID, requester_user_id: UUID, rows: list[dict]):
        created = []
        failed: list[BulkCreateFailure] = []
        for idx, row in enumerate(rows):
            try:
                item = await self.create_url(
                    organization_id=organization_id,
                    owner_user_id=requester_user_id,
                    original_url=row["original_url"],
                    custom_alias=row.get("custom_alias"),
                    title=row.get("title"),
                    expires_at=row.get("expires_at"),
                    one_time=row.get("one_time", False),
                    password=row.get("password"),
                    click_limit=row.get("click_limit"),
                    is_private=row.get("is_private", False),
                )
                created.append(item)
            except (URLServiceError, KeyError, ValueError) as exc:
                failed.append(BulkCreateFailure(index=idx, reason=str(exc)))
        return created, failed

    async def bulk_delete(self, organization_id: UUID, requester_user_id: UUID, ids: list[UUID]) -> int:
        await self._require_membership(organization_id, requester_user_id)
        items = []
        for url_id in ids:
            item = await self._urls.get_by_id(url_id)
            if item and item.organization_id == organization_id and not item.is_deleted:
                items.append(item)
        deleted = await self._urls.bulk_soft_delete(organization_id, ids)
        await self._record_audit(
            requester_user_id, "url.bulk_deleted", "organization", str(organization_id),
            {"deleted_count": deleted},
        )
        await self._session.commit()
        for item in items:
            await self._cache.delete(item.short_code)
        return deleted

    async def list_urls(
        self,
        organization_id: UUID,
        requester_user_id: UUID,
        search: str | None = None,
        archived: bool | None = None,
        offset: int = 0,
        limit: int = 50,
        sort: str = "created_at",
        descending: bool = True,
    ):
        await self._require_membership(organization_id, requester_user_id)
        return await self._urls.list_for_org(
            organization_id,
            search=search,
            archived=archived,
            offset=offset,
            limit=limit,
            sort=sort,
            descending=descending,
        )

    async def resolve_short_code(self, short_code: str):
        cached = await self._cache.get(short_code)
        if cached and cached.get("cacheable", False):
            return cached
        item = await self._urls.get_by_short_code(short_code)
        if item is None or item.is_deleted or item.is_archived:
            raise URLNotFoundError("url not found")
        if not self._cacheable(item):
            raise URLNotFoundError("link requires guarded access")
        payload = self._to_cache_payload(item)
        await self._cache.set(short_code, payload)
        return payload

    async def _require_membership(self, organization_id: UUID, user_id: UUID) -> None:
        membership = await self._members.get_membership(organization_id, user_id)
        if membership is None:
            raise URLPermissionDeniedError("organization access denied")

    async def _resolve_short_code(self, custom_alias: str | None) -> str:
        if custom_alias:
            alias = self._sanitize_alias(custom_alias)
            if await self._urls.is_alias_taken(alias):
                raise URLAliasConflictError("alias already taken")
            return alias
        while True:
            generated = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].lower()
            if not await self._urls.is_alias_taken(generated):
                return generated

    @staticmethod
    def _sanitize_alias(raw_alias: str) -> str:
        alias = re.sub(r"[^a-zA-Z0-9-_]", "-", raw_alias.strip().lower()).strip("-")
        if len(alias) < 3:
            raise URLAliasConflictError("alias too short")
        return alias[:64]

    @staticmethod
    def _cacheable(item) -> bool:
        return (
            not getattr(item, "is_private", False)
            and getattr(item, "password_hash", None) is None
            and not getattr(item, "one_time", False)
            and getattr(item, "click_limit", None) is None
        )

    async def _record_audit(
        self,
        actor_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> None:
        if self._audit is not None:
            await self._audit.record(
                actor_user_id, action, resource_type, resource_id, details
            )

    @staticmethod
    def _to_cache_payload(item) -> dict:
        return {
            "id": str(item.id),
            "organization_id": str(item.organization_id),
            "short_code": item.short_code,
            "original_url": item.original_url,
            "is_private": item.is_private,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "one_time": item.one_time,
            "click_limit": item.click_limit,
            "cacheable": True,
        }
