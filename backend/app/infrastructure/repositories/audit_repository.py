from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_client_ip
from app.infrastructure.db.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
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

    async def list_for_organization(
        self,
        organization_id: UUID,
        offset: int,
        limit: int,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters = [AuditLog.resource_id == str(organization_id)]
        if action is not None:
            filters.append(AuditLog.action == action)
        if resource_type is not None:
            filters.append(AuditLog.resource_type == resource_type)

        total = await self._session.scalar(
            select(func.count()).select_from(AuditLog).where(*filters)
        )
        result = await self._session.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars()), int(total or 0)
