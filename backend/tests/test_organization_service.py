from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.organization_service import (
    AlreadyOrganizationMemberError,
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
        return [(org, OrganizationRole.OWNER) for org in self.orgs.values()]

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

    async def get_membership_for_update(self, organization_id, user_id):
        return await self.get_membership(organization_id, user_id)

    async def list_members(self, organization_id):
        return [
            membership
            for membership in self.memberships
            if membership.organization_id == organization_id
        ]

    async def update_role(self, membership, role):
        membership.role = role

    async def remove_member(self, membership):
        self.memberships.remove(membership)


class FakeApiKeyRepo:
    def __init__(self) -> None:
        self.revoked_for: list[tuple] = []

    async def revoke_for_user_in_organization(self, user_id, organization_id):
        self.revoked_for.append((user_id, organization_id))


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
            revoked_at=None,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.invites[token_hash] = invite
        return invite

    async def get_by_token_hash(self, token_hash):
        return self.invites.get(token_hash)

    async def list_open_for_organization(self, organization_id):
        return [
            invite
            for invite in self.invites.values()
            if invite.organization_id == organization_id
            and invite.accepted_at is None
            and invite.revoked_at is None
        ]

    async def get_for_organization_for_update(self, organization_id, invite_id):
        return next(
            (
                invite
                for invite in self.invites.values()
                if invite.organization_id == organization_id and invite.id == invite_id
            ),
            None,
        )

    async def rotate(self, invite, token_hash, expires_at, invited_by_user_id):
        self.invites.pop(invite.token_hash)
        invite.token_hash = token_hash
        invite.expires_at = expires_at
        invite.invited_by_user_id = invited_by_user_id
        self.invites[token_hash] = invite

    async def revoke(self, invite, revoked_at):
        invite.revoked_at = revoked_at

    async def revoke_open_for_inviter(
        self, organization_id, invited_by_user_id, revoked_at
    ):
        for invite in self.invites.values():
            if (
                invite.organization_id == organization_id
                and invite.invited_by_user_id == invited_by_user_id
                and invite.accepted_at is None
                and invite.revoked_at is None
            ):
                invite.revoked_at = revoked_at

    async def revoke_open_for_invitee(
        self, organization_id, invited_email, revoked_at
    ):
        for invite in self.invites.values():
            if (
                invite.organization_id == organization_id
                and invite.invited_email.lower() == invited_email.lower()
                and invite.accepted_at is None
                and invite.revoked_at is None
            ):
                invite.revoked_at = revoked_at

    async def mark_accepted(self, invite):
        invite.accepted_at = datetime.now(UTC).replace(tzinfo=None)


class FakeUserRepo:
    def __init__(self) -> None:
        self.users_by_id: dict = {}
        self.list_by_ids_calls: list[list] = []

    async def get_by_id(self, user_id):
        return self.users_by_id.get(user_id)

    async def get_by_id_for_update(self, user_id):
        return await self.get_by_id(user_id)

    async def get_by_email_case_insensitive(self, email):
        return next(
            (
                user
                for user in self.users_by_id.values()
                if user.email.lower() == email.lower()
            ),
            None,
        )

    async def list_by_ids(self, user_ids):
        self.list_by_ids_calls.append(user_ids)
        return [
            self.users_by_id[user_id]
            for user_id in user_ids
            if user_id in self.users_by_id
        ]


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
    listed_orgs = await service.list_user_organizations(owner_id)
    assert listed_orgs[0]["role"] == OrganizationRole.OWNER.value

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
async def test_invite_rejects_existing_member_and_accept_race_is_not_silent() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=FakeEmailSender(),
        api_key_repo=FakeApiKeyRepo(),
    )
    owner_id = uuid4()
    member_id = uuid4()
    organization_id = await service.create_organization(owner_id, "No duplicate invite")
    user_repo.users_by_id[member_id] = SimpleNamespace(
        id=member_id, email="member@example.com"
    )
    await member_repo.add_member(organization_id, member_id, OrganizationRole.MEMBER)

    with pytest.raises(AlreadyOrganizationMemberError):
        await service.invite_member(
            owner_id,
            organization_id,
            "MEMBER@example.com",
            OrganizationRole.ADMIN,
        )

    await member_repo.remove_member(
        await member_repo.get_membership(organization_id, member_id)
    )
    invite = await service.invite_member(
        owner_id,
        organization_id,
        "member@example.com",
        OrganizationRole.ADMIN,
    )
    await member_repo.add_member(organization_id, member_id, OrganizationRole.MEMBER)

    with pytest.raises(AlreadyOrganizationMemberError):
        await service.accept_invite(member_id, invite.invite_token)
    stored_invite = next(
        item for item in invite_repo.invites.values() if item.id == invite.invite_id
    )
    assert stored_invite.accepted_at is None


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


