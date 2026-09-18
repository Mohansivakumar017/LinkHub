from contextvars import ContextVar
from typing import Any

_request_id_ctx: ContextVar[str] = ContextVar("linkhub_request_id", default="-")
_client_ip_ctx: ContextVar[str | None] = ContextVar(
    "linkhub_client_ip", default=None
)


def current_request_id() -> str:
    return _request_id_ctx.get()


def current_client_ip() -> str | None:
    return _client_ip_ctx.get()


def set_request_context(request_id: str, client_ip: str | None) -> tuple[Any, Any]:
    token_rid = _request_id_ctx.set(request_id)
    token_ip = _client_ip_ctx.set(client_ip)
    return token_rid, token_ip


def reset_request_context(tokens: tuple[Any, Any]) -> None:
    token_rid, token_ip = tokens
    _request_id_ctx.reset(token_rid)
    _client_ip_ctx.reset(token_ip)
