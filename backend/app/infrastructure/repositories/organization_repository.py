from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.organization import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    OrganizationRole,
)


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, slug: str, owner_user_id: UUID) -> Organization:
        organization = Organization(name=name, slug=slug, owner_user_id=owner_user_id)
        self._session.add(organization)
        await self._session.flush()
        return organization

    async def get_by_id(self, organization_id: UUID) -> Organization | None:
        query = select(Organization).where(Organization.id == organization_id)
        result = await self._session.execute(query)
        return result.scalars().first()

    async def get_by_slug(self, slug: str) -> Organization | None:
        query = select(Organization).where(Organization.slug == slug)
        result = await self._session.execute(query)
        return result.scalars().first()

    async def list_for_user(
        self, user_id: UUID
    ) -> list[tuple[Organization, OrganizationRole]]:
        query = (
            select(Organization, OrganizationMember.role)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.created_at.desc())
        )
        result = await self._session.execute(query)
        return list(result.all())

    async def transfer_ownership(self, organization: Organization, new_owner_user_id: UUID) -> None:
        organization.owner_user_id = new_owner_user_id
        await self._session.flush()


class OrganizationMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_member(
        self, organization_id: UUID, user_id: UUID, role: OrganizationRole
    ) -> OrganizationMember:
        member = OrganizationMember(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
        )
        self._session.add(member)
        await self._session.flush()
        return member

    async def get_membership(self, organization_id: UUID, user_id: UUID) -> OrganizationMember | None:
        query = select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        result = await self._session.execute(query)
        return result.scalars().first()

    async def get_membership_for_update(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        query = (
            select(OrganizationMember)
            .where(
                and_(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalars().first()

    async def update_role(self, membership: OrganizationMember, role: OrganizationRole) -> None:
        membership.role = role
        await self._session.flush()

    async def list_members(self, organization_id: UUID) -> list[OrganizationMember]:
        result = await self._session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.joined_at.asc())
        )
        return list(result.scalars().all())

    async def remove_member(self, membership: OrganizationMember) -> None:
        await self._session.delete(membership)
        await self._session.flush()


class OrganizationInviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_invite(
        self,
        organization_id: UUID,
        invited_email: str,
        role: OrganizationRole,
        invited_by_user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> OrganizationInvite:
        invite = OrganizationInvite(
            organization_id=organization_id,
            invited_email=invited_email.lower(),
            role=role,
            invited_by_user_id=invited_by_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(invite)
        await self._session.flush()
        return invite

    async def get_by_token_hash(self, token_hash: str) -> OrganizationInvite | None:
        query = (
            select(OrganizationInvite)
            .where(OrganizationInvite.token_hash == token_hash)
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalars().first()

    async def list_open_for_organization(
        self, organization_id: UUID
    ) -> list[OrganizationInvite]:
        result = await self._session.execute(
            select(OrganizationInvite)
            .where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.accepted_at.is_(None),
                OrganizationInvite.revoked_at.is_(None),
            )
            .order_by(OrganizationInvite.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_organization_for_update(
        self, organization_id: UUID, invite_id: UUID
    ) -> OrganizationInvite | None:
        result = await self._session.execute(
            select(OrganizationInvite)
            .where(
                OrganizationInvite.id == invite_id,
                OrganizationInvite.organization_id == organization_id,
            )
            .with_for_update()
        )
        return result.scalars().first()

    async def rotate(
        self,
        invite: OrganizationInvite,
        token_hash: str,
        expires_at: datetime,
        invited_by_user_id: UUID,
    ) -> None:
        invite.token_hash = token_hash
        invite.expires_at = expires_at
        invite.invited_by_user_id = invited_by_user_id
        await self._session.flush()

    async def revoke(self, invite: OrganizationInvite, revoked_at: datetime) -> None:
        invite.revoked_at = revoked_at
        await self._session.flush()

    async def revoke_open_for_inviter(
        self,
        organization_id: UUID,
        invited_by_user_id: UUID,
        revoked_at: datetime,
    ) -> None:
        result = await self._session.execute(
            select(OrganizationInvite)
            .where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.invited_by_user_id == invited_by_user_id,
                OrganizationInvite.accepted_at.is_(None),
                OrganizationInvite.revoked_at.is_(None),
            )
            .with_for_update()
        )
        invites = result.scalars().all()
        for invite in invites:
            invite.revoked_at = revoked_at
        await self._session.flush()

    async def revoke_open_for_invitee(
        self,
        organization_id: UUID,
        invited_email: str,
        revoked_at: datetime,
    ) -> None:
        result = await self._session.execute(
            select(OrganizationInvite)
            .where(
                OrganizationInvite.organization_id == organization_id,
                func.lower(OrganizationInvite.invited_email) == invited_email.lower(),
                OrganizationInvite.accepted_at.is_(None),
                OrganizationInvite.revoked_at.is_(None),
            )
            .with_for_update()
        )
        invites = result.scalars().all()
        for invite in invites:
            invite.revoked_at = revoked_at
        await self._session.flush()

    async def mark_accepted(self, invite: OrganizationInvite) -> None:
        invite.accepted_at = datetime.utcnow()
        await self._session.flush()
