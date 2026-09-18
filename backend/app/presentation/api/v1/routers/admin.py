from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
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


class SetActiveRequest(BaseModel):
    is_active: bool


class SetPlatformAdminRequest(BaseModel):
    is_platform_admin: bool


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
         "resource_id": log.resource_id, "ip_address": log.ip_address,
         "details": log.details, "created_at": log.created_at.isoformat()}
        for log in logs
    ])


@router.patch("/users/{user_id}/active")
async def set_user_active(
    user_id: UUID,
    payload: SetActiveRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    repo = AdminRepository(session)
    target = await repo.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if str(target.id) == str(current_user.id) and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot deactivate your own account",
        )
    await repo.set_user_active(target, payload.is_active)
    await repo.record_audit(
        current_user.id,
        "admin.user.active_changed",
        "user",
        str(target.id),
        {"is_active": payload.is_active},
    )
    await session.commit()
    return {
        "id": str(target.id),
        "email": target.email,
        "is_active": target.is_active,
        "is_platform_admin": target.is_platform_admin,
    }


@router.patch("/users/{user_id}/platform-admin")
async def set_user_platform_admin(
    user_id: UUID,
    payload: SetPlatformAdminRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    repo = AdminRepository(session)
    target = await repo.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if str(target.id) == str(current_user.id) and not payload.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot revoke your own platform admin status",
        )
    await repo.set_user_platform_admin(target, payload.is_platform_admin)
    await repo.record_audit(
        current_user.id,
        "admin.user.platform_admin_changed",
        "user",
        str(target.id),
        {"is_platform_admin": payload.is_platform_admin},
    )
    await session.commit()
    return {
        "id": str(target.id),
        "email": target.email,
        "is_active": target.is_active,
        "is_platform_admin": target.is_platform_admin,
    }


@router.patch("/links/{link_id}/restore")
async def restore_link(
    link_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_platform_admin),
) -> dict[str, Any]:
    repo = AdminRepository(session)
    target = await repo.get_url(link_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    if not target.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="link is not deleted",
        )
    await repo.restore_url(target)
    await repo.record_audit(
        current_user.id,
        "admin.link.restored",
        "url",
        str(target.id),
        {"short_code": target.short_code},
    )
    await session.commit()
    return {
        "id": str(target.id),
        "short_code": target.short_code,
        "is_deleted": target.is_deleted,
        "is_archived": target.is_archived,
    }


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hard_delete_link(
    link_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_platform_admin),
) -> None:
    repo = AdminRepository(session)
    target = await repo.get_url(link_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link not found")
    short_code = target.short_code
    await repo.record_audit(
        current_user.id,
        "admin.link.hard_deleted",
        "url",
        str(target.id),
        {"short_code": short_code, "organization_id": str(target.organization_id)},
    )
    await repo.hard_delete_url(target)
    await session.commit()
