from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.organization_service import (
    DuplicateOrganizationSlugError,
    InvalidInviteError,
    OrganizationService,
    PermissionDeniedError,
)
from app.infrastructure.db.models.organization import OrganizationRole


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class FakeOrganizationRepo:
    def __init__(self) -> None:
        self.orgs: dict = {}

    async def create(self, name: str, slug: str, owner_user_id):
        org = SimpleNamespace(id=uuid4(), name=name, slug=slug, owner_user_id=owner_user_id)
        self.orgs[org.id] = org
        return org

    async def get_by_id(self, organization_id):
        return self.orgs.get(organization_id)

    async def get_by_slug(self, slug: str):
        for org in self.orgs.values():
            if org.slug == slug:
                return org
        return None

    async def list_for_user(self, user_id):
        return list(self.orgs.values())

    async def transfer_ownership(self, organization, new_owner_user_id):
        organization.owner_user_id = new_owner_user_id


class FakeMemberRepo:
    def __init__(self) -> None:
        self.memberships: list[SimpleNamespace] = []

    async def add_member(self, organization_id, user_id, role):
        membership = SimpleNamespace(
            id=uuid4(), organization_id=organization_id, user_id=user_id, role=role
        )
        self.memberships.append(membership)
        return membership

    async def get_membership(self, organization_id, user_id):
        for membership in self.memberships:
            if membership.organization_id == organization_id and membership.user_id == user_id:
                return membership
        return None

    async def update_role(self, membership, role):
        membership.role = role


class FakeInviteRepo:
    def __init__(self) -> None:
        self.invites: dict[str, SimpleNamespace] = {}

    async def create_invite(
        self,
        organization_id,
        invited_email,
        role,
        invited_by_user_id,
        token_hash,
        expires_at,
    ):
        invite = SimpleNamespace(
            id=uuid4(),
            organization_id=organization_id,
            invited_email=invited_email,
            role=role,
            invited_by_user_id=invited_by_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            accepted_at=None,
        )
        self.invites[token_hash] = invite
        return invite

    async def get_by_token_hash(self, token_hash):
        return self.invites.get(token_hash)

    async def mark_accepted(self, invite):
        invite.accepted_at = datetime.now(UTC).replace(tzinfo=None)


class FakeUserRepo:
    def __init__(self) -> None:
        self.users_by_id: dict = {}

    async def get_by_id(self, user_id):
        return self.users_by_id.get(user_id)


class FakeEmailSender:
    def __init__(self) -> None:
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


@pytest.mark.asyncio
async def test_create_org_and_duplicate_slug() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    email_sender = FakeEmailSender()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=email_sender,
    )
    owner_id = uuid4()

    org_id = await service.create_organization(owner_id, "My Team")
    assert org_id is not None
    assert len(member_repo.memberships) == 1
    assert member_repo.memberships[0].role == OrganizationRole.OWNER

    with pytest.raises(DuplicateOrganizationSlugError):
        await service.create_organization(owner_id, "My Team")


@pytest.mark.asyncio
async def test_invite_accept_and_transfer_ownership() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    email_sender = FakeEmailSender()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=email_sender,
    )

    owner_id = uuid4()
    member_id = uuid4()
    org_id = await service.create_organization(owner_id, "Acme")
    org = await org_repo.get_by_id(org_id)
    assert org is not None

    user_repo.users_by_id[member_id] = SimpleNamespace(id=member_id, email="member@example.com")

    invite_result = await service.invite_member(
        requester_user_id=owner_id,
        organization_id=org_id,
        invited_email="member@example.com",
        role=OrganizationRole.MEMBER,
    )
    assert invite_result.invite_token
    assert len(email_sender.messages) == 1

    accepted_org_id = await service.accept_invite(member_id, invite_result.invite_token)
    assert accepted_org_id == org_id

    await service.transfer_ownership(owner_id, org_id, member_id)
    assert org.owner_user_id == member_id


@pytest.mark.asyncio
async def test_invite_permission_and_invalid_accept() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    email_sender = FakeEmailSender()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=email_sender,
    )
    owner_id = uuid4()
    outsider_id = uuid4()
    await service.create_organization(owner_id, "Org")
    org_id = next(iter(org_repo.orgs.keys()))

    with pytest.raises(PermissionDeniedError):
        await service.invite_member(
            requester_user_id=outsider_id,
            organization_id=org_id,
            invited_email="x@example.com",
            role=OrganizationRole.MEMBER,
        )

    with pytest.raises(InvalidInviteError):
        await service.accept_invite(owner_id, "invalid-invite-token")