@pytest.mark.asyncio
async def test_admin_cannot_invite_another_admin() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=FakeInviteRepo(),
        user_repo=FakeUserRepo(),
        email_sender=FakeEmailSender(),
    )
    owner_id = uuid4()
    admin_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Invite Policy")
    await member_repo.add_member(organization_id, admin_id, OrganizationRole.ADMIN)

    with pytest.raises(PermissionDeniedError, match="admins can only invite members"):
        await service.invite_member(
            requester_user_id=admin_id,
            organization_id=organization_id,
            invited_email="new-admin@example.com",
            role=OrganizationRole.ADMIN,
        )

    owner_invite = await service.invite_member(
        requester_user_id=owner_id,
        organization_id=organization_id,
        invited_email="new-admin@example.com",
        role=OrganizationRole.ADMIN,
    )
    assert owner_invite.invite_token


@pytest.mark.asyncio
async def test_invite_can_be_listed_resent_and_revoked() -> None:
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
    organization_id = await service.create_organization(owner_id, "Invitation lifecycle")
    user_repo.users_by_id[member_id] = SimpleNamespace(
        id=member_id, email="invited@example.com"
    )

    created = await service.invite_member(
        owner_id,
        organization_id,
        "invited@example.com",
        OrganizationRole.MEMBER,
    )
    pending = await service.list_invites(owner_id, organization_id)
    assert len(pending) == 1
    assert pending[0].id == created.invite_id
    assert pending[0].invited_email == "invited@example.com"
    assert pending[0].role == OrganizationRole.MEMBER
    assert not pending[0].is_expired

    resent = await service.resend_invite(owner_id, organization_id, created.invite_id)
    assert resent.invite_id == created.invite_id
    assert resent.invite_token != created.invite_token
    with pytest.raises(InvalidInviteError):
        await service.accept_invite(member_id, created.invite_token)
    assert await service.accept_invite(member_id, resent.invite_token) == organization_id
    assert await service.list_invites(owner_id, organization_id) == []

    revoked_user_id = uuid4()
    revoked_email = "revoked-invite@example.com"
    user_repo.users_by_id[revoked_user_id] = SimpleNamespace(
        id=revoked_user_id, email=revoked_email
    )
    another = await service.invite_member(
        owner_id,
        organization_id,
        revoked_email,
        OrganizationRole.MEMBER,
    )
    await service.revoke_invite(owner_id, organization_id, another.invite_id)
    assert await service.list_invites(owner_id, organization_id) == []
    with pytest.raises(InvalidInviteError):
        await service.accept_invite(revoked_user_id, another.invite_token)


@pytest.mark.asyncio
async def test_invitation_delivery_failure_keeps_invite_manageable() -> None:
    class FailedEmailSender:
        async def send(self, _message):
            raise OSError("mail service unavailable")

    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=FakeUserRepo(),
        email_sender=FailedEmailSender(),
    )
    owner_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Delivery failure")

    with pytest.raises(OSError, match="mail service unavailable"):
        await service.invite_member(
            owner_id,
            organization_id,
            "pending@example.com",
            OrganizationRole.MEMBER,
        )

    assert session.commit_count == 2
    assert len(await service.list_invites(owner_id, organization_id)) == 1


@pytest.mark.asyncio
async def test_member_cannot_manage_invites_and_admin_cannot_revoke_admin_invite() -> None:
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    service = OrganizationService(
        session=FakeSession(),
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=FakeInviteRepo(),
        user_repo=FakeUserRepo(),
        email_sender=FakeEmailSender(),
    )
    owner_id = uuid4()
    admin_id = uuid4()
    member_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Invite permissions")
    await member_repo.add_member(organization_id, admin_id, OrganizationRole.ADMIN)
    await member_repo.add_member(organization_id, member_id, OrganizationRole.MEMBER)
    admin_invite = await service.invite_member(
        owner_id,
        organization_id,
        "new-admin@example.com",
        OrganizationRole.ADMIN,
    )
    member_invite = await service.invite_member(
        owner_id,
        organization_id,
        "new-member@example.com",
        OrganizationRole.MEMBER,
    )

    with pytest.raises(PermissionDeniedError, match="insufficient privileges"):
        await service.list_invites(member_id, organization_id)
    admin_visible_invites = await service.list_invites(admin_id, organization_id)
    assert [invite.id for invite in admin_visible_invites] == [member_invite.invite_id]
    with pytest.raises(PermissionDeniedError, match="admins can only manage"):
        await service.revoke_invite(admin_id, organization_id, admin_invite.invite_id)


