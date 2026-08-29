"""Adversarial identity lifecycle, RBAC, rate and model-invariant checks."""

from __future__ import annotations

import itertools
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from app.auth import service as service_module
from app.auth.config import AuthSettings
from app.auth.errors import AuthProblem
from app.auth.models import CommunityRole
from app.auth.service import AuthService
from app.auth.storage import AuthStore


def _password() -> str:
    return "LifecycleAa1!"


@dataclass
class Clock:
    value: int = 2_200_000_000

    def __call__(self) -> int:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds


@dataclass
class Harness:
    service: AuthService
    store: AuthStore
    clock: Clock
    database_path: Path


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    clock = Clock()
    database_path = tmp_path / "auth.sqlite3"
    settings = AuthSettings(database_path=database_path)
    store = AuthStore(database_path, now=clock())
    sequence = itertools.count()
    lock = threading.Lock()

    def token_factory() -> str:
        with lock:
            return f"lifecycle-token-{next(sequence):064d}"

    return Harness(
        AuthService(store, settings, clock=clock, token_factory=token_factory),
        store,
        clock,
        database_path,
    )


def signup(harness: Harness, username: str, *, email: str | None = None, client: str | None = None):
    return harness.service.signup(
        {
            "username": username,
            "email": email,
            "password": _password(),
            "display_name": username,
        },
        client_key=client or f"signup-{username}",
    )


def outcome(operation: Callable[[], object]) -> str:
    try:
        operation()
    except AuthProblem as exc:
        return exc.code
    return "OK"


def expect_code(operation: Callable[[], object], code: str) -> AuthProblem:
    with pytest.raises(AuthProblem) as exc_info:
        operation()
    assert exc_info.value.code == code
    return exc_info.value


def test_signup_username_and_email_collisions_are_casefolded_and_generic(harness: Harness) -> None:
    first = signup(harness, "Alice", email="Alice@Example.Test")
    assert first.session.user.username == "alice"
    duplicate_username = expect_code(
        lambda: signup(harness, " ALICE ", email="new@example.test", client="collision-user"),
        "ACCOUNT_UNAVAILABLE",
    )
    duplicate_email = expect_code(
        lambda: signup(harness, "different", email="ALICE@example.TEST", client="collision-email"),
        "ACCOUNT_UNAVAILABLE",
    )
    assert duplicate_username.details == duplicate_email.details == {}
    with harness.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_concurrent_signup_same_normalized_identity_has_one_winner(harness: Harness) -> None:
    barrier = threading.Barrier(2)

    def create(client: str) -> str:
        barrier.wait()
        return outcome(
            lambda: harness.service.signup(
                {
                    "username": "race-user",
                    "email": f"{client}@example.test",
                    "password": _password(),
                },
                client_key=client,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, ("race-a", "race-b")))
    assert sorted(results) == ["ACCOUNT_UNAVAILABLE", "OK"]
    with harness.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users WHERE username = 'race-user'").fetchone()[0] == 1


def _provision_roles(harness: Harness):
    owner = signup(harness, "owner", email="owner@example.test")
    coordinator = signup(harness, "coordinator", email="coordinator@example.test")
    member = signup(harness, "member", email="member@example.test")
    viewer = signup(harness, "viewer", email="viewer@example.test")
    target = signup(harness, "target", email="target@example.test")
    community = harness.service.create_community(owner.token, {"name": "Roles", "slug": "roles"})
    for account, role in (
        (coordinator, CommunityRole.COORDINATOR),
        (member, CommunityRole.MEMBER),
        (viewer, CommunityRole.VIEWER),
    ):
        invitation = harness.service.create_invitation(
            owner.token,
            community.id,
            {"recipient": account.session.user.username, "role": role.value},
        )
        harness.service.accept_invitation(account.token, {"token": invitation.token}, client_key=f"accept-{account.session.user.username}")
    return owner, coordinator, member, viewer, target, community


