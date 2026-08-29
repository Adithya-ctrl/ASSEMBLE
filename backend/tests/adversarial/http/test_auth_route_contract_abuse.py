"""HTTP contract abuse matrix for every identity/community/invitation route.

This complements the non-auth Set P matrix.  It deliberately tests the
installed HTTP boundary rather than calling the auth service directly.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.api import create_auth_app
from app.auth.config import AuthSettings


COMMUNITY_ID = "1" * 32
USER_ID = "2" * 32
INVITATION_ID = "3" * 32


@dataclass
class Clock:
    value: int = 2_400_000_000

    def __call__(self) -> int:
        return self.value


def _app(tmp_path: Path) -> FastAPI:
    sequence = itertools.count()

    def token_factory() -> str:
        return f"gauntlet-http-token-{next(sequence):064d}"

    return create_auth_app(
        AuthSettings(database_path=tmp_path / "auth.sqlite3"),
        clock=Clock(),
        token_factory=token_factory,
    )


def _client(tmp_path: Path) -> TestClient:
    return TestClient(_app(tmp_path))


ROUTES = (
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/auth/session"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/password"),
    ("PATCH", "/api/auth/profile"),
    ("POST", "/api/communities"),
    ("GET", "/api/communities"),
    ("GET", "/api/communities/{community_id}/members"),
    ("PATCH", "/api/communities/{community_id}/members/{user_id}"),
    ("POST", "/api/communities/{community_id}/invitations"),
    ("GET", "/api/communities/{community_id}/invitations"),
    ("POST", "/api/communities/{community_id}/invitations/{invitation_id}/revoke"),
    ("POST", "/api/invitations/accept"),
    ("GET", "/api/communities/{community_id}/audit-events"),
)

WRONG_METHOD_CASES = tuple(
    (wrong_method, path)
    for path in dict.fromkeys(path for _, path in ROUTES)
    for wrong_method in ("GET", "POST", "PATCH", "PUT", "DELETE")
    if wrong_method not in {method for method, route_path in ROUTES if route_path == path}
)


def _concrete(path: str) -> str:
    return path.format(
        community_id=COMMUNITY_ID,
        user_id=USER_ID,
        invitation_id=INVITATION_ID,
    )


def _error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]
    assert isinstance(response.json()["error"]["details"], dict)
    assert response.headers["cache-control"] == "no-store"


def test_exact_auth_community_invitation_route_inventory(tmp_path: Path) -> None:
    app = _app(tmp_path)
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/api/")
        for method in operations
    }
    assert actual == set(ROUTES)


@pytest.mark.parametrize(("wrong_method", "path"), WRONG_METHOD_CASES)
def test_every_route_rejects_wrong_methods_with_framework_405(
    tmp_path: Path,
    path: str,
    wrong_method: str,
) -> None:
    response = _client(tmp_path).request(wrong_method, _concrete(path), json={})
    assert response.status_code == 405, response.text
    assert response.json() == {"detail": "Method Not Allowed"}
    assert response.headers["cache-control"] == "no-store"


PROTECTED_REQUESTS = (
    ("GET", "/api/auth/session", None),
    (
        "POST",
        "/api/auth/password",
        {"current_password": "ValidPassword1!", "new_password": "NewPassword2@"},
    ),
    ("PATCH", "/api/auth/profile", {"display_name": "Alice"}),
    ("POST", "/api/communities", {"name": "Assembly", "slug": "assembly"}),
    ("GET", "/api/communities", None),
    ("GET", f"/api/communities/{COMMUNITY_ID}/members", None),
    (
        "PATCH",
        f"/api/communities/{COMMUNITY_ID}/members/{USER_ID}",
        {"role": "MEMBER"},
    ),
    (
        "POST",
        f"/api/communities/{COMMUNITY_ID}/invitations",
        {"recipient": "recipient", "role": "MEMBER"},
    ),
    ("GET", f"/api/communities/{COMMUNITY_ID}/invitations", None),
    (
        "POST",
        f"/api/communities/{COMMUNITY_ID}/invitations/{INVITATION_ID}/revoke",
        {},
    ),
    ("POST", "/api/invitations/accept", {"token": "a" * 40}),
    ("GET", f"/api/communities/{COMMUNITY_ID}/audit-events", None),
)


@pytest.mark.parametrize(("method", "path", "payload"), PROTECTED_REQUESTS)
def test_every_protected_route_has_a_stable_unauthenticated_boundary(
    tmp_path: Path,
    method: str,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    response = _client(tmp_path).request(method, path, json=payload)
    _error(response, 401, "AUTHENTICATION_REQUIRED")


def test_logout_without_a_session_is_idempotent_no_store_and_clears_cookie(
    tmp_path: Path,
) -> None:
    response = _client(tmp_path).post("/api/auth/logout", json={})
    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert "assemble_session=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie


@pytest.mark.parametrize(
    ("method", "path"),
    (
        ("GET", "/api/communities/not-valid/members"),
        ("PATCH", f"/api/communities/{COMMUNITY_ID}/members/not-valid"),
        ("GET", "/api/communities/not-valid/invitations"),
        ("POST", f"/api/communities/{COMMUNITY_ID}/invitations/not-valid/revoke"),
        ("GET", "/api/communities/not-valid/audit-events"),
    ),
)
def test_path_identifier_validation_uses_the_stable_auth_envelope(
    tmp_path: Path,
    method: str,
    path: str,
) -> None:
    client = _client(tmp_path)
    signup = client.post(
        "/api/auth/signup",
        json={"username": "owner", "password": "ValidPassword1!"},
    )
    assert signup.status_code == 201
    payload = {"role": "MEMBER"} if method == "PATCH" else {} if method == "POST" else None
    response = client.request(method, path, json=payload)
    _error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize(
    ("path", "payload"),
    (
        (
            "/api/auth/login",
            {"identity": "alice", "password": "ValidPassword1!"},
        ),
        ("/api/communities", {"name": "Assembly", "slug": "assembly"}),
        ("/api/invitations/accept", {"token": "a" * 40}),
    ),
)
@pytest.mark.parametrize(
    ("headers", "status", "code"),
    (
        (
            [("Content-Type", "application/json"), ("Origin", "https://evil.example"), ("Origin", "http://localhost:3000")],
            403,
            "BROWSER_ORIGIN_REJECTED",
        ),
        (
            [("Content-Type", "application/json"), ("Origin", "http://localhost:3000"), ("Origin", "https://evil.example")],
            403,
            "BROWSER_ORIGIN_REJECTED",
        ),
        (
            [("Content-Type", "application/json"), ("Sec-Fetch-Site", "same-origin"), ("Sec-Fetch-Site", "cross-site")],
            403,
            "BROWSER_ORIGIN_REJECTED",
        ),
        (
            [("Content-Type", "application/json"), ("Sec-Fetch-Site", "cross-site"), ("Sec-Fetch-Site", "same-origin")],
            403,
            "BROWSER_ORIGIN_REJECTED",
        ),
        (
            [("Content-Type", "application/json"), ("Content-Type", "text/plain")],
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        (
            [("Content-Type", "text/plain"), ("Content-Type", "application/json")],
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        ),
        (
            [("Content-Type", "application/json"), ("Content-Length", "2"), ("Content-Length", "3")],
            422,
            "INVALID_REQUEST",
        ),
        (
            [("Content-Type", "application/json"), ("Content-Length", "3"), ("Content-Length", "2")],
            422,
            "INVALID_REQUEST",
        ),
    ),
)
def test_duplicate_security_headers_fail_before_dispatch_in_every_auth_namespace(
    tmp_path: Path,
    path: str,
    payload: dict[str, object],
    headers: list[tuple[str, str]],
    status: int,
    code: str,
) -> None:
    del payload
    response = _client(tmp_path).post(path, content=b"{}", headers=headers)
    _error(response, status, code)


@pytest.mark.parametrize(
    "path",
    ("/api/auth/login", "/api/communities", "/api/invitations/accept"),
)
def test_malformed_json_and_unknown_fields_are_stable_and_non_reflective(
    tmp_path: Path,
    path: str,
) -> None:
    malformed = _client(tmp_path).post(
        path,
        content=b'{"password":"SensitiveValue1!",',
        headers={"Content-Type": "application/json"},
    )
    _error(malformed, 422, "INVALID_REQUEST")
    assert "SensitiveValue1!" not in malformed.text


@pytest.mark.parametrize(
    "path",
    ("/api/auth/login", "/api/communities", "/api/invitations/accept"),
)
def test_actual_oversized_body_is_rejected_across_auth_namespaces(
    tmp_path: Path,
    path: str,
) -> None:
    response = _client(tmp_path).post(
        path,
        content=b"{" + b"x" * (16 * 1024) + b"}",
        headers={"Content-Type": "application/json", "Content-Length": "1"},
    )
    _error(response, 422, "INVALID_REQUEST")


@pytest.mark.parametrize(
    "path",
    ("/api/authentic", "/api/communities-v2", "/api/invitations-old"),
)
def test_near_prefix_routes_fall_through_without_auth_boundary_reclassification(
    tmp_path: Path,
    path: str,
) -> None:
    response = _client(tmp_path).post(path, content=b"not-json")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert "cache-control" not in response.headers
