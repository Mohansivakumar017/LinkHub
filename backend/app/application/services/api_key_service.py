import secrets
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.infrastructure.db.models.api_key import ApiKey
from app.infrastructure.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.repositories.audit_repository import AuditRepository


@dataclass(frozen=True)
class CreatedApiKey:
    id: UUID
    name: str
    key: str
    key_prefix: str


class ApiKeyNotFoundError(Exception):
    pass


class ApiKeyService:
    def __init__(
        self,
        session: AsyncSession,
        repository: ApiKeyRepository | None = None,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._session = session
        self._keys = repository or ApiKeyRepository(session)
        self._audit = audit_repo or (
            AuditRepository(session) if isinstance(session, AsyncSession) else None
        )

    async def create(self, user_id: UUID, name: str) -> CreatedApiKey:
        raw_key = f"lhk_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:12]
        item = await self._keys.create(user_id, name, prefix, hash_token(raw_key))
        await self._record_audit(user_id, "api_key.created", "api_key", str(item.id))
        await self._session.commit()
        return CreatedApiKey(item.id, item.name, raw_key, item.key_prefix)

    async def list(self, user_id: UUID) -> list[ApiKey]:
        return await self._keys.list_for_user(user_id)

    async def revoke(self, user_id: UUID, key_id: UUID) -> None:
        item = await self._keys.get_for_user(key_id, user_id)
        if item is None:
            raise ApiKeyNotFoundError("API key not found")
        await self._keys.revoke(item)
        await self._record_audit(user_id, "api_key.revoked", "api_key", str(item.id))
        await self._session.commit()

    async def rotate(self, user_id: UUID, key_id: UUID) -> CreatedApiKey:
        item = await self._keys.get_for_user(key_id, user_id)
        if item is None or not item.is_active:
            raise ApiKeyNotFoundError("active API key not found")
        await self._keys.revoke(item)
        raw_key = f"lhk_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:12]
        replacement = await self._keys.create(
            user_id, item.name, prefix, hash_token(raw_key)
        )
        await self._record_audit(user_id, "api_key.rotated", "api_key", str(replacement.id))
        await self._session.commit()
        return CreatedApiKey(replacement.id, replacement.name, raw_key, prefix)

    async def _record_audit(
        self, actor_user_id: UUID, action: str, resource_type: str, resource_id: str
    ) -> None:
        if self._audit is not None:
            await self._audit.record(actor_user_id, action, resource_type, resource_id)