def test_each_persisted_role_has_only_its_declared_administration_permissions(harness: Harness) -> None:
    owner, coordinator, member, viewer, target, community = _provision_roles(harness)
    pending = harness.service.create_invitation(
        owner.token,
        community.id,
        {"recipient": target.session.user.username, "role": CommunityRole.VIEWER.value},
    )

    assert {item.role for item in harness.service.list_members(owner.token, community.id)} == {
        CommunityRole.ADMINISTRATOR,
        CommunityRole.COORDINATOR,
        CommunityRole.MEMBER,
        CommunityRole.VIEWER,
    }
    listed = harness.service.list_invitations(owner.token, community.id)
    assert next(item for item in listed if item.id == pending.id).state.value == "PENDING"
    assert [item.id for item in harness.service.list_invitations(owner.token, community.id)] == [
        item.id for item in listed
    ]

    for account, expected_role in (
        (coordinator, CommunityRole.COORDINATOR),
        (member, CommunityRole.MEMBER),
        (viewer, CommunityRole.VIEWER),
    ):
        assert harness.service.get_community(account.token, community.id).role == expected_role
        expect_code(lambda account=account: harness.service.list_members(account.token, community.id), "PERMISSION_DENIED")
        expect_code(
            lambda account=account: harness.service.list_invitations(account.token, community.id),
            "PERMISSION_DENIED",
        )
        expect_code(
            lambda account=account: harness.service.create_invitation(
                account.token,
                community.id,
                {"recipient": target.session.user.username, "role": CommunityRole.MEMBER.value},
            ),
            "PERMISSION_DENIED",
        )
        expect_code(
            lambda account=account: harness.service.change_member_role(
                account.token,
                community.id,
                owner.session.user.id,
                CommunityRole.MEMBER,
            ),
            "PERMISSION_DENIED",
        )
        expect_code(
            lambda account=account: harness.service.revoke_invitation(account.token, community.id, pending.id),
            "PERMISSION_DENIED",
        )

    assert harness.service.revoke_invitation(owner.token, community.id, pending.id).state.value == "REVOKED"


def test_demoting_the_actual_inviter_revokes_that_inviters_pending_grants(harness: Harness) -> None:
    owner = signup(harness, "owner")
    second_admin = signup(harness, "second-admin")
    recipient = signup(harness, "recipient")
    community = harness.service.create_community(owner.token, {"name": "Demotion", "slug": "demotion-actual-inviter"})
    admin_invite = harness.service.create_invitation(
        owner.token,
        community.id,
        {"recipient": second_admin.session.user.username, "role": CommunityRole.ADMINISTRATOR.value},
    )
    harness.service.accept_invitation(second_admin.token, {"token": admin_invite.token}, client_key="second-admin-accept")
    pending = harness.service.create_invitation(
        second_admin.token,
        community.id,
        {"recipient": recipient.session.user.username, "role": CommunityRole.MEMBER.value},
    )

    changed = harness.service.change_member_role(
        owner.token,
        community.id,
        second_admin.session.user.id,
        CommunityRole.MEMBER,
    )
    assert changed.role == CommunityRole.MEMBER
    listed = harness.service.list_invitations(owner.token, community.id)
    assert next(item for item in listed if item.id == pending.id).state.value == "REVOKED"
    expect_code(
        lambda: harness.service.accept_invitation(recipient.token, {"token": pending.token}, client_key="recipient"),
        "INVITATION_NOT_AVAILABLE",
    )
    assert any(
        event.metadata.get("reason") == "INVITER_NO_LONGER_AUTHORISED"
        and event.invitation_id == pending.id
        for event in harness.service.list_audit_events(owner.token, community.id)
    )


def test_current_role_is_reloaded_after_an_old_session_view_becomes_stale(harness: Harness) -> None:
    owner = signup(harness, "owner")
    member = signup(harness, "member")
    community = harness.service.create_community(owner.token, {"name": "Reload", "slug": "reload-role"})
    invitation = harness.service.create_invitation(
        owner.token,
        community.id,
        {"recipient": member.session.user.username, "role": CommunityRole.ADMINISTRATOR.value},
    )
    harness.service.accept_invitation(member.token, {"token": invitation.token}, client_key="reload-accept")
    assert harness.service.list_members(member.token, community.id)
    harness.service.change_member_role(
        owner.token,
        community.id,
        member.session.user.id,
        CommunityRole.MEMBER,
    )
    # The SessionResult held by the caller still contains the prior membership
    # view, but every protected operation must query the current database row.
    expect_code(lambda: harness.service.list_members(member.token, community.id), "PERMISSION_DENIED")
    assert harness.service.get_community(member.token, community.id).role == CommunityRole.MEMBER


