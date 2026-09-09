import json
import logging
from typing import Protocol

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.metrics import CACHE_ERRORS, CACHE_HITS, CACHE_MISSES

settings = get_settings()
logger = logging.getLogger("linkhub.cache")


class URLCache(Protocol):
    async def get(self, short_code: str) -> dict | None:
        ...

    async def set(self, short_code: str, payload: dict) -> None:
        ...

    async def delete(self, short_code: str) -> None:
        ...


class RedisURLCache:
    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_dsn, decode_responses=True)
        self._ttl_seconds = settings.redis_cache_ttl_seconds

    @staticmethod
    def _key(short_code: str) -> str:
        return f"url:resolve:{short_code}"

    async def get(self, short_code: str) -> dict | None:
        if not settings.redis_cache_enabled:
            return None
        try:
            raw = await self._redis.get(self._key(short_code))
            payload = json.loads(raw) if raw is not None else None
        except (redis.RedisError, json.JSONDecodeError, TypeError):
            CACHE_ERRORS.inc()
            logger.warning("url_cache_read_failed", extra={"short_code": short_code})
            return None

        if payload is None:
            CACHE_MISSES.inc()
            return None

        if not isinstance(payload, dict):
            CACHE_ERRORS.inc()
            logger.warning("url_cache_payload_invalid", extra={"short_code": short_code})
            return None

        CACHE_HITS.inc()
        return payload

    async def set(self, short_code: str, payload: dict) -> None:
        if not settings.redis_cache_enabled:
            return
        try:
            await self._redis.set(
                self._key(short_code),
                json.dumps(payload),
                ex=self._ttl_seconds,
            )
        except redis.RedisError:
            CACHE_ERRORS.inc()
            logger.warning("url_cache_write_failed", extra={"short_code": short_code})

    async def delete(self, short_code: str) -> None:
        if not settings.redis_cache_enabled:
            return
        try:
            await self._redis.delete(self._key(short_code))
        except redis.RedisError:
            CACHE_ERRORS.inc()
            logger.warning("url_cache_delete_failed", extra={"short_code": short_code})
