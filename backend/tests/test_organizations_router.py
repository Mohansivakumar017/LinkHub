from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.presentation.api.v1.routers import organizations as organizations_router_module


class FakeOrganizationService:
    def __init__(self, session) -> None:
        self._session = session

    async def create_organization(self, user_id, name: str):
        return uuid4()

    async def list_user_organizations(self, user_id):
        return [{"id": str(uuid4()), "name": "Acme", "slug": "acme", "owner_user_id": str(user_id)}]

    async def invite_member(self, requester_user_id, organization_id, invited_email, role):
        return type("InviteResult", (), {"invite_token": "invite-token"})()

    async def accept_invite(self, user_id, invite_token: str):
        return uuid4()

    async def transfer_ownership(self, requester_user_id, organization_id, new_owner_user_id):
        return None


async def fake_db_session():
    yield None


async def fake_current_user():
    return type("User", (), {"id": uuid4(), "is_active": True})()


def test_organization_endpoints_contract(monkeypatch) -> None:
    monkeypatch.setattr(organizations_router_module, "OrganizationService", FakeOrganizationService)
    app.dependency_overrides[organizations_router_module.get_db_session] = fake_db_session
    app.dependency_overrides[organizations_router_module.get_current_user] = fake_current_user

    client = TestClient(app)
    create_res = client.post("/api/v1/organizations", json={"name": "Acme"})
    assert create_res.status_code == 201
    assert "id" in create_res.json()

    list_res = client.get("/api/v1/organizations")
    assert list_res.status_code == 200
    assert isinstance(list_res.json(), list)

    organization_id = str(uuid4())
    invite_res = client.post(
        f"/api/v1/organizations/{organization_id}/invites",
        json={"email": "member@example.com", "role": "member"},
    )
    assert invite_res.status_code == 200
    assert invite_res.json()["invite_token"] == "invite-token"

    accept_res = client.post("/api/v1/organizations/invites/accept", json={"invite_token": "invite-token"})
    assert accept_res.status_code == 200

    transfer_res = client.post(
        f"/api/v1/organizations/{organization_id}/transfer-ownership",
        json={"new_owner_user_id": str(uuid4())},
    )
    assert transfer_res.status_code == 204

    app.dependency_overrides.clear()
