import logging
import math
import time

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.metrics import RATE_LIMIT_EXCEEDED

settings = get_settings()
logger = logging.getLogger("linkhub.rate_limit")

TOKEN_BUCKET_SCRIPT = """
local state = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local capacity = tonumber(ARGV[2])
local refill = tonumber(ARGV[3])
local now = tonumber(ARGV[1])
local tokens = tonumber(state[1]) or capacity
local last_refill = tonumber(state[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - last_refill) * refill)
if tokens < 1 then
  redis.call('EXPIRE', KEYS[1], math.max(2, math.floor(capacity / refill) + 2))
  return {0, tokens}
end
tokens = tokens - 1
redis.call('HSET', KEYS[1], 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', KEYS[1], math.max(2, math.floor(capacity / refill) + 2))
return {1, tokens}
"""


class RedisTokenBucketRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._redis = redis.from_url(settings.redis_dsn, decode_responses=True)
        self._capacity = settings.rate_limit_capacity
        self._refill_per_second = settings.rate_limit_refill_per_second
        self._paths = {p.strip() for p in settings.rate_limit_paths.split(",") if p.strip()}
        self._prefixes = {path for path in self._paths if path.endswith("/")}

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        prefix = next(
            (candidate for candidate in self._prefixes if path.startswith(candidate)),
            None,
        )
        if not settings.rate_limit_enabled or (
            path not in self._paths and prefix is None
        ):
            return await call_next(request)
        if prefix is not None and (
            "password" not in request.query_params
            and "x-link-password" not in request.headers
        ):
            return await call_next(request)

        identifier = request.client.host if request.client else "unknown"
        bucket_path = prefix or path
        keys = [f"rl:{bucket_path}:{identifier}"]
        if prefix is not None:
            short_code = path[len(prefix) :].split("/", 1)[0]
            keys.append(f"rl:{bucket_path}:{short_code}:{identifier}")
        now = time.time()

        try:
            tokens = self._capacity
            for bucket_key in keys:
                allowed, tokens = await self._redis.eval(
                    TOKEN_BUCKET_SCRIPT,
                    1,
                    bucket_key,
                    now,
                    self._capacity,
                    self._refill_per_second,
                )
                if not allowed:
                    break
        except redis.RedisError:
            logger.exception("rate_limit_backend_unavailable")
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "rate_limit_backend_unavailable",
                        "message": "rate limiting service unavailable",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
                headers={"Retry-After": "5"},
            )
        if not allowed:
            RATE_LIMIT_EXCEEDED.labels(request.url.path).inc()
            retry_after = max(
                1,
                math.ceil((1 - float(tokens)) / self._refill_per_second),
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "rate limit exceeded",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
