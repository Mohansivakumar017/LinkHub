import pytest
import redis.asyncio as redis
from starlette.requests import Request
from starlette.responses import Response

from app.core.rate_limit import middleware as rate_limit_module


def _request(path: str = "/api/v1/auth/login", query_string: bytes = b"") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "query_string": query_string,
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
async def test_rate_limit_retry_after_reflects_token_refill_time(monkeypatch) -> None:
    class Redis:
        async def eval(self, *args):
            return [0, 0]

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_paths", "/api/v1/auth/login")
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_refill_per_second", 0.25)
    limiter = rate_limit_module.RedisTokenBucketRateLimitMiddleware(lambda scope: None)
    limiter._redis = Redis()

    response = await limiter.dispatch(_request(), lambda request: Response("ok"))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "4"


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


@pytest.mark.asyncio
async def test_password_link_attempts_are_rate_limited_by_ip_across_link_codes(
    monkeypatch,
) -> None:
    keys = []

    class Redis:
        async def eval(self, _script, _keys_count, key, *_args):
            keys.append(key)
            return [0, 0]

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        rate_limit_module.settings,
        "rate_limit_paths",
        "/api/v1/urls/resolve/,/api/v1/urls/r/",
    )
    limiter = rate_limit_module.RedisTokenBucketRateLimitMiddleware(lambda scope: None)
    limiter._redis = Redis()

    first = await limiter.dispatch(
        _request("/api/v1/urls/resolve/link-one", b"password=guess"),
        lambda request: Response("ok"),
    )
    second = await limiter.dispatch(
        _request("/api/v1/urls/resolve/link-two", b"password=guess"),
        lambda request: Response("ok"),
    )

    assert first.status_code == second.status_code == 429
    assert keys == ["rl:/api/v1/urls/resolve/:127.0.0.1"] * 2


@pytest.mark.asyncio
async def test_public_link_open_without_password_is_not_throttled_as_password_attempt(
    monkeypatch,
) -> None:
    class Redis:
        async def eval(self, *_args):
            raise AssertionError("Redis should not be called")

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        rate_limit_module.settings, "rate_limit_paths", "/api/v1/urls/resolve/"
    )
    limiter = rate_limit_module.RedisTokenBucketRateLimitMiddleware(lambda scope: None)
    limiter._redis = Redis()

    async def call_next(_request):
        return Response("ok")

    response = await limiter.dispatch(
        _request("/api/v1/urls/resolve/public-link"),
        call_next,
    )

    assert response.status_code == 200
