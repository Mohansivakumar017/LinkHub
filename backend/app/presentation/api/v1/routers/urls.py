import csv
from datetime import datetime
from io import BytesIO, StringIO
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.analytics_service import (
    AnalyticsService,
    ClickContext,
    URLAccessDeniedError,
    URLClickLimitReachedError,
    URLExpiredError,
)
from app.application.services.url_service import (
    URLAliasConflictError,
    URLNotFoundError,
    URLPermissionDeniedError,
    URLService,
)
from app.core.config import get_settings
from app.core.dependencies import (
    get_api_key_user,
    get_current_user,
    get_optional_current_user,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/urls", tags=["urls"])


class URLCreateRequest(BaseModel):
    organization_id: UUID
    original_url: HttpUrl
    custom_alias: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None
    one_time: bool = False
    password: str | None = Field(default=None, min_length=8, max_length=128)
    click_limit: int | None = Field(default=None, ge=1)
    is_private: bool = False


class URLUpdateRequest(BaseModel):
    original_url: HttpUrl | None = None
    custom_alias: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None
    one_time: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    click_limit: int | None = Field(default=None, ge=1)
    is_private: bool | None = None


class URLBulkCreateRequest(BaseModel):
    organization_id: UUID
    rows: list[URLCreateRequest] = Field(max_length=1000)


class URLBulkDeleteRequest(BaseModel):
    organization_id: UUID
    ids: list[UUID] = Field(min_length=1, max_length=1000)


def _to_response(item) -> dict:
    return {
        "id": str(item.id),
        "organization_id": str(item.organization_id),
        "owner_user_id": str(item.owner_user_id),
        "original_url": item.original_url,
        "short_code": item.short_code,
        "custom_alias": item.custom_alias,
        "title": item.title,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "one_time": item.one_time,
        "click_limit": item.click_limit,
        "is_private": item.is_private,
        "password_protected": bool(getattr(item, "password_hash", None)),
        "is_archived": item.is_archived,
    }


def _csv_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_url(
    payload: URLCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = URLService(session)
    try:
        item = await service.create_url(
            organization_id=payload.organization_id,
            owner_user_id=current_user.id,
            original_url=str(payload.original_url),
            custom_alias=payload.custom_alias,
            title=payload.title,
            expires_at=payload.expires_at,
            one_time=payload.one_time,
            password=payload.password,
            click_limit=payload.click_limit,
            is_private=payload.is_private,
        )
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLAliasConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_response(item)


@router.get("/organizations/{organization_id}")
async def list_urls(
    organization_id: UUID,
    search: str | None = Query(default=None, max_length=128),
    archived: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sort: str = Query(default="created_at", pattern="^(created_at|updated_at|short_code)$"),
    descending: bool = True,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    service = URLService(session)
    try:
        items = await service.list_urls(
            organization_id,
            current_user.id,
            search=search,
            archived=archived,
            offset=offset,
            limit=limit,
            sort=sort,
            descending=descending,
        )
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [_to_response(item) for item in items]


@router.get("/api/organizations/{organization_id}")
async def list_urls_with_api_key(
    organization_id: UUID,
    search: str | None = Query(default=None, max_length=128),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    api_user: User = Depends(get_api_key_user),
) -> list[dict]:
    """List organization links for service integrations authenticated by X-API-Key."""
    try:
        items = await URLService(session).list_urls(
            organization_id,
            api_user.id,
            search=search,
            offset=offset,
            limit=limit,
        )
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [_to_response(item) for item in items]


@router.get("/resolve/{short_code}")
async def resolve_short_code(
    short_code: str,
    request: Request,
    password: str | None = Query(default=None, min_length=1, max_length=128),
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
    service = AnalyticsService(session)
    try:
        track_kwargs = (
            {"requester_user_id": current_user.id} if current_user else {}
        )
        return await service.track_click(
            short_code=short_code,
            context=ClickContext(
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                referrer=request.headers.get("referer"),
                country=request.headers.get("x-country"),
                city=request.headers.get("x-city"),
            ),
            password=password,
            **track_kwargs,
        )
    except URLAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except (URLExpiredError, URLClickLimitReachedError) as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/r/{short_code}", include_in_schema=False)
async def redirect_short_code(
    short_code: str,
    request: Request,
    password: str | None = Query(default=None, min_length=1, max_length=128),
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
) -> RedirectResponse:
    """Track a public link visit and redirect the browser to its destination."""
    service = AnalyticsService(session)
    try:
        track_kwargs = (
            {"requester_user_id": current_user.id} if current_user else {}
        )
        result = await service.track_click(
            short_code=short_code,
            context=ClickContext(
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                referrer=request.headers.get("referer"),
                country=request.headers.get("x-country"),
                city=request.headers.get("x-city"),
            ),
            password=password,
            **track_kwargs,
        )
    except URLAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except (URLExpiredError, URLClickLimitReachedError) as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RedirectResponse(
        url=result["original_url"],
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/{url_id}/qr", response_class=Response)
async def download_qr_code(
    url_id: UUID,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = URLService(session)
    try:
        items = await service.list_urls(organization_id, current_user.id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    item = next((candidate for candidate in items if candidate.id == url_id), None)
    if item is None or item.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="url not found")

    import qrcode

    target = f"{get_settings().public_base_url.rstrip('/')}/api/v1/urls/r/{item.short_code}"
    image = qrcode.make(target)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{item.short_code}.png"'},
    )


@router.patch("/{url_id}")
async def update_url(
    url_id: UUID,
    payload: URLUpdateRequest,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = URLService(session)
    changes = payload.model_dump(exclude_unset=True)
    if "original_url" in changes:
        changes["original_url"] = str(changes["original_url"])
    try:
        item = await service.update_url(organization_id, current_user.id, url_id, **changes)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLAliasConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(item)


@router.delete("/{url_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_url(
    url_id: UUID,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = URLService(session)
    try:
        await service.delete_url(organization_id, current_user.id, url_id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{url_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_url(
    url_id: UUID,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = URLService(session)
    try:
        await service.archive_url(organization_id, current_user.id, url_id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{url_id}/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_url(
    url_id: UUID,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = URLService(session)
    try:
        await service.restore_url(organization_id, current_user.id, url_id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{url_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_url(
    url_id: UUID,
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = URLService(session)
    try:
        item = await service.duplicate_url(organization_id, current_user.id, url_id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(item)


@router.post("/bulk/create", status_code=status.HTTP_201_CREATED)
async def bulk_create_urls(
    payload: URLBulkCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = URLService(session)
    rows = [
        {
            "original_url": str(r.original_url),
            "custom_alias": r.custom_alias,
            "title": r.title,
            "expires_at": r.expires_at,
            "one_time": r.one_time,
            "password": r.password,
            "click_limit": r.click_limit,
            "is_private": r.is_private,
        }
        for r in payload.rows
    ]
    try:
        created, failed = await service.bulk_create(payload.organization_id, current_user.id, rows)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {
        "created": [_to_response(item) for item in created],
        "failed": [{"index": f.index, "reason": f.reason} for f in failed],
    }


@router.post("/bulk/upload", status_code=status.HTTP_201_CREATED)
async def bulk_upload_urls(
    organization_id: UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Import up to 1,000 links from a CSV with an original_url column."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file too large")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(StringIO(decoded))
    if not reader.fieldnames or "original_url" not in reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV requires an original_url column")

    rows: list[dict] = []
    failures: list[dict[str, int | str]] = []
    for index, raw_row in enumerate(reader):
        if index >= 1000:
            failures.append({"index": index, "reason": "maximum 1,000 rows exceeded"})
            break
        try:
            payload = URLCreateRequest.model_validate(
                {
                    "organization_id": organization_id,
                    "original_url": raw_row.get("original_url", ""),
                    "custom_alias": raw_row.get("custom_alias") or None,
                    "title": raw_row.get("title") or None,
                    "expires_at": raw_row.get("expires_at") or None,
                    "one_time": _csv_bool(raw_row.get("one_time")),
                    "password": raw_row.get("password") or None,
                    "click_limit": (
                        int(raw_row["click_limit"]) if raw_row.get("click_limit") else None
                    ),
                    "is_private": _csv_bool(raw_row.get("is_private")),
                }
            )
            rows.append(payload.model_dump())
        except (TypeError, ValueError) as exc:
            failures.append({"index": index, "reason": str(exc)})

    service = URLService(session)
    try:
        created, failed = await service.bulk_create(organization_id, current_user.id, rows)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {
        "created": [_to_response(item) for item in created],
        "failed": failures + [{"index": f.index, "reason": f.reason} for f in failed],
    }


@router.delete("/bulk/delete", status_code=status.HTTP_200_OK)
async def bulk_delete_urls(
    payload: URLBulkDeleteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = URLService(session)
    try:
        count = await service.bulk_delete(payload.organization_id, current_user.id, payload.ids)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"deleted_count": count}