def test_audit_limit_is_bounded_ordered_and_cannot_cross_community(harness: Harness) -> None:
    owner = signup(harness, "owner")
    outsider = signup(harness, "outsider")
    first = harness.service.create_community(owner.token, {"name": "First", "slug": "audit-first"})
    second = harness.service.create_community(outsider.token, {"name": "Second", "slug": "audit-second"})
    harness.service.create_invitation(
        owner.token,
        first.id,
        {"recipient": outsider.session.user.username, "role": CommunityRole.MEMBER.value},
    )
    with harness.store.connect() as connection:
        first_events = connection.execute(
            "SELECT sequence FROM audit_events WHERE community_id = ? ORDER BY sequence DESC",
            (first.id,),
        ).fetchall()
    assert first_events
    assert len(harness.service.list_audit_events(owner.token, first.id, 1)) == 1
    assert harness.service.list_audit_events(owner.token, first.id, 200)[0].occurred_at >= harness.service.list_audit_events(owner.token, first.id, 200)[-1].occurred_at
    for limit in (0, 201, True, False, 1.0, "1"):
        expect_code(lambda limit=limit: harness.service.list_audit_events(owner.token, first.id, limit), "INVALID_REQUEST")
    expect_code(lambda: harness.service.list_audit_events(owner.token, second.id), "COMMUNITY_NOT_FOUND")
    assert all(event.community_id == first.id for event in harness.service.list_audit_events(owner.token, first.id, 200))


def test_audit_metadata_forbids_sensitive_keys_recursively_and_is_canonical() -> None:
    clean = {"z": 1, "a": ["x", {"reason": "test"}]}
    first = service_module.AuthService._audit_metadata(clean)
    second = service_module.AuthService._audit_metadata({"a": ["x", {"reason": "test"}], "z": 1})
    assert first == second == json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    for metadata in (
        {"nested": {"TOKEN": "ephemeral"}},
        {"nested": [{"password_hash": "ephemeral"}]},
        {"DIGEST": "ephemeral"},
        {"recipient": {"kind": "email"}},
    ):
        with pytest.raises(ValueError, match="forbidden audit metadata key"):
            service_module.AuthService._audit_metadata(metadata)


