import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.metrics import (
    REQUEST_COUNT,
    REQUEST_ERRORS,
    REQUEST_LATENCY,
    route_label,
)

logger = logging.getLogger("linkhub.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request metadata to the response and request state."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_seconds = time.perf_counter() - start
            path = route_label(request.url.path, request.scope.get("route"))
            REQUEST_LATENCY.labels(request.method, path).observe(duration_seconds)
            REQUEST_COUNT.labels(request.method, path, "500").inc()
            REQUEST_ERRORS.labels(request.method, path, "500").inc()
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status_code": 500,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
            raise

        duration_seconds = time.perf_counter() - start
        path = route_label(request.url.path, request.scope.get("route"))
        status = str(response.status_code)
        REQUEST_LATENCY.labels(request.method, path).observe(duration_seconds)
        REQUEST_COUNT.labels(request.method, path, status).inc()
        if response.status_code >= 500:
            REQUEST_ERRORS.labels(request.method, path, status).inc()
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": round(duration_seconds * 1000, 2),
            },
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = f"{duration_seconds * 1000:.2f}"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply browser security headers to every application response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if request.app.state.settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
