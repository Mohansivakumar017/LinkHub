from fastapi.testclient import TestClient

from app.main import app
from app.presentation.api.v1.routers import auth as auth_router_module


class FakeAuthService:
    def __init__(self, session) -> None:
        self._session = session

    async def register(self, email: str, password: str, full_name: str | None = None):
        return "11111111-1111-1111-1111-111111111111"

    async def send_verification_email(self, email: str) -> None:
        return None

    async def authenticate(self, email: str, password: str):
        return type("Tokens", (), {"access_token": "access", "refresh_token": "refresh"})()

    async def refresh(self, raw_refresh_token: str):
        return type("Tokens", (), {"access_token": "new-access", "refresh_token": "new-refresh"})()

    async def logout(self, raw_refresh_token: str) -> None:
        return None

    async def verify_email(self, verification_token: str) -> None:
        return None

    async def request_password_reset(self, email: str) -> None:
        return None

    async def reset_password(self, reset_token: str, new_password: str) -> None:
        return None


async def fake_db_session():
    yield None


def test_auth_endpoints_contract(monkeypatch) -> None:
    monkeypatch.setattr(auth_router_module, "AuthService", FakeAuthService)
    app.dependency_overrides[auth_router_module.get_db_session] = fake_db_session

    client = TestClient(app)

    register_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "StrongPass123!",
            "full_name": "User",
        },
    )
    assert register_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "StrongPass123!"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["access_token"] == "access"

    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": "refresh"})
    assert refresh_res.status_code == 200
    assert refresh_res.json()["refresh_token"] == "new-refresh"

    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": "new-refresh"})
    assert logout_res.status_code == 204

    verify_res = client.post("/api/v1/auth/verify-email", json={"token": "token"})
    assert verify_res.status_code == 204

    resend_res = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "user@example.com"},
    )
    assert resend_res.status_code == 202

    forgot_res = client.post("/api/v1/auth/forgot-password", json={"email": "user@example.com"})
    assert forgot_res.status_code == 202

    reset_res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "token", "new_password": "NewStrongPass123!"},
    )
    assert reset_res.status_code == 204

    app.dependency_overrides.clear()
