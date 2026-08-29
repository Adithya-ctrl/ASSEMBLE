"""Adversarial API and service checks for the frozen auth boundary."""

from __future__ import annotations

import itertools
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

from app.auth.api import create_auth_app
from app.auth.config import AuthSettings
from app.auth.crypto import token_digest
from app.auth.errors import AuthProblem
from app.auth.models import CommunityRole
from app.auth.service import AuthService
from app.auth import service as service_module


PASSWORD = "ValidPassword1!"


@dataclass
class Clock:
    value: int = 2_100_000_000

    def __call__(self) -> int:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds


class TokenFactory:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._sequence = itertools.count()
        self._lock = threading.Lock()

    def __call__(self) -> str:
        with self._lock:
            return f"{self._prefix}-{next(self._sequence):064d}"


def _settings(database_path: Path, *, session_ttl_seconds: int = 7 * 24 * 60 * 60) -> AuthSettings:
    return AuthSettings(
        database_path=database_path,
        session_ttl_seconds=session_ttl_seconds,
    )


def _app(
    database_path: Path,
    clock: Clock,
    *,
    token_prefix: str,
    session_ttl_seconds: int = 7 * 24 * 60 * 60,
):
    return create_auth_app(
        _settings(database_path, session_ttl_seconds=session_ttl_seconds),
        clock=clock,
        token_factory=TokenFactory(token_prefix),
    )


