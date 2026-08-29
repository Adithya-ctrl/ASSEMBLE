"""Auth-scoped ASGI limits, browser-origin checks and cache controls."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.auth.config import AuthSettings


AUTH_PATH_PREFIXES = ("/api/auth", "/api/communities", "/api/invitations")
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

AsgiReceive = Callable[[], Awaitable[dict[str, Any]]]
AsgiSend = Callable[[dict[str, Any]], Awaitable[None]]


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


async def _problem(send: AsgiSend, status: int, code: str, message: str) -> None:
    body = json.dumps(
        {"error": {"code": code, "message": message, "details": {}}},
        separators=(",", ":"),
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class AuthBoundaryMiddleware:
    """Apply bounded-body and browser checks without touching non-auth routes."""

    def __init__(self, app: Any, settings: AuthSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: dict[str, Any], receive: AsgiReceive, send: AsgiSend) -> None:
        if scope.get("type") != "http" or not scope.get("path", "").startswith(AUTH_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        method = str(scope.get("method", "GET")).upper()
        if method in UNSAFE_METHODS:
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                await _problem(send, 415, "UNSUPPORTED_MEDIA_TYPE", "Unsafe auth requests require application/json.")
                return

            origin = headers.get("origin")
            host = headers.get("host")
            request_origin = f"{scope.get('scheme', 'http')}://{host}" if host else None
            allowed_origins = {*self.settings.allowed_browser_origins}
            if request_origin:
                allowed_origins.add(request_origin)
            if origin is not None and origin.rstrip("/") not in allowed_origins:
                await _problem(send, 403, "BROWSER_ORIGIN_REJECTED", "The browser origin is not allowed.")
                return

            fetch_site = headers.get("sec-fetch-site")
            if fetch_site is not None and fetch_site.lower() not in {"same-origin", "none"}:
                await _problem(send, 403, "BROWSER_ORIGIN_REJECTED", "The browser request is not same-origin.")
                return

        declared_length = headers.get("content-length")
        if declared_length is not None:
            try:
                parsed_length = int(declared_length)
                if parsed_length < 0:
                    raise ValueError
                if parsed_length > self.settings.request_body_limit_bytes:
                    await _problem(send, 422, "INVALID_REQUEST", "The auth request body exceeds 16 KiB.")
                    return
            except ValueError:
                await _problem(send, 422, "INVALID_REQUEST", "Content-Length is invalid.")
                return

        buffered: list[dict[str, Any]] = []
        received_bytes = 0
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                buffered.append(message)
                break
            body = message.get("body", b"")
            received_bytes += len(body)
            if received_bytes > self.settings.request_body_limit_bytes:
                await _problem(send, 422, "INVALID_REQUEST", "The auth request body exceeds 16 KiB.")
                return
            buffered.append(message)
            if not message.get("more_body", False):
                break

        index = 0

        async def replay() -> dict[str, Any]:
            nonlocal index
            if index < len(buffered):
                message = buffered[index]
                index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        async def no_store_send(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers = [
                    item for item in response_headers if item[0].lower() != b"cache-control"
                ]
                response_headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": response_headers}
            await send(message)

        await self.app(scope, replay, no_store_send)
