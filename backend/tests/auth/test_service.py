"""Focused state-machine coverage for the isolated auth service."""

from __future__ import annotations

import itertools
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.auth import service as service_module
from app.auth.errors import AuthProblem
from app.auth.models import (
    CommunityRole,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RoleChangeRequest,
    SignupRequest,
)
from app.auth.service import AuthService
from app.auth.storage import AuthStore


@dataclass
class Clock:
    value: int = 1_000_000

    def __call__(self) -> int:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds


@dataclass
class Harness:
    service: AuthService
    store: AuthStore
    clock: TestClock
    database_path: Path


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    clock = Clock()
    database_path = tmp_path / "auth.sqlite3"
    store = AuthStore(database_path, now=clock())
    sequence = itertools.count()

    def token_factory() -> str:
        return f"test-token-{next(sequence):064d}"

    return Harness(AuthService(store, clock=clock, token_factory=token_factory), store, clock, database_path)


def signup(
    harness: Harness,
    username: str,
    *,
    email: str | None = None,
    display_name: str | None = None,
    client_key: str = "signup-client",
) -> object:
    return harness.service.signup(
        SignupRequest(
            username=username,
            email=email,
            password="ValidPassword1!",
            display_name=display_name,
        ),
        client_key=client_key,
    )


def expect_code(callable_obj, code: str) -> AuthProblem:
    with pytest.raises(AuthProblem) as exc_info:
        callable_obj()
    assert exc_info.value.code == code
    return exc_info.value


def test_signup_login_rotation_and_digest_only(harness: Harness) -> None:
    first = signup(harness, "Alice", email="alice@example.test")
    first_token = first.token

    with harness.store.connect() as connection:
        rows = connection.execute("SELECT token_hash FROM sessions").fetchall()
    assert rows and all(row["token_hash"] == service_module.token_digest(first_token) for row in rows)
    assert first_token not in {row["token_hash"] for row in rows}

    second = harness.service.login(LoginRequest(identity="ALICE", password="ValidPassword1!"), client_key="login-client")
    assert second.token != first_token
    assert second.session.user.username == "alice"
    assert harness.service.session(first_token).user.username == "alice"