def _api_signup(
    client: TestClient,
    username: str,
    *,
    email: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/auth/signup",
        json={
            "username": username,
            "email": email,
            "password": PASSWORD,
            "display_name": username.title(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _service_signup(
    service: AuthService,
    username: str,
    *,
    email: str | None = None,
):
    return service.signup(
        {
            "username": username,
            "email": email,
            "password": PASSWORD,
            "display_name": username.title(),
        },
        client_key=f"signup-{username}",
    )


def _service_outcome(operation: Callable[[], object]) -> str:
    try:
        operation()
    except AuthProblem as exc:
        return exc.code
    return "OK"


def _assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_attacker_cookie_is_replaced_without_session_fixation(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    app = _app(database_path, Clock(), token_prefix="fixation")
    client = TestClient(app)
    attacker_cookie = "attacker-selected-session-cookie"

    response = client.post(
        "/api/auth/signup",
        json={"username": "alice", "password": PASSWORD},
        headers={"Cookie": f"assemble_session={attacker_cookie}"},
    )

    assert response.status_code == 201
    issued_cookie = client.cookies.get("assemble_session")
    assert issued_cookie and issued_cookie != attacker_cookie
    assert issued_cookie not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get("/api/auth/session").status_code == 200

    attacker_replay = TestClient(app).get(
        "/api/auth/session",
        headers={"Cookie": f"assemble_session={attacker_cookie}"},
    )
    _assert_error(attacker_replay, 401, "AUTHENTICATION_REQUIRED")


def test_database_dump_contains_digests_but_no_raw_password_cookie_or_invite_token(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "auth.sqlite3"
    app = _app(database_path, Clock(), token_prefix="secret-scan")
    owner = TestClient(app)
    _api_signup(owner, "owner", email="owner@example.test")
    raw_cookie = owner.cookies.get("assemble_session")
    assert raw_cookie
    community = owner.post(
        "/api/communities",
        json={"name": "Secret Scan", "slug": "secret-scan"},
    ).json()
    invitation = owner.post(
        f"/api/communities/{community['id']}/invitations",
        json={"recipient": "recipient@example.test", "role": "MEMBER"},
    ).json()
    raw_invite = invitation["token"]

    service: AuthService = app.state.assemble_auth_service
    with service.store.connect() as connection:
        database_dump = "\n".join(connection.iterdump())

    for raw_secret in (PASSWORD, raw_cookie, raw_invite):
        assert raw_secret not in database_dump
    assert token_digest(raw_cookie) in database_dump
    assert token_digest(raw_invite) in database_dump
    assert "scrypt-v1$" in database_dump


def test_double_accept_race_has_exactly_one_winner(tmp_path: Path) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="double-accept")
    service: AuthService = app.state.assemble_auth_service
    owner = _service_signup(service, "owner")
    recipient = _service_signup(service, "recipient")
    community = service.create_community(owner.token, {"name": "Race", "slug": "race"})
    invitation = service.create_invitation(
        owner.token,
        community.id,
        {"recipient": "recipient", "role": "MEMBER"},
    )
    barrier = threading.Barrier(2)

    def accept(client_key: str) -> str:
        barrier.wait()
        return _service_outcome(
            lambda: service.accept_invitation(
                recipient.token,
                {"token": invitation.token},
                client_key=client_key,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(accept, ("accept-a", "accept-b")))

    assert sorted(outcomes) == ["INVITATION_NOT_AVAILABLE", "OK"]
    with service.store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM memberships WHERE community_id = ? AND user_id = ?",
            (community.id, recipient.session.user.id),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT state FROM invitations WHERE id = ?",
            (invitation.id,),
        ).fetchone()[0] == "ACCEPTED"


def test_accept_and_revoke_race_cannot_both_commit(tmp_path: Path) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="accept-revoke")
    service: AuthService = app.state.assemble_auth_service
    owner = _service_signup(service, "owner")
    recipient = _service_signup(service, "recipient")
    community = service.create_community(owner.token, {"name": "Race", "slug": "race"})
    invitation = service.create_invitation(
        owner.token,
        community.id,
        {"recipient": "recipient", "role": "MEMBER"},
    )
    barrier = threading.Barrier(2)

    def accept() -> str:
        barrier.wait()
        return "accept:" + _service_outcome(
            lambda: service.accept_invitation(
                recipient.token,
                {"token": invitation.token},
                client_key="accept-client",
            )
        )

    def revoke() -> str:
        barrier.wait()
        return "revoke:" + _service_outcome(
            lambda: service.revoke_invitation(owner.token, community.id, invitation.id)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [executor.submit(accept), executor.submit(revoke)]
        results = {future.result() for future in outcomes}

    assert len([result for result in results if result.endswith(":OK")]) == 1
    assert results in (
        {"accept:OK", "revoke:INVITATION_NOT_PENDING"},
        {"accept:INVITATION_NOT_AVAILABLE", "revoke:OK"},
    )
    with service.store.connect() as connection:
        state = connection.execute(
            "SELECT state FROM invitations WHERE id = ?",
            (invitation.id,),
        ).fetchone()[0]
        membership_count = connection.execute(
            "SELECT COUNT(*) FROM memberships WHERE community_id = ? AND user_id = ?",
            (community.id, recipient.session.user.id),
        ).fetchone()[0]
    assert (state, membership_count) in {("ACCEPTED", 1), ("REVOKED", 0)}


def test_concurrent_two_admin_demotion_preserves_an_administrator(tmp_path: Path) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="admin-race")
    service: AuthService = app.state.assemble_auth_service
    first = _service_signup(service, "firstadmin")
    second = _service_signup(service, "secondadmin")
    community = service.create_community(first.token, {"name": "Admins", "slug": "admins"})
    invitation = service.create_invitation(
        first.token,
        community.id,
        {"recipient": "secondadmin", "role": "ADMINISTRATOR"},
    )
    service.accept_invitation(
        second.token,
        {"token": invitation.token},
        client_key="second-admin",
    )
    barrier = threading.Barrier(2)

    def demote(actor_token: str, target_user_id: str) -> str:
        barrier.wait()
        return _service_outcome(
            lambda: service.change_member_role(
                actor_token,
                community.id,
                target_user_id,
                CommunityRole.MEMBER,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda arguments: demote(*arguments),
                (
                    (first.token, second.session.user.id),
                    (second.token, first.session.user.id),
                ),
            )
        )

    assert sorted(outcomes) == ["OK", "PERMISSION_DENIED"]
    with service.store.connect() as connection:
        roles = [
            row[0]
            for row in connection.execute(
                "SELECT role FROM memberships WHERE community_id = ? ORDER BY user_id",
                (community.id,),
            )
        ]
    assert roles.count("ADMINISTRATOR") == 1
    assert roles.count("MEMBER") == 1


def test_exact_invitation_and_session_expiry_boundaries(tmp_path: Path) -> None:
    clock = Clock()
    app = _app(
        tmp_path / "auth.sqlite3",
        clock,
        token_prefix="expiry",
        session_ttl_seconds=301,
    )
    service: AuthService = app.state.assemble_auth_service
    owner = _service_signup(service, "owner")
    recipient = _service_signup(service, "recipient")
    community = service.create_community(owner.token, {"name": "Expiry", "slug": "expiry"})
    invitation = service.create_invitation(
        owner.token,
        community.id,
        {"recipient": "recipient", "role": "MEMBER", "expires_in_seconds": 300},
    )

    clock.advance(299)
    assert service.session(owner.token).user.username == "owner"
    assert service.list_invitations(owner.token, community.id)[0].state.value == "PENDING"

    clock.advance(1)
    assert _service_outcome(
        lambda: service.accept_invitation(
            recipient.token,
            {"token": invitation.token},
            client_key="expiry-recipient",
        )
    ) == "INVITATION_NOT_AVAILABLE"
    assert service.list_invitations(owner.token, community.id)[0].state.value == "EXPIRED"

    clock.advance(1)
    assert _service_outcome(lambda: service.session(owner.token)) == "AUTHENTICATION_REQUIRED"


def test_role_demotion_is_immediate_and_cross_community_access_is_concealed(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="rbac")
    service: AuthService = app.state.assemble_auth_service
    owner = _service_signup(service, "owner")
    second = _service_signup(service, "second")
    outsider = _service_signup(service, "outsider")
    first_community = service.create_community(owner.token, {"name": "First", "slug": "first"})
    second_community = service.create_community(
        outsider.token,
        {"name": "Second", "slug": "second"},
    )
    invitation = service.create_invitation(
        owner.token,
        first_community.id,
        {"recipient": "second", "role": "ADMINISTRATOR"},
    )
    service.accept_invitation(
        second.token,
        {"token": invitation.token},
        client_key="second-client",
    )
    assert len(service.list_members(second.token, first_community.id)) == 2

    service.change_member_role(
        owner.token,
        first_community.id,
        second.session.user.id,
        CommunityRole.MEMBER,
    )

    assert _service_outcome(
        lambda: service.list_members(second.token, first_community.id)
    ) == "PERMISSION_DENIED"
    assert service.session(second.token).memberships[0].role == CommunityRole.MEMBER
    assert _service_outcome(
        lambda: service.list_members(owner.token, second_community.id)
    ) == "COMMUNITY_NOT_FOUND"


def test_wrong_recipient_revoked_and_replay_failures_are_publicly_identical(
    tmp_path: Path,
) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="generic")
    owner = TestClient(app)
    recipient = TestClient(app)
    wrong = TestClient(app)
    _api_signup(owner, "owner")
    _api_signup(recipient, "recipient")
    _api_signup(wrong, "wrong")
    community_id = owner.post(
        "/api/communities",
        json={"name": "Generic Errors", "slug": "generic-errors"},
    ).json()["id"]

    revoked_invitation = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "recipient", "role": "MEMBER"},
    ).json()
    wrong_response = wrong.post(
        "/api/invitations/accept",
        json={"token": revoked_invitation["token"]},
    )
    owner.post(
        f"/api/communities/{community_id}/invitations/{revoked_invitation['id']}/revoke",
        json={},
    )
    revoked_response = recipient.post(
        "/api/invitations/accept",
        json={"token": revoked_invitation["token"]},
    )

    accepted_invitation = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "recipient", "role": "MEMBER"},
    ).json()
    accepted = recipient.post(
        "/api/invitations/accept",
        json={"token": accepted_invitation["token"]},
    )
    assert accepted.status_code == 200
    replay_response = recipient.post(
        "/api/invitations/accept",
        json={"token": accepted_invitation["token"]},
    )

    for response in (wrong_response, revoked_response, replay_response):
        _assert_error(response, 404, "INVITATION_NOT_AVAILABLE")
        assert response.json()["error"]["details"] == {}
    assert wrong_response.json() == revoked_response.json() == replay_response.json()


