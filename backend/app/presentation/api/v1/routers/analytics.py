from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.analytics_service import (
    AnalyticsPermissionDeniedError,
    AnalyticsService,
)
from app.core.dependencies import get_current_user
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/organizations/{organization_id}/overview")
async def organization_overview(
    organization_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = AnalyticsService(session)
    try:
        return await service.get_overview(organization_id, current_user.id, days=days)
    except AnalyticsPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/organizations/{organization_id}/timeseries")
async def organization_time_series(
    organization_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    granularity: str = Query(default="daily", pattern="^(daily|weekly)$"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    service = AnalyticsService(session)
    try:
        return await service.get_time_series(
            organization_id, current_user.id, days=days, granularity=granularity
        )
    except AnalyticsPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/organizations/{organization_id}/top-links")
async def organization_top_links(
    organization_id: UUID,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    service = AnalyticsService(session)
    try:
        return await service.get_top_links(organization_id, current_user.id, days=days, limit=limit)
    except AnalyticsPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/organizations/{organization_id}/breakdown")
async def organization_breakdown(
    organization_id: UUID,
    dimension: str = Query(
        default="browser",
        pattern="^(browser|device|country|city|referrer|os)$",
    ),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    service = AnalyticsService(session)
    try:
        return await service.get_breakdown(
            organization_id,
            current_user.id,
            dimension=dimension,
            days=days,
            limit=limit,
        )
    except AnalyticsPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
