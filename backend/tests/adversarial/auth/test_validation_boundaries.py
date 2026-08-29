"""Adversarial request, origin and ASGI-boundary checks for auth (B2-G2).

These tests intentionally exercise the executable contract at exact edges.  They
do not call external services or persist any values other than the temporary
SQLite files created by the fixtures.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.boundary import AuthBoundaryMiddleware
from app.auth.config import AuthSettings, _parse_allowed_browser_origins
from app.auth.models import (
    CommunityCreateRequest,
    CommunityRole,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RoleChangeRequest,
    SignupRequest,
)


def _password(length: int = 12) -> str:
    """Return a valid deterministic value local to one test assertion."""

    if length < 4:
        return "a" * length
    return ("Aa1!" + ("x" * (length - 4)))[:length]


def _assert_invalid(model_type: type[Any], payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


def _boundary_client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        AuthBoundaryMiddleware,
        settings=AuthSettings(database_path=tmp_path / "auth.sqlite3"),
    )

    @app.post("/api/auth/echo")
    async def echo(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    @app.get("/api/auth/echo")
    async def get_echo() -> dict[str, str]:
        return {"method": "GET"}

    @app.post("/api/unrelated")
    async def unrelated(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    return TestClient(app)


def test_identity_and_password_ceilings_accept_exact_edges_and_reject_adjacent_values() -> None:
    username_at_minimum = SignupRequest(
        username="a1b",
        password=_password(),
    )
    assert username_at_minimum.username == "a1b"

    username_at_maximum = "a" + ("b" * 62) + "c"
    assert len(username_at_maximum) == 64
    assert SignupRequest(username=username_at_maximum, password=_password()).username == username_at_maximum

    _assert_invalid(SignupRequest, {"username": "ab", "password": _password()})
    _assert_invalid(SignupRequest, {"username": "a" * 65, "password": _password()})
    for password in (_password(11), _password(129), "a" * 12, "A" * 12, "1" * 12, "!" * 12):
        _assert_invalid(SignupRequest, {"username": "alice", "password": password})


def test_email_display_and_profile_boundaries_are_strict_without_overvalidating_allowed_metadata() -> None:
    # 254 characters is the declared email ceiling and still has a dot in the domain.
    email_at_maximum = ("a" * 64) + "@" + ("b" * 185) + ".com"
    assert len(email_at_maximum) == 254
    request = SignupRequest(username="alice", email=email_at_maximum, password=_password())
    assert request.email == email_at_maximum
    _assert_invalid(
        SignupRequest,
        {"username": "alice", "email": email_at_maximum + "x", "password": _password()},
    )

    assert SignupRequest(username=" alice ", password=_password(), display_name="  Alice  ").display_name == "Alice"
    assert len(SignupRequest(username="alice", password=_password(), display_name="x" * 120).display_name or "") == 120
    _assert_invalid(SignupRequest, {"username": "alice", "password": _password(), "display_name": " "})
    _assert_invalid(SignupRequest, {"username": "alice", "password": _password(), "display_name": "x" * 121})

    assert ProfileUpdateRequest(avatar_url="https://images.example.test/a?size=small#top").avatar_url
    for value in (
        "https://",
        "https://user:pass@images.example.test/a",
        "https://images.example.test:99999/a",
        "http://images.example.test/a",
        "javascript:alert(1)",
        "//images.example.test/a",
    ):
        _assert_invalid(ProfileUpdateRequest, {"avatar_url": value})


def test_community_invitation_and_role_models_reject_coercion_and_extra_fields() -> None:
    exact_slug = "a" + ("b" * 62) + "c"
    assert len(exact_slug) == 64
    assert CommunityCreateRequest(name="  Assembly  ", slug=exact_slug).slug == exact_slug
    _assert_invalid(CommunityCreateRequest, {"name": "x", "slug": "ab"})
    _assert_invalid(CommunityCreateRequest, {"name": "x", "slug": "-abc"})
    _assert_invalid(CommunityCreateRequest, {"name": "x", "slug": "abc-"})
    _assert_invalid(CommunityCreateRequest, {"name": " " * 5, "slug": "abc"})
    _assert_invalid(CommunityCreateRequest, {"name": "x", "slug": "abc", "unexpected": True})

    for payload in (
        {"recipient": "someone", "role": CommunityRole.MEMBER, "expires_in_seconds": "300"},
        {"recipient": "someone", "role": CommunityRole.MEMBER, "expires_in_seconds": 300.0},
        {"recipient": "someone", "role": CommunityRole.MEMBER, "expires_in_seconds": True},
        {"recipient": "someone", "role": "NOT_A_ROLE", "expires_in_seconds": 300},
        {"recipient": "someone", "role": CommunityRole.MEMBER, "expires_in_seconds": 300, "extra": 1},
    ):
        _assert_invalid(InvitationCreateRequest, payload)

    assert InvitationCreateRequest(
        recipient="someone",
        role=CommunityRole.MEMBER,
        expires_in_seconds=300,
    ).expires_in_seconds == 300
    for token in ("a" * 39, "a" * 129, "a" * 39 + "!", "a" * 40 + "/"):
        _assert_invalid(InvitationAcceptRequest, {"token": token})
    _assert_invalid(RoleChangeRequest, {"role": "MEMBER", "is_admin": True})


def test_every_auth_request_model_forbids_unknown_fields() -> None:
    cases = (
        (SignupRequest, {"username": "alice", "password": _password()}),
        (LoginRequest, {"identity": "alice", "password": _password()}),
        (
            PasswordChangeRequest,
            {"current_password": _password(), "new_password": "Bb2@" + "y" * 8},
        ),
        (ProfileUpdateRequest, {"display_name": "Alice"}),
        (CommunityCreateRequest, {"name": "Assembly", "slug": "assembly"}),
        (RoleChangeRequest, {"role": "MEMBER"}),
        (InvitationCreateRequest, {"recipient": "alice", "role": "MEMBER"}),
        (InvitationAcceptRequest, {"token": "a" * 40}),
    )
    for model_type, payload in cases:
        _assert_invalid(model_type, {**payload, "unknown_field": "rejected"})


@pytest.mark.parametrize(
    "value",
    (
        "http://LOCALHOST:3000",
        "HTTP://localhost:3000",
        "http://localhost:3000/",
        "http://localhost:3000/path",
        "http://localhost:3000?x=1",
        "http://localhost:3000#fragment",
        "http://user:pass@localhost:3000",
        "http://localhost%2f.evil:3000",
        "http://localhost:65536",
        "http://localhost:0",
        "http://local_host:3000",
        "http://localhost:3000\t",
        "http://localhost:3000\x7f",
        "https://*",
        "https://例え.test",
    ),
)
def test_origin_parser_rejects_noncanonical_and_ambiguous_values(value: str) -> None:
    with pytest.raises(ValueError, match="ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS"):
        _parse_allowed_browser_origins(value)


def test_origin_parser_accepts_bounded_canonical_ipv4_ipv6_and_deduplicates() -> None:
    assert _parse_allowed_browser_origins(
        "http://127.0.0.1:3000,https://[2001:db8::1]:443,http://127.0.0.1:3000"
    ) == ("http://127.0.0.1:3000", "https://[2001:db8::1]:443")
    origins = ",".join(f"https://app-{index}.example.test" for index in range(32))
    assert len(_parse_allowed_browser_origins(origins)) == 32
    with pytest.raises(ValueError, match="too many origins"):
        _parse_allowed_browser_origins(origins + ",https://overflow.example.test")


def test_origin_parser_uses_utf8_byte_ceiling_and_rejects_empty_segments() -> None:
    # Repeated canonical values make the environment large without relying on
    # an invalid hostname as the source of the failure.
    oversized = ",".join("https://app.example.test" for _ in range(100))
    assert len(oversized.encode("utf-8")) < 4096
    oversized = oversized + "," + ("https://app.example.test" * 200)
    with pytest.raises(ValueError, match="bounded|too many"):
        _parse_allowed_browser_origins(oversized)
    for value in ("http://localhost:3000,,https://app.example.test", ",http://localhost:3000"):
        with pytest.raises(ValueError, match="invalid origin"):
            _parse_allowed_browser_origins(value)


def test_browser_metadata_is_exact_and_duplicate_origin_values_do_not_smuggle_an_allowlisted_value(
    tmp_path: Path,
) -> None:
    client = _boundary_client(tmp_path)
    assert client.post(
        "/api/auth/echo",
        json={"ok": True},
        headers={"Origin": "http://localhost:3000", "Sec-Fetch-Site": "SAME-ORIGIN"},
    ).status_code == 200
    assert client.post(
        "/api/auth/echo",
        json={"ok": True},
        headers={"Origin": "http://localhost:3000", "Sec-Fetch-Site": "none"},
    ).status_code == 200
    for fetch_site in ("same-origin ", "cross-site", "same-site", "SAME_ORIGIN"):
        response = client.post(
            "/api/auth/echo",
            json={"ok": True},
            headers={"Origin": "http://localhost:3000", "Sec-Fetch-Site": fetch_site},
        )
        assert response.status_code == 403

    # Two Origin fields are not one exact origin.  The boundary must not let a
    # proxy/header parser choose whichever value happens to be last.
    duplicate = client.post(
        "/api/auth/echo",
        content=b"{}",
        headers=[
            ("Content-Type", "application/json"),
            ("Origin", "https://evil.example"),
            ("Origin", "http://localhost:3000"),
        ],
    )
    assert duplicate.status_code == 403
    assert duplicate.json()["error"]["code"] == "BROWSER_ORIGIN_REJECTED"


def test_actual_body_limit_accepts_exact_bytes_and_rejects_dishonest_lengths(tmp_path: Path) -> None:
    client = _boundary_client(tmp_path)
    prefix = b'{"payload":"'
    suffix = b'"}'
    body = prefix + (b"x" * (16 * 1024 - len(prefix) - len(suffix))) + suffix
    assert len(body) == 16 * 1024
    exact = client.post(
        "/api/auth/echo",
        content=body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    assert exact.status_code == 200
    assert len(exact.json()["payload"]) == 16 * 1024 - len(prefix) - len(suffix)

    def over_limit() -> Any:
        yield b'{"payload":"'
        yield b"x" * (16 * 1024)
        yield b'"}'

    streamed = client.post(
        "/api/auth/echo",
        content=over_limit(),
        headers={"Content-Type": "application/json", "Content-Length": "1"},
    )
    assert streamed.status_code == 422
    assert streamed.json()["error"]["code"] == "INVALID_REQUEST"

    for declared in ("-1", "not-a-number", "1.5"):
        response = client.post(
            "/api/auth/echo",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": declared},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_body_content_type_is_media_type_exactly_and_scope_is_preserved(tmp_path: Path) -> None:
    client = _boundary_client(tmp_path)
    for content_type in ("application/json; charset=utf-8", "APPLICATION/JSON"):
        assert client.post(
            "/api/auth/echo",
            content=b"{}",
            headers={"Content-Type": content_type},
        ).status_code == 200
    for content_type in ("text/plain", "application/json-patch+json", "", "application/x-www-form-urlencoded"):
        response = client.post(
            "/api/auth/echo",
            content=b"{}",
            headers={"Content-Type": content_type},
        )
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    # The same bytes are unrestricted on a non-auth route.
    assert client.post("/api/unrelated", content=b"{}", headers={"Content-Type": "text/plain"}).status_code == 422


def test_auth_boundary_never_reads_or_rewrites_non_http_scopes() -> None:
    seen: list[dict[str, Any]] = []

    async def downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
        seen.append(scope)

    middleware = AuthBoundaryMiddleware(
        downstream,
        AuthSettings(database_path=Path("/tmp/unused-auth-boundary.sqlite3")),
    )

    async def run() -> None:
        await middleware({"type": "lifespan", "path": "/api/auth"}, lambda: None, lambda _: None)

    asyncio.run(run())
    assert seen and seen[0]["type"] == "lifespan"


def test_auth_validation_error_body_is_stable_and_does_not_echo_password(tmp_path: Path) -> None:
    # This uses the real focused app only for HTTP envelope shape; the value is
    # local to this request and is never written to the temporary database.
    from app.auth.api import create_auth_app

    app = create_auth_app(AuthSettings(database_path=tmp_path / "auth.sqlite3"))
    client = TestClient(app)
    password = "TransientAa1!"
    response = client.post(
        "/api/auth/login",
        content=json.dumps({"identity": "alice", "password": password, "extra": "reject"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert password not in response.text
    assert response.headers["cache-control"] == "no-store"