def test_unknown_and_malformed_hash_login_run_one_dummy_scrypt(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    original_verify = service_module.verify_password
    calls: list[str] = []

    def recording_verify(password: str, encoded: str) -> bool:
        calls.append(encoded)
        return original_verify(password, encoded)

    monkeypatch.setattr(service_module, "verify_password", recording_verify)
    expect_code(
        lambda: harness.service.login(LoginRequest(identity="unknown", password="WrongPassword1!"), client_key="client"),
        "AUTHENTICATION_FAILED",
    )
    assert calls == [service_module._DUMMY_PASSWORD_HASH]

    with harness.store.transaction(immediate=True) as connection:
        connection.execute(
            """
            INSERT INTO users(id, username, email, password_hash, password_version, display_name, avatar_url, created_at, updated_at)
            VALUES ('bad-hash-user', 'bad-hash', NULL, 'not-a-scrypt-record', 1, NULL, NULL, 1000000, 1000000)
            """
        )
    calls.clear()
    expect_code(
        lambda: harness.service.login(LoginRequest(identity="bad-hash", password="WrongPassword1!"), client_key="client"),
        "AUTHENTICATION_FAILED",
    )
    assert calls == [service_module._DUMMY_PASSWORD_HASH]


def test_stored_hash_precheck_uses_canonical_crypto_parser() -> None:
    canonical = service_module.hash_password("ValidPassword1!", salt=b"\xfb" * 16)
    parts = canonical.split("$")
    noncanonical = parts.copy()
    noncanonical[4] = noncanonical[4].replace("-", "+").replace("_", "/")

    assert AuthService._supported_stored_hash(canonical)
    assert not AuthService._supported_stored_hash("$".join(noncanonical))
    assert AuthService._supported_stored_hash(
        canonical
    ) == service_module.is_supported_password_hash(canonical)
    assert AuthService._supported_stored_hash(
        "$".join(noncanonical)
    ) == service_module.is_supported_password_hash("$".join(noncanonical))


def test_known_stale_session_audited_once_but_unknown_cookie_is_not(harness: Harness) -> None:
    result = signup(harness, "Alice")
    harness.service.logout(result.token)
    expect_code(lambda: harness.service.session(result.token), "AUTHENTICATION_REQUIRED")
    expect_code(lambda: harness.service.session(result.token), "AUTHENTICATION_REQUIRED")
    expect_code(lambda: harness.service.session("random-unknown-cookie"), "AUTHENTICATION_REQUIRED")

    with harness.store.connect() as connection:
        rejected = connection.execute("SELECT event_type FROM audit_events WHERE event_type = 'SESSION_REJECTED'").fetchall()
        assert len(rejected) == 1
        assert connection.execute("SELECT COUNT(*) FROM audit_events WHERE event_type = 'SESSION_REJECTED'").fetchone()[0] == 1


def test_password_change_revokes_all_prior_sessions_and_rotates(harness: Harness) -> None:
    signed_up = signup(harness, "Alice")
    logged_in = harness.service.login(LoginRequest(identity="alice", password="ValidPassword1!"), client_key="login")
    changed = harness.service.change_password(
        signed_up.token,
        PasswordChangeRequest(current_password="ValidPassword1!", new_password="NewPassword2@"),
    )
    assert changed.token not in {signed_up.token, logged_in.token}
    assert changed.session.user.username == "alice"
    expect_code(lambda: harness.service.session(signed_up.token), "AUTHENTICATION_REQUIRED")
    expect_code(lambda: harness.service.session(logged_in.token), "AUTHENTICATION_REQUIRED")
    expect_code(
        lambda: harness.service.login(LoginRequest(identity="alice", password="ValidPassword1!"), client_key="new-client"),
        "AUTHENTICATION_FAILED",
    )
    assert harness.service.login(LoginRequest(identity="alice", password="NewPassword2@"), client_key="new-client").session.user.username == "alice"


def test_profile_omitted_fields_preserve_and_explicit_null_clears(harness: Harness) -> None:
    result = signup(harness, "Alice", display_name="Alice Original")
    preserved = harness.service.update_profile(result.token, ProfileUpdateRequest(avatar_url="https://example.test/a.png"))
    assert preserved.display_name == "Alice Original"
    assert preserved.avatar_url == "https://example.test/a.png"

    cleared = harness.service.update_profile(result.token, ProfileUpdateRequest(display_name=None, avatar_url=None))
    assert cleared.display_name is None
    assert cleared.avatar_url is None


def test_community_create_duplicate_and_current_membership_reload(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    community = harness.service.create_community(owner.token, {"name": "A Community", "slug": "community"})
    assert community.role == CommunityRole.ADMINISTRATOR
    assert harness.service.list_communities(owner.token)[0].id == community.id
    expect_code(
        lambda: harness.service.create_community(owner.token, {"name": "Other", "slug": "COMMUNITY"}),
        "COMMUNITY_UNAVAILABLE",
    )


def test_rbac_cross_community_and_missing_membership_errors(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    member = signup(harness, "Member")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "shared"})
    invitation = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="member", role=CommunityRole.VIEWER),
    )
    harness.service.accept_invitation(member.token, InvitationAcceptRequest(token=invitation.token), client_key="member-client")

    expect_code(lambda: harness.service.list_members(member.token, community.id), "PERMISSION_DENIED")
    expect_code(
        lambda: harness.service.create_invitation(
            member.token,
            community.id,
            InvitationCreateRequest(recipient="someone", role=CommunityRole.MEMBER),
        ),
        "PERMISSION_DENIED",
    )
    expect_code(lambda: harness.service.list_members(member.token, "missing-community"), "COMMUNITY_NOT_FOUND")
    expect_code(
        lambda: harness.service.change_member_role(owner.token, community.id, "missing-user", RoleChangeRequest(role=CommunityRole.MEMBER)),
        "MEMBERSHIP_NOT_FOUND",
    )


