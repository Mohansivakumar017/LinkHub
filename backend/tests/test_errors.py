from fastapi.testclient import TestClient

from app.main import app


def test_validation_errors_use_stable_envelope() -> None:
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["message"] == "request validation failed"
    assert body["request_id"]