def test_malformed_and_actual_byte_oversized_bodies_use_frozen_errors(
    tmp_path: Path,
) -> None:
    client = TestClient(_app(tmp_path / "auth.sqlite3", Clock(), token_prefix="body"))

    malformed = client.post(
        "/api/auth/login",
        content=b'{"identity":"alice","password":',
        headers={"Content-Type": "application/json"},
    )
    _assert_error(malformed, 422, "INVALID_REQUEST")

    def oversized_chunks():
        yield b'{"identity":"alice","password":"'
        yield b"x" * (16 * 1024)
        yield b'"}'

    oversized = client.post(
        "/api/auth/login",
        content=oversized_chunks(),
        headers={"Content-Type": "application/json"},
    )
    _assert_error(oversized, 422, "INVALID_REQUEST")


def test_fresh_app_same_file_preserves_security_state_and_rate_window(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    clock = Clock()
    first_app = _app(database_path, clock, token_prefix="restart-first")
    owner = TestClient(first_app)
    accepted_user = TestClient(first_app)
    pending_user = TestClient(first_app)
    revoked_user = TestClient(first_app)
    _api_signup(owner, "owner")
    _api_signup(accepted_user, "accepted")
    _api_signup(pending_user, "pending")
    _api_signup(revoked_user, "revoked")
    owner_cookie = owner.cookies.get("assemble_session")
    assert owner_cookie
    community_id = owner.post(
        "/api/communities",
        json={"name": "Restart", "slug": "restart"},
    ).json()["id"]

    accepted_invitation = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "accepted", "role": "VIEWER"},
    ).json()
    assert accepted_user.post(
        "/api/invitations/accept",
        json={"token": accepted_invitation["token"]},
    ).status_code == 200
    pending_invitation = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "pending", "role": "MEMBER"},
    ).json()
    revoked_invitation = owner.post(
        f"/api/communities/{community_id}/invitations",
        json={"recipient": "revoked", "role": "COORDINATOR"},
    ).json()
    assert owner.post(
        f"/api/communities/{community_id}/invitations/{revoked_invitation['id']}/revoke",
        json={},
    ).status_code == 200

    rate_client = TestClient(first_app)
    for _ in range(10):
        failed = rate_client.post(
            "/api/auth/login",
            json={"identity": "owner", "password": "WrongPassword1!"},
        )
        _assert_error(failed, 401, "AUTHENTICATION_FAILED")

    owner.close()
    accepted_user.close()
    pending_user.close()
    revoked_user.close()
    rate_client.close()

    restarted_app = _app(database_path, clock, token_prefix="restart-second")
    restarted_owner = TestClient(restarted_app)
    cookie_header = {"Cookie": f"assemble_session={owner_cookie}"}
    session = restarted_owner.get("/api/auth/session", headers=cookie_header)
    assert session.status_code == 200
    assert session.json()["user"]["username"] == "owner"
    assert session.json()["memberships"][0]["community_id"] == community_id

    invitations = restarted_owner.get(
        f"/api/communities/{community_id}/invitations",
        headers=cookie_header,
    )
    assert invitations.status_code == 200
    states = {item["id"]: item["state"] for item in invitations.json()}
    assert states == {
        accepted_invitation["id"]: "ACCEPTED",
        pending_invitation["id"]: "PENDING",
        revoked_invitation["id"]: "REVOKED",
    }

    limited = TestClient(restarted_app).post(
        "/api/auth/login",
        json={"identity": "owner", "password": "WrongPassword1!"},
    )
    _assert_error(limited, 429, "RATE_LIMITED")
    assert limited.headers["retry-after"] == "60"

    service: AuthService = restarted_app.state.assemble_auth_service
    with service.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 4
        assert connection.execute(
            "SELECT COUNT(*) FROM memberships WHERE community_id = ?",
            (community_id,),
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE token_hash = ? AND revoked_at IS NULL",
            (token_digest(owner_cookie),),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM rate_limits WHERE count >= 11",
        ).fetchone()[0] >= 2
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 1",
        ).fetchone()[0] == 1