def test_invitation_duplicate_wrong_recipient_accept_replay_and_membership_conflict(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    invited = signup(harness, "Invited", email="invited@example.test")
    wrong = signup(harness, "Wrong", email="wrong@example.test")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "invite-flow"})
    invitation = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="invited@example.test", role=CommunityRole.MEMBER),
    )
    expect_code(
        lambda: harness.service.create_invitation(
            owner.token,
            community.id,
            InvitationCreateRequest(recipient="INVITED@example.test", role=CommunityRole.MEMBER),
        ),
        "PENDING_INVITATION_EXISTS",
    )
    expect_code(
        lambda: harness.service.accept_invitation(wrong.token, {"token": invitation.token}, client_key="wrong-client"),
        "INVITATION_NOT_AVAILABLE",
    )
    accepted = harness.service.accept_invitation(invited.token, {"token": invitation.token}, client_key="invite-client")
    assert accepted.role == CommunityRole.MEMBER
    expect_code(
        lambda: harness.service.accept_invitation(invited.token, {"token": invitation.token}, client_key="invite-client"),
        "INVITATION_NOT_AVAILABLE",
    )
    expect_code(
        lambda: harness.service.create_invitation(
            owner.token,
            community.id,
            InvitationCreateRequest(recipient="invited", role=CommunityRole.MEMBER),
        ),
        "MEMBERSHIP_EXISTS",
    )


def test_revoke_and_exact_invitation_expiry(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    recipient = signup(harness, "Recipient")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "lifecycle"})

    revoked = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="recipient", role=CommunityRole.MEMBER),
    )
    result = harness.service.revoke_invitation(owner.token, community.id, revoked.id)
    assert result.state.value == "REVOKED"
    expect_code(
        lambda: harness.service.revoke_invitation(owner.token, community.id, revoked.id),
        "INVITATION_NOT_PENDING",
    )
    expect_code(
        lambda: harness.service.accept_invitation(recipient.token, {"token": revoked.token}, client_key="recipient-client"),
        "INVITATION_NOT_AVAILABLE",
    )

    expiring = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="recipient", role=CommunityRole.MEMBER, expires_in_seconds=300),
    )
    harness.clock.advance(300)
    expect_code(
        lambda: harness.service.accept_invitation(recipient.token, {"token": expiring.token}, client_key="recipient-client"),
        "INVITATION_NOT_AVAILABLE",
    )
    listed = harness.service.list_invitations(owner.token, community.id)
    assert next(item for item in listed if item.id == expiring.id).state.value == "EXPIRED"


def test_demoting_any_administrator_revokes_their_pending_invites_and_audits_reason(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    second_admin = signup(harness, "SecondAdmin")
    pending_target = signup(harness, "PendingTarget")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "demotion"})
    admin_invite = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="secondadmin", role=CommunityRole.ADMINISTRATOR),
    )
    harness.service.accept_invitation(second_admin.token, {"token": admin_invite.token}, client_key="second-client")
    pending = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="pendingtarget", role=CommunityRole.MEMBER),
    )

    changed = harness.service.change_member_role(
        second_admin.token,
        community.id,
        owner.session.user.id,
        RoleChangeRequest(role=CommunityRole.MEMBER),
    )
    assert changed.role == CommunityRole.MEMBER
    invitation_state = next(item for item in harness.service.list_invitations(second_admin.token, community.id) if item.id == pending.id)
    assert invitation_state.state.value == "REVOKED"
    events = harness.service.list_audit_events(second_admin.token, community.id)
    assert any(event.metadata.get("reason") == "INVITER_NO_LONGER_AUTHORISED" for event in events)


