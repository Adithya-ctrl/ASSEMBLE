from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.api import create_auth_app, install_auth_api
from app.auth.config import AuthSettings


@dataclass
class Clock:
    value: int = 2_000_000_000

    def __call__(self) -> int:
        return self.value


def _app(tmp_path: Path, *, secure: bool = False) -> FastAPI:
    sequence = itertools.count()

    def token_factory() -> str:
        return f"api-token-{next(sequence):064d}"

    return create_auth_app(
        AuthSettings(database_path=tmp_path / "auth.sqlite3", cookie_secure=secure),
        clock=Clock(),
        token_factory=token_factory,
    )


def _signup(client: TestClient, username: str, email: str | None = None) -> dict[str, object]:
    response = client.post(
        "/api/auth/signup",
        json={
            "username": username,
            "email": email,
            "password": "ValidPassword1!",
            "display_name": username.title(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_install_registration_is_idempotent_and_does_not_need_main(tmp_path: Path) -> None:
    app = FastAPI()
    settings = AuthSettings(database_path=tmp_path / "auth.sqlite3")
    first = install_auth_api(app, settings)
    second = install_auth_api(app, settings)
    assert first is second
    assert "/api/auth/signup" in app.openapi()["paths"]


def test_signup_session_logout_cookie_and_cache_contract(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    signup = client.post(
        "/api/auth/signup",
        json={"username": "alice", "password": "ValidPassword1!"},
    )
    assert signup.status_code == 201
    assert signup.headers["cache-control"] == "no-store"
    cookie = signup.headers["set-cookie"]
    assert "assemble_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=604800" in cookie
    assert "expires=" in cookie.lower()
    assert "Domain=" not in cookie
    assert "api-token" not in signup.text

    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["username"] == "alice"

    logout = client.post("/api/auth/logout", json={})
    assert logout.status_code == 204
    cleared = logout.headers["set-cookie"]
    assert "assemble_session=" in cleared and "Max-Age=0" in cleared
    assert "HttpOnly" in cleared and "SameSite=lax" in cleared and "Path=/" in cleared
    assert client.get("/api/auth/session").status_code == 401


def test_complete_admin_invitation_accept_and_redaction_journey(tmp_path: Path) -> None:
    app = _app(tmp_path)
    owner = TestClient(app)
    recipient = TestClient(app)
    wrong = TestClient(app)
    owner_view = _signup(owner, "owner", "owner@example.test")
    recipient_view = _signup(recipient, "recipient", "recipient@example.test")
    _signup(wrong, "wrong", "wrong@example.test")

    community = owner.post(
        "/api/communities",
        json={"name": "Neighbourhood Assembly", "slug": "neighbourhood"},
    )
    assert community.status_code == 201
    community_id = community.json()["id"]

    created = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "recipient@example.test", "role": "COORDINATOR"},
    )
    assert created.status_code == 201
    assert created.headers["referrer-policy"] == "no-referrer"
    invitation = created.json()
    token = invitation["token"]

    listed = owner.get(f"/api/communities/{community_id}/invitations")
    assert listed.status_code == 200
    assert "token" not in listed.text and "token_hash" not in listed.text

    wrong_accept = wrong.post("/api/invitations/accept", json={"token": token})
    assert (wrong_accept.status_code, wrong_accept.json()["error"]["code"]) == (
        404,
        "INVITATION_NOT_AVAILABLE",
    )
    accepted = recipient.post("/api/invitations/accept", json={"token": token})
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "COORDINATOR"
    assert accepted.json()["user_id"] == recipient_view["user"]["id"]

    replay = recipient.post("/api/invitations/accept", json={"token": token})
    assert (replay.status_code, replay.json()["error"]["code"]) == (
        404,
        "INVITATION_NOT_AVAILABLE",
    )
    members = owner.get(f"/api/communities/{community_id}/members")
    assert {item["username"]: item["role"] for item in members.json()} == {
        "owner": "ADMINISTRATOR",
        "recipient": "COORDINATOR",
    }
    assert owner_view["user"]["username"] == "owner"


def test_generic_login_validation_origin_and_forwarded_header_contract(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    _signup(client, "alice")
    unknown = client.post(
        "/api/auth/login",
        json={"identity": "unknown", "password": "WrongPassword1!"},
        headers={"X-Forwarded-For": "203.0.113.77"},
    )
    wrong = client.post(
        "/api/auth/login",
        json={"identity": "alice", "password": "WrongPassword1!"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()

    extra = client.post(
        "/api/auth/login",
        json={"identity": "alice", "password": "ValidPassword1!", "admin": True},
    )
    assert (extra.status_code, extra.json()["error"]["code"]) == (422, "INVALID_REQUEST")

    hostile = client.post(
        "/api/auth/login",
        json={"identity": "alice", "password": "ValidPassword1!"},
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert (hostile.status_code, hostile.json()["error"]["code"]) == (
        403,
        "BROWSER_ORIGIN_REJECTED",
    )


def test_password_change_rotates_cookie_and_invalidates_other_session(tmp_path: Path) -> None:
    app = _app(tmp_path)
    first = TestClient(app)
    second = TestClient(app)
    _signup(first, "alice")
    login = second.post(
        "/api/auth/login",
        json={"identity": "alice", "password": "ValidPassword1!"},
    )
    assert login.status_code == 200
    old_first = first.cookies.get("assemble_session")
    old_second = second.cookies.get("assemble_session")

    changed = first.post(
        "/api/auth/password",
        json={"current_password": "ValidPassword1!", "new_password": "NewPassword2@"},
    )
    assert changed.status_code == 200
    assert first.cookies.get("assemble_session") not in {old_first, old_second}
    assert second.get("/api/auth/session").status_code == 401


def test_secure_cookie_flag_is_configurable(tmp_path: Path) -> None:
    response = TestClient(_app(tmp_path, secure=True)).post(
        "/api/auth/signup",
        json={"username": "alice", "password": "ValidPassword1!"},
    )
    assert "Secure" in response.headers["set-cookie"]