def test_concurrent_password_change_prevents_old_password_session_issuance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="credential-race")
    service: AuthService = app.state.assemble_auth_service
    account = _service_signup(service, "alice")
    old_hash_verified = threading.Event()
    allow_login_to_continue = threading.Event()
    original_verify = service_module.verify_password

    def pausing_verify(password: str, encoded: str) -> bool:
        result = original_verify(password, encoded)
        if threading.current_thread().name == "stale-old-login" and result:
            old_hash_verified.set()
            assert allow_login_to_continue.wait(timeout=5)
        return result

    monkeypatch.setattr(service_module, "verify_password", pausing_verify)
    outcome: list[str] = []

    def old_password_login() -> None:
        outcome.append(
            _service_outcome(
                lambda: service.login(
                    {"identity": "alice", "password": PASSWORD},
                    client_key="stale-login-client",
                )
            )
        )

    thread = threading.Thread(target=old_password_login, name="stale-old-login")
    thread.start()
    assert old_hash_verified.wait(timeout=5)
    changed = service.change_password(
        account.token,
        {"current_password": PASSWORD, "new_password": "NewPassword2@"},
        client_key="password-client",
    )
    allow_login_to_continue.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert outcome == ["AUTHENTICATION_FAILED"]
    assert service.session(changed.token).user.username == "alice"


