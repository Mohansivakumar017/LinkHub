import logging
import time

import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings

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

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.rate_limit_enabled or request.url.path not in self._paths:
            return await call_next(request)

        identifier = request.client.host if request.client else "unknown"
        bucket_key = f"rl:{request.url.path}:{identifier}"
        now = time.time()

        try:
            allowed, _tokens = await self._redis.eval(
                TOKEN_BUCKET_SCRIPT,
                1,
                bucket_key,
                now,
                self._capacity,
                self._refill_per_second,
            )
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
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "rate limit exceeded",
                        "request_id": getattr(request.state, "request_id", "-"),
                    }
                },
                headers={"Retry-After": "1"},
            )

        return await call_next(request)