@pytest.mark.asyncio
async def test_removing_member_revokes_org_keys_and_pending_invites_they_issued() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    api_key_repo = FakeApiKeyRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=FakeEmailSender(),
        api_key_repo=api_key_repo,
    )
    owner_id = uuid4()
    member_id = uuid4()
    invitee_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Key revocation")
    user_repo.users_by_id[member_id] = SimpleNamespace(
        id=member_id, email="removed-admin@example.com"
    )
    await member_repo.add_member(
        organization_id, member_id, OrganizationRole.ADMIN
    )
    user_repo.users_by_id[invitee_id] = SimpleNamespace(
        id=invitee_id, email="invited@example.com"
    )
    invite = await service.invite_member(
        member_id,
        organization_id,
        "invited@example.com",
        OrganizationRole.MEMBER,
    )

    await service.remove_member(owner_id, organization_id, member_id)

    assert api_key_repo.revoked_for == [(member_id, organization_id)]
    assert await member_repo.get_membership(organization_id, member_id) is None
    with pytest.raises(InvalidInviteError, match="invalid or expired"):
        await service.accept_invite(invitee_id, invite.invite_token)


@pytest.mark.asyncio
async def test_removing_invitee_revokes_their_existing_admin_invitation() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    invite_repo = FakeInviteRepo()
    user_repo = FakeUserRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        invite_repo=invite_repo,
        user_repo=user_repo,
        email_sender=FakeEmailSender(),
        api_key_repo=FakeApiKeyRepo(),
    )
    owner_id = uuid4()
    invitee_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Invite revocation")
    invitee = SimpleNamespace(id=invitee_id, email="user@example.com")
    user_repo.users_by_id[invitee_id] = invitee
    invite = await service.invite_member(
        owner_id,
        organization_id,
        "USER@example.com",
        OrganizationRole.ADMIN,
    )
    member_invite = await service.invite_member(
        owner_id,
        organization_id,
        "user@example.com",
        OrganizationRole.MEMBER,
    )
    await service.accept_invite(invitee_id, member_invite.invite_token)

    await service.remove_member(owner_id, organization_id, invitee_id)

    with pytest.raises(InvalidInviteError, match="invalid or expired"):
        await service.accept_invite(invitee_id, invite.invite_token)
    stored_invite = next(
        item for item in invite_repo.invites.values() if item.id == invite.invite_id
    )
    assert stored_invite.revoked_at is not None


@pytest.mark.asyncio
async def test_member_removal_lookup_locks_the_membership_row() -> None:
    from sqlalchemy.dialects import postgresql

    from app.infrastructure.repositories.organization_repository import (
        OrganizationMemberRepository,
    )

    class Result:
        def scalars(self):
            return self

        def first(self):
            return None

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    await OrganizationMemberRepository(session).get_membership_for_update(
        uuid4(), uuid4()
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    assert "FOR UPDATE" in str(compiled)


@pytest.mark.asyncio
async def test_list_members_fetches_users_in_one_batch_and_preserves_membership_order() -> None:
    session = FakeSession()
    org_repo = FakeOrganizationRepo()
    member_repo = FakeMemberRepo()
    user_repo = FakeUserRepo()
    service = OrganizationService(
        session,
        org_repo=org_repo,
        member_repo=member_repo,
        user_repo=user_repo,
    )
    owner_id = uuid4()
    member_id = uuid4()
    missing_user_id = uuid4()
    organization_id = await service.create_organization(owner_id, "Batch Team")
    await member_repo.add_member(organization_id, member_id, OrganizationRole.MEMBER)
    await member_repo.add_member(
        organization_id, missing_user_id, OrganizationRole.MEMBER
    )
    user_repo.users_by_id[owner_id] = SimpleNamespace(
        id=owner_id, email="owner@example.com", full_name="Owner"
    )
    user_repo.users_by_id[member_id] = SimpleNamespace(
        id=member_id, email="member@example.com", full_name=None
    )

    members = await service.list_members(owner_id, organization_id)

    assert [member["user_id"] for member in members] == [
        str(owner_id),
        str(member_id),
    ]
    assert members[1]["full_name"] == ""
    assert user_repo.list_by_ids_calls == [[owner_id, member_id, missing_user_id]]