def test_password_change_scrypt_is_rate_limited_and_persists_across_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    clock = Clock()
    app = _app(database_path, clock, token_prefix="password-rate")
    service: AuthService = app.state.assemble_auth_service
    account = _service_signup(service, "alice")
    for _ in range(10):
        assert _service_outcome(
            lambda: service.change_password(
                account.token,
                {"current_password": "WrongPassword1!", "new_password": "NewPassword2@"},
                client_key="same-password-client",
            )
        ) == "AUTHENTICATION_FAILED"
    assert _service_outcome(
        lambda: service.change_password(
            account.token,
            {"current_password": "WrongPassword1!", "new_password": "NewPassword2@"},
            client_key="same-password-client",
        )
    ) == "RATE_LIMITED"

    restarted = _app(database_path, clock, token_prefix="password-rate-restart")
    restarted_service: AuthService = restarted.state.assemble_auth_service
    assert _service_outcome(
        lambda: restarted_service.change_password(
            account.token,
            {"current_password": "WrongPassword1!", "new_password": "NewPassword2@"},
            client_key="same-password-client",
        )
    ) == "RATE_LIMITED"
    with restarted_service.store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = 'PASSWORD_CHANGE_FAILED'"
        ).fetchone()[0] == 10
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = 'RATE_LIMIT_REJECTED'"
        ).fetchone()[0] == 1


def test_locked_database_returns_stable_service_busy_envelope(tmp_path: Path) -> None:
    app = _app(tmp_path / "auth.sqlite3", Clock(), token_prefix="busy")
    service: AuthService = app.state.assemble_auth_service
    original_connect = service.store.connect

    def fast_connect():
        connection = original_connect()
        connection.execute("PRAGMA busy_timeout=1")
        return connection

    service.store.connect = fast_connect  # type: ignore[method-assign]
    holder = original_connect()
    holder.execute("BEGIN IMMEDIATE")
    try:
        response = TestClient(app).post(
            "/api/auth/signup",
            json={"username": "alice", "password": PASSWORD},
        )
    finally:
        holder.rollback()
        holder.close()
    _assert_error(response, 503, "SERVICE_BUSY")
    assert response.headers["retry-after"] == "1"
    assert response.headers["cache-control"] == "no-store"


def test_auth_database_files_are_private_on_posix(tmp_path: Path) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "private-auth" / "auth.sqlite3"
    app = _app(database_path, Clock(), token_prefix="permissions")
    service: AuthService = app.state.assemble_auth_service
    with service.store.transaction(immediate=True):
        paths = [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]
        assert oct(database_path.parent.stat().st_mode & 0o777) == "0o700"
        for path in paths:
            if path.exists():
                assert oct(path.stat().st_mode & 0o777) == "0o600"
