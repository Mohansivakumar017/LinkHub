import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("linkhub.errors")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", request.headers.get("X-Request-ID", "-"))


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return a stable error envelope for application and authentication errors."""
    code = f"http_{exc.status_code}"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": exc.detail,
                "request_id": _request_id(request),
            }
        },
        headers=exc.headers,
    )


def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation failures without exposing internal exception details."""
    errors: list[dict[str, Any]] = [
        {
            "location": list(error.get("loc", ())),
            "message": error.get("msg", "invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "request validation failed",
                "details": errors,
                "request_id": _request_id(request),
            }
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Return a safe internal error response and log the correlated exception."""
    request_id = _request_id(request)
    logger.exception("unhandled_exception", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "an unexpected error occurred",
                "request_id": request_id,
            }
        },
    )
