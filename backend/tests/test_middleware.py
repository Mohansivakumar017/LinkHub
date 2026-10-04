import pytest
from starlette.requests import Request
from starlette.responses import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core import middleware


@pytest.mark.asyncio
async def test_request_context_ignores_untrusted_forwarded_for(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    def set_request_context(request_id: str, client_ip: str | None) -> tuple[None, None]:
        captured["request_id"] = request_id
        captured["client_ip"] = client_ip
        return None, None

    monkeypatch.setattr(middleware, "set_request_context", set_request_context)
    monkeypatch.setattr(middleware, "reset_request_context", lambda _tokens: None)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [(b"x-forwarded-for", b"203.0.113.99")],
            "client": ("172.31.240.2", 4567),
            "scheme": "http",
        }
    )
    instance = middleware.RequestContextMiddleware(lambda _scope: None)

    await instance.dispatch(request, lambda _request: _response())

    assert captured["client_ip"] == "172.31.240.2"


@pytest.mark.asyncio
async def test_trusted_frontend_proxy_resolves_the_actual_client_ip() -> None:
    forwarded_client: list[tuple[str, int] | None] = []

    async def app(scope, _receive, _send) -> None:
        forwarded_client.append(scope["client"])

    middleware = ProxyHeadersMiddleware(app, trusted_hosts="172.31.240.2")
    scope = {
        "type": "http",
        "headers": [
            (b"x-forwarded-for", b"203.0.113.99, 198.51.100.17"),
        ],
        "client": ("172.31.240.2", 4567),
    }

    await middleware(scope, None, None)

    assert forwarded_client == [("198.51.100.17", 0)]


async def _response() -> Response:
    return Response("ok")
