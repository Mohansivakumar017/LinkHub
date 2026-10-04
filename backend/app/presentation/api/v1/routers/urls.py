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
from pydantic import BaseModel, Field, HttpUrl, field_validator
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
    ApiKeyPrincipal,
    get_api_key_principal,
    get_current_user,
    get_optional_current_user,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/urls", tags=["urls"])
_LINK_RESPONSE_HEADERS = {"Cache-Control": "private, no-store"}


def _link_access_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=_LINK_RESPONSE_HEADERS,
    )


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

    @field_validator("password")
    @classmethod
    def validate_password_byte_length(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("link password must be at most 72 UTF-8 bytes")
        return value


class URLUpdateRequest(BaseModel):
    original_url: HttpUrl | None = None
    custom_alias: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None
    one_time: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    click_limit: int | None = Field(default=None, ge=1)
    is_private: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password_byte_length(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("link password must be at most 72 UTF-8 bytes")
        return value


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
    api_principal: ApiKeyPrincipal = Depends(get_api_key_principal),
) -> list[dict]:
    """List organization links for service integrations authenticated by X-API-Key."""
    if (
        api_principal.organization_id is not None
        and api_principal.organization_id != organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is not scoped to this organization",
        )
    try:
        items = await URLService(session).list_urls(
            organization_id,
            api_principal.user.id,
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
    response: Response,
    password: str | None = Query(default=None, min_length=1, max_length=128),
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
) -> dict:
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
        raise _link_access_error(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except (URLExpiredError, URLClickLimitReachedError) as exc:
        raise _link_access_error(status.HTTP_410_GONE, str(exc)) from exc
    except URLNotFoundError as exc:
        raise _link_access_error(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    response.headers.update(_LINK_RESPONSE_HEADERS)
    return result


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
        raise _link_access_error(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except (URLExpiredError, URLClickLimitReachedError) as exc:
        raise _link_access_error(status.HTTP_410_GONE, str(exc)) from exc
    except URLNotFoundError as exc:
        raise _link_access_error(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return RedirectResponse(
        url=result["original_url"],
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers=_LINK_RESPONSE_HEADERS,
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
        item = await service.get_url(organization_id, current_user.id, url_id)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except URLNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    import qrcode

    target = f"{get_settings().public_base_url.rstrip('/')}/?link={item.short_code}"
    image = qrcode.make(target)
    buffer = BytesIO()
    image.save(buffer)
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
    max_file_bytes = 5 * 1024 * 1024
    content = await file.read(max_file_bytes + 1)
    if len(content) > max_file_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="CSV file too large")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(StringIO(decoded), strict=True)
    try:
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV format is invalid") from exc
    if not fieldnames or "original_url" not in fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV requires an original_url column")
    if any(not name.strip() for name in fieldnames) or len(set(fieldnames)) != len(fieldnames):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV headers must be non-empty and unique")

    rows: list[dict] = []
    row_indices: list[int] = []
    failures: list[dict[str, int | str]] = []
    index = 0
    while True:
        try:
            raw_row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV format is invalid") from exc
        if index >= 1000:
            failures.append({"index": index, "reason": "maximum 1,000 rows exceeded"})
            break
        if None in raw_row:
            failures.append({"index": index, "reason": "row contains more fields than the CSV header"})
            index += 1
            continue
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
            row = payload.model_dump()
            row["original_url"] = str(payload.original_url)
            rows.append(row)
            row_indices.append(index)
        except (TypeError, ValueError) as exc:
            failures.append({"index": index, "reason": str(exc)})
        index += 1

    service = URLService(session)
    try:
        created, failed = await service.bulk_create(organization_id, current_user.id, rows)
    except URLPermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    failures.extend(
        {
            "index": row_indices[f.index],
            "reason": f.reason,
        }
        for f in failed
    )
    return {
        "created": [_to_response(item) for item in created],
        "failed": failures,
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