def test_rate_limit_blocks_before_password_verification_and_resets_at_exact_window(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    signup(harness, "alice")
    original_verify = service_module.verify_password
    calls: list[str] = []

    def recording_verify(password: str, encoded: str) -> bool:
        calls.append(encoded)
        return original_verify(password, encoded)

    monkeypatch.setattr(service_module, "verify_password", recording_verify)
    for _ in range(10):
        assert outcome(
            lambda: harness.service.login(
                {"identity": "alice", "password": "WrongAa1!"},
                client_key="exact-rate-client",
            )
        ) == "AUTHENTICATION_FAILED"
    assert outcome(
        lambda: harness.service.login(
            {"identity": "alice", "password": "WrongAa1!"},
            client_key="exact-rate-client",
        )
    ) == "RATE_LIMITED"
    assert len(calls) == 10
    harness.clock.advance(60)
    assert outcome(
        lambda: harness.service.login(
            {"identity": "alice", "password": "WrongAa1!"},
            client_key="exact-rate-client",
        )
    ) == "AUTHENTICATION_FAILED"
    assert len(calls) == 11


def test_concurrent_login_attempts_have_exactly_one_fixed_window_budget(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    signup(harness, "alice")
    monkeypatch.setattr(service_module, "verify_password", lambda password, encoded: False)
    barrier = threading.Barrier(12)

    def attempt(_: int) -> str:
        barrier.wait()
        return outcome(
            lambda: harness.service.login(
                {"identity": "alice", "password": "WrongAa1!"},
                client_key="concurrent-rate-client",
            )
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(12)))
    assert results.count("AUTHENTICATION_FAILED") == 10
    assert results.count("RATE_LIMITED") == 2
    with harness.store.connect() as connection:
        assert connection.execute(
            "SELECT count FROM rate_limits WHERE bucket_hash = ?",
            (service_module.opaque_bucket("auth-rate", "login", "client", "concurrent-rate-client"),),
        ).fetchone()[0] == 12


def test_invitation_accept_rate_limit_is_scoped_separately_from_login(harness: Harness) -> None:
    owner = signup(harness, "owner")
    recipient = signup(harness, "recipient")
    community = harness.service.create_community(owner.token, {"name": "Rate", "slug": "rate-invites"})
    for _ in range(10):
        assert outcome(
            lambda: harness.service.accept_invitation(
                recipient.token,
                {"token": "z" * 40},
                client_key="invite-rate-client",
            )
        ) == "INVITATION_NOT_AVAILABLE"
    assert outcome(
        lambda: harness.service.accept_invitation(
            recipient.token,
            {"token": "z" * 40},
            client_key="invite-rate-client",
        )
    ) == "RATE_LIMITED"
    # A login bucket with the same client name is independent of invitation use.
    assert outcome(
        lambda: harness.service.login(
            {"identity": "recipient", "password": "WrongAa1!"},
            client_key="invite-rate-client",
        )
    ) == "AUTHENTICATION_FAILED"
    assert community.id


def test_deterministic_model_checks_invitation_and_membership_invariants(harness: Harness) -> None:
    """Run a small generated lifecycle while checking durable invariants after each step."""

    rng = random.Random(20260830)
    owner = signup(harness, "model-owner")
    candidates = [signup(harness, f"model-user-{index}") for index in range(4)]
    community = harness.service.create_community(owner.token, {"name": "Model", "slug": "model-lifecycle"})
    known_tokens: dict[str, str] = {}

    def check_invariants() -> None:
        with harness.store.connect() as connection:
            duplicate_pending = connection.execute(
                """
                SELECT recipient_kind, recipient, COUNT(*)
                FROM invitations
                WHERE community_id = ? AND state = 'PENDING'
                GROUP BY recipient_kind, recipient
                HAVING COUNT(*) > 1
                """,
                (community.id,),
            ).fetchall()
            assert duplicate_pending == []
            invitation_rows = connection.execute(
                "SELECT state, accepted_by_user_id, accepted_at, revoked_at FROM invitations WHERE community_id = ?",
                (community.id,),
            ).fetchall()
            assert {row[0] for row in invitation_rows} <= {"PENDING", "ACCEPTED", "REVOKED", "EXPIRED"}
            for state, accepted_by, accepted_at, revoked_at in invitation_rows:
                if state == "ACCEPTED":
                    assert accepted_by is not None and accepted_at is not None and revoked_at is None
                elif state == "REVOKED":
                    assert accepted_by is None and accepted_at is None and revoked_at is not None
                elif state == "PENDING":
                    assert accepted_by is None and accepted_at is None and revoked_at is None
            assert connection.execute(
                "SELECT COUNT(*) FROM memberships WHERE community_id = ? AND role = 'ADMINISTRATOR'",
                (community.id,),
            ).fetchone()[0] >= 1

    for _ in range(24):
        candidate = rng.choice(candidates)
        with harness.store.connect() as connection:
            is_member = connection.execute(
                "SELECT 1 FROM memberships WHERE community_id = ? AND user_id = ?",
                (community.id, candidate.session.user.id),
            ).fetchone()
            pending = connection.execute(
                "SELECT id FROM invitations WHERE community_id = ? AND recipient = ? AND state = 'PENDING'",
                (community.id, candidate.session.user.username),
            ).fetchone()
        if is_member is not None:
            # A member cannot be invited again; this is a deliberate conflict path.
            assert outcome(
                lambda candidate=candidate: harness.service.create_invitation(
                    owner.token,
                    community.id,
                    {"recipient": candidate.session.user.username, "role": CommunityRole.MEMBER.value},
                )
            ) == "MEMBERSHIP_EXISTS"
        elif pending is None:
            invitation = harness.service.create_invitation(
                owner.token,
                community.id,
                {"recipient": candidate.session.user.username, "role": rng.choice(["MEMBER", "VIEWER"])},
            )
            known_tokens[invitation.id] = invitation.token
        else:
            invitation_id = str(pending[0])
            token = known_tokens.get(invitation_id)
            if token is None:
                # A pending row is only created by this loop, so this branch is
                # an explicit guard against a model/token bookkeeping mismatch.
                raise AssertionError("model lost a pending invitation token")
            if rng.choice([True, False]):
                assert outcome(
                    lambda candidate=candidate, token=token: harness.service.accept_invitation(
                        candidate.token,
                        {"token": token},
                        client_key=f"model-accept-{candidate.session.user.username}",
                    )
                ) == "OK"
            else:
                assert harness.service.revoke_invitation(owner.token, community.id, invitation_id).state.value == "REVOKED"
        check_invariants()

    # The model run must leave only durable, redacted audit JSON.
    events = harness.service.list_audit_events(owner.token, community.id, 200)
    assert all(isinstance(event.metadata, dict) for event in events)
    assert all("token" not in json.dumps(event.metadata).casefold() for event in events)
