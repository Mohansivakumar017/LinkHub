from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.admin_repository import AdminRepository

router = APIRouter(prefix="/admin", tags=["admin"])


def _page(
    offset: int, limit: int, total: int, items: list[dict[str, Any]]
) -> dict[str, Any]:
    return {"items": items, "offset": offset, "limit": limit, "total": total}


@router.get("/users")
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    users, total = await AdminRepository(session).list_users(offset, limit)
    return _page(offset, limit, total, [
        {"id": str(user.id), "email": user.email, "full_name": user.full_name,
         "is_active": user.is_active, "is_platform_admin": user.is_platform_admin,
         "created_at": user.created_at.isoformat()}
        for user in users
    ])


@router.get("/organizations")
async def list_organizations(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    organizations, total = await AdminRepository(session).list_organizations(offset, limit)
    return _page(offset, limit, total, [
        {"id": str(org.id), "name": org.name, "slug": org.slug,
         "owner_user_id": str(org.owner_user_id), "created_at": org.created_at.isoformat()}
        for org in organizations
    ])


@router.get("/links")
async def list_links(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    links, total = await AdminRepository(session).list_urls(offset, limit)
    return _page(offset, limit, total, [
        {"id": str(link.id), "short_code": link.short_code,
         "organization_id": str(link.organization_id), "owner_user_id": str(link.owner_user_id),
         "is_archived": link.is_archived, "is_deleted": link.is_deleted,
         "created_at": link.created_at.isoformat()}
        for link in links
    ])


@router.get("/metrics")
async def platform_metrics(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, int]:
    return await AdminRepository(session).metrics()


@router.get("/audit-logs")
async def list_audit_logs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: str | None = Query(default=None, min_length=1, max_length=128),
    resource_type: str | None = Query(default=None, min_length=1, max_length=64),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    logs, total = await AdminRepository(session).list_audit_logs(
        offset, limit, action=action, resource_type=resource_type
    )
    return _page(offset, limit, total, [
        {"id": str(log.id), "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
         "action": log.action, "resource_type": log.resource_type,
         "resource_id": log.resource_id, "details": log.details,
         "created_at": log.created_at.isoformat()}
        for log in logs
    ])
