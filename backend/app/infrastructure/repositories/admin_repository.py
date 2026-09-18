from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_client_ip
from app.infrastructure.db.models.audit_log import AuditLog
from app.infrastructure.db.models.click import Click
from app.infrastructure.db.models.organization import Organization
from app.infrastructure.db.models.url import URL
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.url_repository import URLRepository
from app.infrastructure.repositories.user_repository import UserRepository


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._urls = URLRepository(session)

    async def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        total = await self._session.scalar(select(func.count()).select_from(User))
        result = await self._session.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars()), int(total or 0)

    async def list_organizations(
        self, offset: int, limit: int
    ) -> tuple[list[Organization], int]:
        total = await self._session.scalar(select(func.count()).select_from(Organization))
        result = await self._session.execute(
            select(Organization)
            .order_by(Organization.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars()), int(total or 0)

    async def list_urls(self, offset: int, limit: int) -> tuple[list[URL], int]:
        total = await self._session.scalar(select(func.count()).select_from(URL))
        result = await self._session.execute(
            select(URL).order_by(URL.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars()), int(total or 0)

    async def metrics(self) -> dict[str, int]:
        values = await self._session.execute(
            select(
                select(func.count()).select_from(User).scalar_subquery().label("users"),
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True))
                .scalar_subquery()
                .label("active_users"),
                select(func.count()).select_from(Organization).scalar_subquery().label("organizations"),
                select(func.count()).select_from(URL).scalar_subquery().label("urls"),
                select(func.count()).select_from(Click).scalar_subquery().label("clicks"),
            )
        )
        row = values.one()
        return {key: int(value) for key, value in row._mapping.items()}

    async def list_audit_logs(
        self,
        offset: int,
        limit: int,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters = []
        if action is not None:
            filters.append(AuditLog.action == action)
        if resource_type is not None:
            filters.append(AuditLog.resource_type == resource_type)

        count_query = select(func.count()).select_from(AuditLog).where(*filters)
        total = await self._session.scalar(count_query)
        result = await self._session.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars()), int(total or 0)

    async def record_audit(
        self,
        actor_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=current_client_ip(),
            )
        )
        await self._session.flush()

    async def get_user(self, user_id: UUID) -> User | None:
        return await self._users.get_by_id(user_id)

    async def set_user_active(self, user: User, is_active: bool) -> None:
        await self._users.set_active(user, is_active)

    async def set_user_platform_admin(
        self, user: User, is_platform_admin: bool
    ) -> None:
        await self._users.set_platform_admin(user, is_platform_admin)

    async def get_url(self, url_id: UUID) -> URL | None:
        return await self._urls.get_by_id(url_id)

    async def restore_url(self, url: URL) -> None:
        await self._urls.restore(url)

    async def hard_delete_url(self, url: URL) -> None:
        await self._urls.hard_delete(url)
