import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.api.v1.routers import health


def test_health_check() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.asyncio
async def test_readiness_check_reports_healthy_dependencies(monkeypatch) -> None:
    async def healthy_check() -> None:
        return None

    monkeypatch.setattr(health, "_check_database", healthy_check)
    monkeypatch.setattr(health, "_check_redis", healthy_check)

    response = await health.readiness_check()

    assert response.status_code == 200
    assert response.body == (
        b'{"status":"ready","checks":{"database":"ok","redis":"ok"}}'
    )


@pytest.mark.asyncio
async def test_readiness_check_returns_service_unavailable(monkeypatch) -> None:
    async def failing_check() -> None:
        raise RuntimeError("dependency unavailable")

    monkeypatch.setattr(health, "_check_database", failing_check)
    monkeypatch.setattr(health, "_check_redis", failing_check)

    response = await health.readiness_check()

    assert response.status_code == 503
    assert response.body == (
        b'{"status":"not_ready","checks":{"database":"unavailable","redis":"unavailable"}}'
    )
