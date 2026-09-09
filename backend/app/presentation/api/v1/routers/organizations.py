from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.organization_service import (
    DuplicateOrganizationSlugError,
    InvalidInviteError,
    MemberNotFoundError,
    OrganizationNotFoundError,
    OrganizationService,
    PermissionDeniedError,
)
from app.core.dependencies import get_current_user
from app.infrastructure.db.models.organization import OrganizationRole
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/organizations", tags=["organizations"])


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class CreateOrganizationResponse(BaseModel):
    id: str


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER


class InviteMemberResponse(BaseModel):
    invite_token: str


class AcceptInviteRequest(BaseModel):
    invite_token: str


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: UUID


class UpdateMemberRoleRequest(BaseModel):
    role: OrganizationRole


@router.post("", response_model=CreateOrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrganizationRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CreateOrganizationResponse:
    service = OrganizationService(session)
    try:
        org_id = await service.create_organization(current_user.id, payload.name)
    except DuplicateOrganizationSlugError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CreateOrganizationResponse(id=str(org_id))


@router.get("")
async def list_organizations(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    service = OrganizationService(session)
    return await service.list_user_organizations(current_user.id)


@router.post("/{organization_id}/invites", response_model=InviteMemberResponse)
async def invite_member(
    organization_id: UUID,
    payload: InviteMemberRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InviteMemberResponse:
    service = OrganizationService(session)
    try:
        result = await service.invite_member(
            requester_user_id=current_user.id,
            organization_id=organization_id,
            invited_email=str(payload.email),
            role=payload.role,
        )
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return InviteMemberResponse(invite_token=result.invite_token)


@router.get("/{organization_id}/members")
async def list_members(
    organization_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    service = OrganizationService(session)
    try:
        return await service.list_members(current_user.id, organization_id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch("/{organization_id}/members/{member_user_id}")
async def update_member_role(
    organization_id: UUID,
    member_user_id: UUID,
    payload: UpdateMemberRoleRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    service = OrganizationService(session)
    try:
        await service.update_member_role(
            current_user.id, organization_id, member_user_id, payload.role
        )
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"user_id": str(member_user_id), "role": payload.role.value}


@router.delete("/{organization_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: UUID,
    member_user_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = OrganizationService(session)
    try:
        await service.remove_member(current_user.id, organization_id, member_user_id)
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/invites/accept", status_code=status.HTTP_200_OK)
async def accept_invite(
    payload: AcceptInviteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    service = OrganizationService(session)
    try:
        org_id = await service.accept_invite(current_user.id, payload.invite_token)
    except InvalidInviteError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"organization_id": str(org_id), "status": "accepted"}


@router.post("/{organization_id}/transfer-ownership", status_code=status.HTTP_204_NO_CONTENT)
async def transfer_ownership(
    organization_id: UUID,
    payload: TransferOwnershipRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    service = OrganizationService(session)
    try:
        await service.transfer_ownership(
            requester_user_id=current_user.id,
            organization_id=organization_id,
            new_owner_user_id=payload.new_owner_user_id,
        )
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
