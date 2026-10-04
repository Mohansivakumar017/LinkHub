from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.services.organization_service import AlreadyOrganizationMemberError
from app.main import app
from app.presentation.api.v1.routers import organizations as organizations_router_module


class FakeOrganizationService:
    def __init__(self, session) -> None:
        self._session = session

    async def create_organization(self, user_id, name: str):
        return uuid4()

    async def list_user_organizations(self, user_id):
        return [{
            "id": str(uuid4()),
            "name": "Acme",
            "slug": "acme",
            "owner_user_id": str(user_id),
            "role": "owner",
        }]

    async def invite_member(self, requester_user_id, organization_id, invited_email, role):
        return type(
            "InviteResult",
            (),
            {"invite_id": uuid4(), "invite_token": "invite-token"},
        )()

    async def list_invites(self, requester_user_id, organization_id):
        return []

    async def resend_invite(self, requester_user_id, organization_id, invite_id):
        return type(
            "InviteResult",
            (),
            {"invite_id": invite_id, "invite_token": "resent-token"},
        )()

    async def revoke_invite(self, requester_user_id, organization_id, invite_id):
        return None
    async def accept_invite(self, user_id, invite_token: str):
        return uuid4()

    async def transfer_ownership(self, requester_user_id, organization_id, new_owner_user_id):
        return None

    async def ensure_member_access(self, requester_user_id, organization_id):
        return None


class FakeAuditRepository:
    def __init__(self, session) -> None:
        self._session = session

    async def list_for_organization(
        self, organization_id, offset, limit, action=None, resource_type=None
    ):
        return [], 0


async def fake_db_session():
    yield None


async def fake_current_user():
    return type("User", (), {"id": uuid4(), "is_active": True})()


def test_organization_endpoints_contract(monkeypatch) -> None:
    monkeypatch.setattr(organizations_router_module, "OrganizationService", FakeOrganizationService)
    monkeypatch.setattr(organizations_router_module, "AuditRepository", FakeAuditRepository)
    app.dependency_overrides[organizations_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[organizations_router_module.get_current_user] = fake_current_user

    client = TestClient(app)
    create_res = client.post("/api/v1/organizations", json={"name": "Acme"})
    assert create_res.status_code == 201
    assert "id" in create_res.json()

    list_res = client.get("/api/v1/organizations")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)
    assert list_res.json()[0]["role"] == "owner"

    organization_id = str(uuid4())
    invite_res = client.post(
        f"/api/v1/organizations/{organization_id}/invites",
        json={"email": "member@example.com", "role": "member"},
    )
    assert invite_res.status_code == 200
    assert invite_res.json()["invite_token"] == "invite-token"
    assert "invite_id" in invite_res.json()

    list_invites_res = client.get(
        f"/api/v1/organizations/{organization_id}/invites"
    )
    assert list_invites_res.status_code == 200
    assert list_invites_res.json() == []

    invite_id = str(uuid4())
    resend_res = client.post(
        f"/api/v1/organizations/{organization_id}/invites/{invite_id}/resend"
    )
    assert resend_res.status_code == 200
    assert resend_res.json()["invite_token"] == "resent-token"

    revoke_res = client.delete(
        f"/api/v1/organizations/{organization_id}/invites/{invite_id}"
    )
    assert revoke_res.status_code == 204

    accept_res = client.post("/api/v1/organizations/invites/accept", json={"invite_token": "invite-token"})
    assert accept_res.status_code == 200

    transfer_res = client.post(
        f"/api/v1/organizations/{organization_id}/transfer-ownership",
        json={"new_owner_user_id": str(uuid4())},
    )
    assert transfer_res.status_code == 204

    audit_res = client.get(
        f"/api/v1/organizations/{organization_id}/audit-logs",
        params={"action": "organization.created", "resource_type": "organization"},
    )
    assert audit_res.status_code == 200
    assert audit_res.json() == {"items": [], "offset": 0, "limit": 50, "total": 0}

    app.dependency_overrides.clear()


def test_invite_existing_member_conflicts_are_returned_as_409(monkeypatch) -> None:
    class AlreadyMemberService:
        def __init__(self, session) -> None:
            self._session = session

        async def invite_member(self, **kwargs):
            raise AlreadyOrganizationMemberError(
                "user is already a member of this organization"
            )

        async def accept_invite(self, user_id, invite_token):
            raise AlreadyOrganizationMemberError(
                "user is already a member of this organization"
            )

    monkeypatch.setattr(
        organizations_router_module, "OrganizationService", AlreadyMemberService
    )
    app.dependency_overrides[organizations_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[organizations_router_module.get_current_user] = fake_current_user
    client = TestClient(app)
    try:
        organization_id = uuid4()
        invite = client.post(
            f"/api/v1/organizations/{organization_id}/invites",
            json={"email": "member@example.com", "role": "member"},
        )
        assert invite.status_code == 409

        accepted = client.post(
            "/api/v1/organizations/invites/accept",
            json={"invite_token": "invite-token"},
        )
        assert accepted.status_code == 409
    finally:
        app.dependency_overrides.clear()
