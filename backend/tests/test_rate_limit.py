import pytest
import redis.asyncio as redis
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limit import middleware as rate_limit_module


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_rate_limit_exceeded_uses_standard_error_envelope(monkeypatch) -> None:
    class Redis:
        async def eval(self, *args):
            return [0, 0]

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_paths", "/api/v1/auth/login")
    limiter = rate_limit_module.RedisTokenBucketRateLimitMiddleware(lambda scope: None)
    limiter._redis = Redis()

    response = await limiter.dispatch(_request(), lambda request: Response("ok"))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert response.body == (
        b'{"error":{"code":"rate_limit_exceeded","message":"rate limit exceeded","request_id":"-"}}'
    )


@pytest.mark.asyncio
async def test_rate_limit_backend_failure_is_explicit(monkeypatch) -> None:
    class Redis:
        async def eval(self, *args):
            raise redis.RedisError("unavailable")

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_paths", "/api/v1/auth/login")
    limiter = rate_limit_module.RedisTokenBucketRateLimitMiddleware(lambda scope: None)
    limiter._redis = Redis()

    response = await limiter.dispatch(_request(), lambda request: Response("ok"))

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert b"rate_limit_backend_unavailable" in response.body