def test_last_administrator_guard(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    second_admin = signup(harness, "SecondAdmin")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "last-admin"})
    expect_code(
        lambda: harness.service.change_member_role(owner.token, community.id, owner.session.user.id, CommunityRole.MEMBER),
        "LAST_ADMINISTRATOR_REQUIRED",
    )
    invitation = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="secondadmin", role=CommunityRole.ADMINISTRATOR),
    )
    harness.service.accept_invitation(second_admin.token, {"token": invitation.token}, client_key="second-client")
    assert harness.service.change_member_role(owner.token, community.id, owner.session.user.id, CommunityRole.MEMBER).role == CommunityRole.MEMBER
    expect_code(
        lambda: harness.service.change_member_role(second_admin.token, community.id, second_admin.session.user.id, CommunityRole.MEMBER),
        "LAST_ADMINISTRATOR_REQUIRED",
    )


def test_persisted_dual_rate_buckets_survive_restart_and_reset_after_window(harness: Harness) -> None:
    signup(harness, "Alice")
    for _ in range(10):
        expect_code(
            lambda: harness.service.login(LoginRequest(identity="alice", password="WrongPassword1!"), client_key="same-client"),
            "AUTHENTICATION_FAILED",
        )
    limited = expect_code(
        lambda: harness.service.login(LoginRequest(identity="alice", password="WrongPassword1!"), client_key="same-client"),
        "RATE_LIMITED",
    )
    assert limited.retry_after and limited.retry_after <= 60

    restarted_store = AuthStore(harness.database_path, now=harness.clock())
    restarted = AuthService(restarted_store, clock=harness.clock, token_factory=lambda: "restart-token-" + "x" * 64)
    expect_code(
        lambda: restarted.login(LoginRequest(identity="alice", password="WrongPassword1!"), client_key="same-client"),
        "RATE_LIMITED",
    )
    with restarted_store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rate_limits").fetchone()[0] == 4
    harness.clock.advance(60)
    expect_code(
        lambda: restarted.login(LoginRequest(identity="alice", password="WrongPassword1!"), client_key="same-client"),
        "AUTHENTICATION_FAILED",
    )


def test_audit_metadata_contains_no_password_hash_token_or_full_recipient(harness: Harness) -> None:
    owner = signup(harness, "Owner", email="owner@example.test")
    recipient = signup(harness, "Recipient", email="recipient@example.test")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "audit"})
    invitation = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="recipient@example.test", role=CommunityRole.MEMBER),
    )
    harness.service.accept_invitation(recipient.token, InvitationAcceptRequest(token=invitation.token), client_key="recipient-client")
    events = harness.service.list_audit_events(owner.token, community.id)
    serialised = json.dumps([event.model_dump(mode="json") for event in events], sort_keys=True)
    assert "ValidPassword1!" not in serialised
    assert invitation.token not in serialised
    assert service_module.token_digest(invitation.token) not in serialised
    assert "recipient@example.test" not in serialised
    assert "password_hash" not in serialised

    for forbidden_key in ("password", "password_hash", "token", "token_hash", "digest", "recipient"):
        with pytest.raises(ValueError, match="forbidden audit metadata key"):
            service_module.AuthService._audit_metadata({forbidden_key: "secret"})


def test_expired_pending_invitation_can_be_replaced_without_listing_first(harness: Harness) -> None:
    owner = signup(harness, "Owner")
    signup(harness, "Recipient")
    community = harness.service.create_community(owner.token, {"name": "Shared", "slug": "replacement"})
    first = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(
            recipient="recipient",
            role=CommunityRole.MEMBER,
            expires_in_seconds=300,
        ),
    )
    harness.clock.advance(300)
    replacement = harness.service.create_invitation(
        owner.token,
        community.id,
        InvitationCreateRequest(recipient="recipient", role=CommunityRole.VIEWER),
    )
    assert replacement.id != first.id
    states = {item.id: item.state.value for item in harness.service.list_invitations(owner.token, community.id)}
    assert states == {first.id: "EXPIRED", replacement.id: "PENDING"}


def test_rate_limit_rejection_audit_is_bounded(harness: Harness) -> None:
    signup(harness, "Alice")
    for _ in range(14):
        try:
            harness.service.login(
                LoginRequest(identity="alice", password="WrongPassword1!"),
                client_key="same-client",
            )
        except AuthProblem:
            pass
    with harness.store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = 'RATE_LIMIT_REJECTED'"
        ).fetchone()[0] == 1
