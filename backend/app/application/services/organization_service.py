import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_refresh_token, hash_token
from app.infrastructure.db.models.organization import OrganizationRole
from app.infrastructure.email.sender import (
    BackgroundEmailSender,
    EmailMessage,
    EmailSender,
)
from app.infrastructure.repositories.audit_repository import AuditRepository
from app.infrastructure.repositories.organization_repository import (
    OrganizationInviteRepository,
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.infrastructure.repositories.user_repository import UserRepository


class OrganizationError(Exception):
    pass


class OrganizationNotFoundError(OrganizationError):
    pass


class PermissionDeniedError(OrganizationError):
    pass


class DuplicateOrganizationSlugError(OrganizationError):
    pass


class InvalidInviteError(OrganizationError):
    pass


class MemberNotFoundError(OrganizationError):
    pass


@dataclass(frozen=True)
class OrganizationInviteResult:
    invite_token: str


class OrganizationService:
    def __init__(
        self,
        session: AsyncSession,
        org_repo: OrganizationRepository | None = None,
        member_repo: OrganizationMemberRepository | None = None,
        invite_repo: OrganizationInviteRepository | None = None,
        user_repo: UserRepository | None = None,
        email_sender: EmailSender | None = None,
        audit_repo: AuditRepository | None = None,
    ) -> None:
        self._session = session
        self._orgs = org_repo or OrganizationRepository(session)
        self._members = member_repo or OrganizationMemberRepository(session)
        self._invites = invite_repo or OrganizationInviteRepository(session)
        self._users = user_repo or UserRepository(session)
        self._email_sender = email_sender or BackgroundEmailSender()
        self._audit = audit_repo or (
            AuditRepository(session) if isinstance(session, AsyncSession) else None
        )

    async def create_organization(self, user_id: UUID, name: str) -> UUID:
        slug = self._slugify(name)
        if await self._orgs.get_by_slug(slug) is not None:
            raise DuplicateOrganizationSlugError("organization slug already exists")

        try:
            organization = await self._orgs.create(
                name=name, slug=slug, owner_user_id=user_id
            )
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateOrganizationSlugError(
                "organization slug already exists"
            ) from exc
        await self._members.add_member(organization.id, user_id, OrganizationRole.OWNER)
        await self._record_audit(user_id, "organization.created", "organization", str(organization.id))
        await self._session.commit()
        return organization.id

    async def list_user_organizations(self, user_id: UUID) -> list[dict[str, str]]:
        organizations = await self._orgs.list_for_user(user_id)
        return [
            {"id": str(org.id), "name": org.name, "slug": org.slug, "owner_user_id": str(org.owner_user_id)}
            for org in organizations
        ]

    async def invite_member(
        self,
        requester_user_id: UUID,
        organization_id: UUID,
        invited_email: str,
        role: OrganizationRole,
    ) -> OrganizationInviteResult:
        organization = await self._orgs.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError("organization not found")

        requester_membership = await self._members.get_membership(organization_id, requester_user_id)
        if requester_membership is None or requester_membership.role not in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            raise PermissionDeniedError("insufficient privileges for invite")
        if role == OrganizationRole.OWNER:
            raise PermissionDeniedError("owner role cannot be assigned by invitation")

        invite_token = generate_refresh_token()
        invite_hash = hash_token(invite_token)
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7)
        await self._invites.create_invite(
            organization_id=organization_id,
            invited_email=invited_email,
            role=role,
            invited_by_user_id=requester_user_id,
            token_hash=invite_hash,
            expires_at=expires_at,
        )
        await self._record_audit(
            requester_user_id, "organization.invite_created", "organization",
            str(organization_id), {"invited_email": invited_email, "role": role.value},
        )
        await self._session.commit()

        await self._email_sender.send(
            EmailMessage(
                to_email=invited_email,
                subject=f"Invitation to join {organization.name}",
                body=f"Use this invite token to join organization: {invite_token}",
            )
        )
        return OrganizationInviteResult(invite_token=invite_token)

    async def list_members(
        self, requester_user_id: UUID, organization_id: UUID
    ) -> list[dict[str, str]]:
        if await self._orgs.get_by_id(organization_id) is None:
            raise OrganizationNotFoundError("organization not found")
        if await self._members.get_membership(organization_id, requester_user_id) is None:
            raise PermissionDeniedError("organization access denied")
        members = await self._members.list_members(organization_id)
        users = []
        for member in members:
            user = await self._users.get_by_id(member.user_id)
            if user is not None:
                users.append(
                    {
                        "user_id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name or "",
                        "role": member.role.value,
                    }
                )
        return users

    async def update_member_role(
        self,
        requester_user_id: UUID,
        organization_id: UUID,
        member_user_id: UUID,
        role: OrganizationRole,
    ) -> None:
        organization = await self._orgs.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError("organization not found")
        requester = await self._members.get_membership(
            organization_id, requester_user_id
        )
        target = await self._members.get_membership(organization_id, member_user_id)
        if requester is None or requester.role != OrganizationRole.OWNER:
            raise PermissionDeniedError("only the owner can change member roles")
        if target is None:
            raise MemberNotFoundError("member not found")
        if member_user_id == organization.owner_user_id or role == OrganizationRole.OWNER:
            raise PermissionDeniedError("owner role requires ownership transfer")
        await self._members.update_role(target, role)
        await self._record_audit(
            requester_user_id, "organization.member_role_updated", "organization",
            str(organization_id), {"member_user_id": str(member_user_id), "role": role.value},
        )
        await self._session.commit()

    async def remove_member(
        self, requester_user_id: UUID, organization_id: UUID, member_user_id: UUID
    ) -> None:
        organization = await self._orgs.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError("organization not found")
        requester = await self._members.get_membership(
            organization_id, requester_user_id
        )
        target = await self._members.get_membership(organization_id, member_user_id)
        if requester is None or requester.role not in {
            OrganizationRole.OWNER,
            OrganizationRole.ADMIN,
        }:
            raise PermissionDeniedError("insufficient privileges to remove member")
        if target is None:
            raise MemberNotFoundError("member not found")
        if member_user_id == organization.owner_user_id:
            raise PermissionDeniedError("organization owner cannot be removed")
        if requester.role == OrganizationRole.ADMIN and target.role != OrganizationRole.MEMBER:
            raise PermissionDeniedError("admins can only remove members")
        await self._members.remove_member(target)
        await self._record_audit(
            requester_user_id, "organization.member_removed", "organization",
            str(organization_id), {"member_user_id": str(member_user_id)},
        )
        await self._session.commit()

    async def accept_invite(self, user_id: UUID, invite_token: str) -> UUID:
        invite_hash = hash_token(invite_token.strip())
        invite = await self._invites.get_by_token_hash(invite_hash)
        now = datetime.now(UTC).replace(tzinfo=None)
        if invite is None or invite.accepted_at is not None or invite.expires_at <= now:
            raise InvalidInviteError("invalid or expired invite")

        user = await self._users.get_by_id(user_id)
        if user is None or user.email.lower() != invite.invited_email.lower():
            raise InvalidInviteError("invite email does not match user")

        existing = await self._members.get_membership(invite.organization_id, user_id)
        if existing is None:
            await self._members.add_member(invite.organization_id, user_id, invite.role)
        await self._invites.mark_accepted(invite)
        await self._record_audit(
            user_id, "organization.invite_accepted", "organization",
            str(invite.organization_id),
        )
        await self._session.commit()
        return invite.organization_id

    async def transfer_ownership(
        self,
        requester_user_id: UUID,
        organization_id: UUID,
        new_owner_user_id: UUID,
    ) -> None:
        organization = await self._orgs.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError("organization not found")
        if organization.owner_user_id != requester_user_id:
            raise PermissionDeniedError("only the owner can transfer ownership")

        requester_membership = await self._members.get_membership(organization_id, requester_user_id)
        new_owner_membership = await self._members.get_membership(organization_id, new_owner_user_id)
        if requester_membership is None or new_owner_membership is None:
            raise MemberNotFoundError("both users must be organization members")

        await self._members.update_role(requester_membership, OrganizationRole.ADMIN)
        await self._members.update_role(new_owner_membership, OrganizationRole.OWNER)
        await self._orgs.transfer_ownership(organization, new_owner_user_id)
        await self._record_audit(
            requester_user_id, "organization.ownership_transferred", "organization",
            str(organization_id), {"new_owner_user_id": str(new_owner_user_id)},
        )
        await self._session.commit()

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
    def _slugify(name: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
        return normalized or "organization"
