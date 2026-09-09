import asyncio

import redis.asyncio as redis
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.infrastructure.db.session import AsyncSessionLocal

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


async def _check_database() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))


async def _check_redis() -> None:
    client = redis.from_url(get_settings().redis_dsn)
    try:
        await client.ping()
    finally:
        await client.close()


@router.get("/ready", summary="Readiness check")
async def readiness_check() -> JSONResponse:
    checks: dict[str, str] = {}
    timeout = get_settings().readiness_timeout_seconds
    for name, check in (("database", _check_database), ("redis", _check_redis)):
        try:
            await asyncio.wait_for(check(), timeout=timeout)
            checks[name] = "ok"
        except (
            OSError,
            RuntimeError,
            SQLAlchemyError,
            TimeoutError,
            redis.RedisError,
        ):
            checks[name] = "unavailable"

    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )
