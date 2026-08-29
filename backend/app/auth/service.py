"""Persistent identity, community, RBAC and invitation state machine.

The HTTP adapter is intentionally kept outside this module.  This service owns
the durable state transitions and returns the strict view models consumed by
that adapter.  Secrets are accepted only at the operation boundary: sessions
and invitations are stored as SHA-256 digests and audit metadata is assembled
from a small, non-secret allow-list.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from math import ceil
from typing import Any, TypeVar

from app.auth.config import AuthSettings
from app.auth.crypto import (
    hash_password,
    is_supported_password_hash,
    normalize_email,
    normalize_username,
    new_bearer_token,
    opaque_bucket,
    token_digest,
    verify_password,
)
from app.auth.errors import AuthProblem, authentication_required, invitation_not_available, permission_denied
from app.auth.models import (
    ROLE_PERMISSIONS,
    AuditEventView,
    CommunityCreateRequest,
    CommunityRole,
    CommunityView,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationCreatedView,
    InvitationState,
    InvitationView,
    LoginRequest,
    MembershipView,
    PasswordChangeRequest,
    Permission,
    ProfileUpdateRequest,
    RoleChangeRequest,
    SessionView,
    SignupRequest,
    UserView,
)
from app.auth.storage import AuthStore


_Request = TypeVar("_Request")
_DUMMY_PASSWORD_HASH = hash_password("Assemble-Dummy-Password9!")


def _problem(status_code: int, code: str, message: str, *, retry_after: int | None = None) -> AuthProblem:
    return AuthProblem(status_code, code, message, {}, retry_after=retry_after)


def account_unavailable() -> AuthProblem:
    return _problem(409, "ACCOUNT_UNAVAILABLE", "The supplied account identity is unavailable.")


def authentication_failed() -> AuthProblem:
    return _problem(401, "AUTHENTICATION_FAILED", "The supplied credentials are not valid.")


def community_unavailable() -> AuthProblem:
    return _problem(409, "COMMUNITY_UNAVAILABLE", "The supplied community is unavailable.")


def community_not_found() -> AuthProblem:
    return _problem(404, "COMMUNITY_NOT_FOUND", "The requested community was not found.")


def membership_exists() -> AuthProblem:
    return _problem(409, "MEMBERSHIP_EXISTS", "The recipient is already a community member.")


def pending_invitation_exists() -> AuthProblem:
    return _problem(409, "PENDING_INVITATION_EXISTS", "A pending invitation already covers the recipient.")


def membership_not_found() -> AuthProblem:
    return _problem(404, "MEMBERSHIP_NOT_FOUND", "The requested membership was not found.")


def invitation_not_pending() -> AuthProblem:
    return _problem(409, "INVITATION_NOT_PENDING", "The invitation is no longer pending.")


def last_administrator_required() -> AuthProblem:
    return _problem(409, "LAST_ADMINISTRATOR_REQUIRED", "The community must retain an Administrator.")


def invalid_request(message: str = "The request is invalid.") -> AuthProblem:
    return _problem(422, "INVALID_REQUEST", message)


def rate_limited(retry_after: int) -> AuthProblem:
    return _problem(429, "RATE_LIMITED", "Too many requests. Try again later.", retry_after=retry_after)


@dataclass(frozen=True, slots=True)
class SessionResult:
    """A session response plus the one-time raw cookie value.

    The raw token is deliberately kept out of :class:`SessionView`; the API
    adapter puts it in an HttpOnly cookie and never serialises it as JSON.
    """

    session: SessionView
    token: str

    @property
    def view(self) -> SessionView:
        return self.session

    @property
    def session_token(self) -> str:
        return self.token

    @property
    def expires_at(self) -> int:
        return self.session.session_expires_at

    @property
    def session_expires_at(self) -> int:
        return self.session.session_expires_at

    def __iter__(self) -> Iterator[object]:
        yield self.session
        yield self.token


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """Current session identity used by the HTTP adapter and service helpers."""

    session_id: str
    user_id: str
    password_version: int
    expires_at: int
    user: UserView
    session: SessionView

    @property
    def view(self) -> SessionView:
        return self.session


class AuthService:
    """Implement the isolated local auth/community/invitation state machine."""

    def __init__(
        self,
        store: AuthStore,
        settings: AuthSettings | None = None,
        *,
        clock: Callable[[], int] | None = None,
        now: Callable[[], int] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if clock is not None and now is not None:
            raise TypeError("provide clock or now, not both")
        self.store = store
        self.settings = settings or AuthSettings(database_path=store.database_path)
        self._clock = clock or now or (lambda: int(time.time()))
        self._token_factory = token_factory or new_bearer_token

    # ------------------------------------------------------------------
    # Small boundary helpers
    # ------------------------------------------------------------------
    def _now(self) -> int:
        return int(self._clock())

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex

    def _new_token(self) -> str:
        token = self._token_factory()
        if (
            not isinstance(token, str)
            or not (40 <= len(token) <= 128)
            or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in token)
        ):
            raise ValueError("token factory must return a 40-128 character URL-safe bearer")
        return token

    @staticmethod
    def _value(request: object, name: str, default: Any = None) -> Any:
        if isinstance(request, Mapping):
            return request.get(name, default)
        return getattr(request, name, default)

    @classmethod
    def _coerce(cls, model_type: type[_Request], request: _Request | Mapping[str, Any] | None, values: Mapping[str, Any]) -> _Request:
        if request is None:
            payload = dict(values)
        elif isinstance(request, Mapping):
            payload = dict(request)
            payload.update(values)
        else:
            if values:
                raise TypeError("keyword request fields cannot accompany a request model")
            payload = request
        model_validate = getattr(model_type, "model_validate", None)
        if model_validate is None:
            return payload  # pragma: no cover - all current request types are Pydantic models
        return model_validate(payload)

    @staticmethod
    def _field_supplied(request: object, field_name: str) -> bool:
        fields_set = getattr(request, "model_fields_set", None)
        if fields_set is None:
            fields_set = getattr(request, "__fields_set__", None)
        if fields_set is not None:
            return field_name in fields_set
        return isinstance(request, Mapping) and field_name in request

    @staticmethod
    def _password_for_dummy(password: object) -> str:
        value = password if isinstance(password, str) else str(password)
        # Request models cap this at 128 characters.  Keeping the defensive
        # bound here ensures malformed direct service calls still execute the
        # equivalent bounded scrypt work rather than taking an early byte-size
        # return from verify_password.
        return value[:128]

    @staticmethod
    def _supported_stored_hash(encoded: object) -> bool:
        return is_supported_password_hash(encoded)

    # ------------------------------------------------------------------
    # Audit and rate limiting
    # ------------------------------------------------------------------
    @staticmethod
    def _audit_metadata(metadata: Mapping[str, Any]) -> str:
        """Serialise only metadata this module explicitly considers safe."""

        forbidden = {"password", "password_hash", "hash", "token", "token_hash", "digest", "recipient"}

        def check(value: Any, key: str | None = None) -> None:
            if key is not None and key.casefold() in forbidden:
                raise ValueError(f"forbidden audit metadata key: {key}")
            if isinstance(value, Mapping):
                for nested_key, nested_value in value.items():
                    check(nested_value, str(nested_key))
            elif isinstance(value, (list, tuple)):
                for nested in value:
                    check(nested)

        clean = dict(metadata)
        check(clean)
        return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _audit(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        *,
        actor_user_id: str | None = None,
        subject_user_id: str | None = None,
        community_id: str | None = None,
        invitation_id: str | None = None,
        occurred_at: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        once: bool = False,
    ) -> None:
        metadata_json = self._audit_metadata(metadata or {})
        if once:
            existing = connection.execute(
                "SELECT 1 FROM audit_events WHERE event_type = ? AND metadata_json = ? LIMIT 1",
                (event_type, metadata_json),
            ).fetchone()
            if existing is not None:
                return
        connection.execute(
            """
            INSERT INTO audit_events(
                id, event_type, actor_user_id, subject_user_id, community_id,
                invitation_id, occurred_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._new_id(),
                event_type,
                actor_user_id,
                subject_user_id,
                community_id,
                invitation_id,
                self._now() if occurred_at is None else occurred_at,
                metadata_json,
            ),
        )

    def _consume_rate_limits(
        self,
        connection: sqlite3.Connection,
        scope: str,
        client_key: object,
        identities: Iterator[str] | tuple[str, ...] | list[str],
        now: int,
    ) -> int | None:
        """Increment all client/identity buckets and return retry seconds.

        The caller remains inside the transaction.  Returning instead of
        raising is important: a rejected request must still commit its durable
        counter and rate-limit audit event.
        """

        identity_values = [str(identity) for identity in identities if identity]
        bucket_inputs: list[tuple[str, str]] = [("client", str(client_key))]
        bucket_inputs.extend(("identity", value) for value in identity_values)
        bucket_hashes: list[tuple[str, str]] = []
        seen: set[str] = set()
        for kind, value in bucket_inputs:
            bucket_hash = opaque_bucket("auth-rate", scope, kind, value)
            if bucket_hash in seen:
                continue
            seen.add(bucket_hash)
            bucket_hashes.append((bucket_hash, kind))

        blocked = False
        retry_at = now + 1
        states: list[tuple[str, int, int]] = []
        for bucket_hash, _ in bucket_hashes:
            row = connection.execute(
                "SELECT window_start, count FROM rate_limits WHERE bucket_hash = ?",
                (bucket_hash,),
            ).fetchone()
            if row is None or now >= int(row["window_start"]) + self.settings.rate_limit_window_seconds:
                window_start, count = now, 0
            else:
                window_start, count = int(row["window_start"]), int(row["count"])
            states.append((bucket_hash, window_start, count))
            if count >= self.settings.rate_limit_attempts:
                blocked = True
                retry_at = max(retry_at, window_start + self.settings.rate_limit_window_seconds)

        for bucket_hash, window_start, count in states:
            updated_count = count + 1
            connection.execute(
                """
                INSERT INTO rate_limits(bucket_hash, window_start, count) VALUES (?, ?, ?)
                ON CONFLICT(bucket_hash) DO UPDATE SET window_start = excluded.window_start, count = excluded.count
                """,
                (bucket_hash, window_start, updated_count),
            )
        if not blocked:
            return None
        return max(1, ceil(retry_at - now))

    # ------------------------------------------------------------------
    # View conversion helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _user_view(row: sqlite3.Row) -> UserView:
        return UserView(
            id=str(row["user_id"] if "user_id" in row.keys() else row["id"]),
            username=str(row["username"]),
            email=row["email"],
            display_name=row["display_name"],
            avatar_url=row["avatar_url"],
        )

    @staticmethod
    def _membership_view(row: sqlite3.Row) -> MembershipView:
        return MembershipView(
            community_id=str(row["community_id"]),
            community_name=str(row["community_name"]),
            community_slug=str(row["community_slug"]),
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            role=CommunityRole(str(row["role"])),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
        )

    @staticmethod
    def _invitation_view(row: sqlite3.Row) -> InvitationView:
        return InvitationView(
            id=str(row["id"]),
            community_id=str(row["community_id"]),
            role=CommunityRole(str(row["role"])),
            inviter_user_id=str(row["inviter_user_id"]),
            recipient_kind=str(row["recipient_kind"]),
            recipient=str(row["recipient"]),
            state=InvitationState(str(row["state"])),
            created_at=int(row["created_at"]),
            expires_at=int(row["expires_at"]),
            accepted_by_user_id=row["accepted_by_user_id"],
            accepted_at=row["accepted_at"],
            revoked_at=row["revoked_at"],
        )

    def _membership_rows(self, connection: sqlite3.Connection, user_id: str) -> list[MembershipView]:
        rows = connection.execute(
            """
            SELECT m.community_id, c.name AS community_name, c.slug AS community_slug,
                   m.user_id, u.username, m.role, m.created_at, m.updated_at
            FROM memberships AS m
            JOIN communities AS c ON c.id = m.community_id
            JOIN users AS u ON u.id = m.user_id
            WHERE m.user_id = ?
            ORDER BY c.slug, c.id
            """,
            (user_id,),
        ).fetchall()
        return [self._membership_view(row) for row in rows]

    def _session_view(self, connection: sqlite3.Connection, user_row: sqlite3.Row, expires_at: int) -> SessionView:
        user = UserView(
            id=str(user_row["id"]),
            username=str(user_row["username"]),
            email=user_row["email"],
            display_name=user_row["display_name"],
            avatar_url=user_row["avatar_url"],
        )
        return SessionView(
            user=user,
            memberships=self._membership_rows(connection, str(user_row["id"])),
            session_expires_at=int(expires_at),
        )

    def _insert_session(
        self,
        connection: sqlite3.Connection,
        *,
        user_id: str,
        password_version: int,
        created_at: int,
    ) -> tuple[str, int]:
        token = self._new_token()
        expires_at = created_at + self.settings.session_ttl_seconds
        connection.execute(
            """
            INSERT INTO sessions(
                id, token_hash, user_id, password_version, created_at,
                last_seen_at, expires_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                self._new_id(),
                token_digest(token),
                user_id,
                password_version,
                created_at,
                created_at,
                expires_at,
            ),
        )
        return token, expires_at

    # ------------------------------------------------------------------
    # Session authentication
    # ------------------------------------------------------------------
    @staticmethod
    def _session_query() -> str:
        return """
            SELECT s.id AS session_id, s.token_hash, s.user_id,
                   s.password_version AS session_password_version,
                   s.expires_at, s.revoked_at,
                   u.id, u.username, u.email, u.display_name, u.avatar_url,
                   u.password_version AS current_password_version
            FROM sessions AS s
            JOIN users AS u ON u.id = s.user_id
            WHERE s.token_hash = ?
        """

    def _require_authenticated(self, session_token: str | None) -> AuthenticatedSession:
        if not session_token:
            raise authentication_required()
        now = self._now()
        rejected = False
        context: AuthenticatedSession | None = None
        with self.store.transaction(immediate=True) as connection:
            row = connection.execute(self._session_query(), (token_digest(str(session_token)),)).fetchone()
            if row is None:
                # Unknown random cookies intentionally create no audit event.
                rejected = True
            else:
                reason: str | None = None
                if row["revoked_at"] is not None:
                    reason = "REVOKED"
                elif now >= int(row["expires_at"]):
                    reason = "EXPIRED"
                elif int(row["session_password_version"]) != int(row["current_password_version"]):
                    reason = "PASSWORD_CHANGED"
                if reason is not None:
                    self._audit(
                        connection,
                        "SESSION_REJECTED",
                        subject_user_id=str(row["user_id"]),
                        occurred_at=now,
                        metadata={"reason": reason, "session_id": str(row["session_id"])},
                        once=True,
                    )
                    rejected = True
                else:
                    connection.execute(
                        "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
                        (now, row["session_id"]),
                    )
                    user = UserView(
                        id=str(row["id"]),
                        username=str(row["username"]),
                        email=row["email"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                    )
                    view = self._session_view(connection, row, int(row["expires_at"]))
                    context = AuthenticatedSession(
                        session_id=str(row["session_id"]),
                        user_id=str(row["user_id"]),
                        password_version=int(row["current_password_version"]),
                        expires_at=int(row["expires_at"]),
                        user=user,
                        session=view,
                    )
        if rejected or context is None:
            raise authentication_required()
        return context

    def session(self, session_token: str | None) -> SessionView:
        return self._require_authenticated(session_token).session

    get_session = session

    def logout(self, session_token: str | None) -> None:
        if not session_token:
            return
        now = self._now()
        with self.store.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT id, user_id, revoked_at FROM sessions WHERE token_hash = ?",
                (token_digest(str(session_token)),),
            ).fetchone()
            if row is None:
                return
            if row["revoked_at"] is None:
                connection.execute("UPDATE sessions SET revoked_at = ? WHERE id = ?", (now, row["id"]))
                self._audit(
                    connection,
                    "LOGOUT",
                    actor_user_id=str(row["user_id"]),
                    occurred_at=now,
                    metadata={"session_id": str(row["id"])},
                )

    # ------------------------------------------------------------------
    # Public identity operations
    # ------------------------------------------------------------------
    def signup(
        self,
        request: SignupRequest | Mapping[str, Any] | None = None,
        client_key: str = "",
        **values: Any,
    ) -> SessionResult:
        request = self._coerce(SignupRequest, request, values)
        username = normalize_username(str(self._value(request, "username")))
        email_value = self._value(request, "email")
        email = normalize_email(email_value) if email_value is not None else None
        password = str(self._value(request, "password"))
        display_name = self._value(request, "display_name")
        now = self._now()
        retry_after: int | None = None
        conflict = False
        result: SessionResult | None = None
        with self.store.transaction(immediate=True) as connection:
            identities = [username] + ([email] if email is not None else [])
            retry_after = self._consume_rate_limits(connection, "signup", client_key, iter(identities), now)
            if retry_after is not None:
                self._audit(
                    connection,
                    "RATE_LIMIT_REJECTED",
                    occurred_at=now,
                    metadata={"scope": "signup", "reason": "RATE_LIMIT"},
                    once=True,
                )
            else:
                existing = connection.execute(
                    "SELECT id FROM users WHERE username = ? OR (? IS NOT NULL AND email = ?)",
                    (username, email, email),
                ).fetchone()
                if existing is not None:
                    conflict = True
                else:
                    user_id = self._new_id()
                    password_hash = hash_password(password)
                    connection.execute(
                        """
                        INSERT INTO users(
                            id, username, email, password_hash, password_version,
                            display_name, avatar_url, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 1, ?, NULL, ?, ?)
                        """,
                        (user_id, username, email, password_hash, display_name, now, now),
                    )
                    self._audit(
                        connection,
                        "ACCOUNT_CREATED",
                        subject_user_id=user_id,
                        occurred_at=now,
                        metadata={"has_email": email is not None},
                    )
                    token, expires_at = self._insert_session(
                        connection,
                        user_id=user_id,
                        password_version=1,
                        created_at=now,
                    )
                    user_row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                    assert user_row is not None
                    result = SessionResult(self._session_view(connection, user_row, expires_at), token)
        if retry_after is not None:
            raise rate_limited(retry_after)
        if conflict:
            raise account_unavailable()
        assert result is not None
        return result

    def login(
        self,
        request: LoginRequest | Mapping[str, Any] | None = None,
        client_key: str = "",
        **values: Any,
    ) -> SessionResult:
        request = self._coerce(LoginRequest, request, values)
        identity = str(self._value(request, "identity"))
        password = self._value(request, "password")
        now = self._now()
        retry_after: int | None = None
        user_row: sqlite3.Row | None = None
        with self.store.transaction(immediate=True) as connection:
            retry_after = self._consume_rate_limits(connection, "login", client_key, iter((identity,)), now)
            if retry_after is not None:
                self._audit(
                    connection,
                    "RATE_LIMIT_REJECTED",
                    occurred_at=now,
                    metadata={"scope": "login", "reason": "RATE_LIMIT"},
                    once=True,
                )
            else:
                if "@" in identity:
                    user_row = connection.execute("SELECT * FROM users WHERE email = ?", (normalize_email(identity),)).fetchone()
                else:
                    user_row = connection.execute("SELECT * FROM users WHERE username = ?", (normalize_username(identity),)).fetchone()

        if retry_after is not None:
            raise rate_limited(retry_after)

        valid = False
        failure_reason = "BAD_CREDENTIALS"
        if user_row is None:
            verify_password(self._password_for_dummy(password), _DUMMY_PASSWORD_HASH)
            failure_reason = "UNKNOWN_IDENTITY"
        elif not self._supported_stored_hash(user_row["password_hash"]):
            verify_password(self._password_for_dummy(password), _DUMMY_PASSWORD_HASH)
            failure_reason = "MALFORMED_STORED_HASH"
        else:
            valid = verify_password(str(password), str(user_row["password_hash"]))

        if not valid:
            with self.store.transaction(immediate=True) as connection:
                self._audit(connection, "LOGIN_FAILED", occurred_at=now, metadata={"reason": failure_reason})
            raise authentication_failed()

        verified_password_hash = str(user_row["password_hash"])
        verified_password_version = int(user_row["password_version"])
        with self.store.transaction(immediate=True) as connection:
            current = connection.execute("SELECT * FROM users WHERE id = ?", (user_row["id"],)).fetchone()
            if current is None:
                self._audit(connection, "LOGIN_FAILED", occurred_at=now, metadata={"reason": "UNKNOWN_IDENTITY"})
                # This branch only becomes possible if a concurrent delete is
                # added later; keep the public error generic.
                result = None
            elif (
                str(current["password_hash"]) != verified_password_hash
                or int(current["password_version"]) != verified_password_version
            ):
                self._audit(
                    connection,
                    "LOGIN_FAILED",
                    subject_user_id=str(current["id"]),
                    occurred_at=now,
                    metadata={"reason": "CREDENTIAL_CHANGED_DURING_LOGIN"},
                )
                result = None
            else:
                token, expires_at = self._insert_session(
                    connection,
                    user_id=str(current["id"]),
                    password_version=int(current["password_version"]),
                    created_at=now,
                )
                self._audit(
                    connection,
                    "LOGIN_SUCCEEDED",
                    actor_user_id=str(current["id"]),
                    occurred_at=now,
                    metadata={"identity_kind": "email" if "@" in identity else "username"},
                )
                result = SessionResult(self._session_view(connection, current, expires_at), token)
        if result is None:
            raise authentication_failed()
        return result

    def change_password(
        self,
        session_token: str,
        request: PasswordChangeRequest | Mapping[str, Any] | None = None,
        client_key: str = "",
        **values: Any,
    ) -> SessionResult:
        request = self._coerce(PasswordChangeRequest, request, values)
        context = self._require_authenticated(session_token)
        current_password = str(self._value(request, "current_password"))
        new_password = str(self._value(request, "new_password"))
        now = self._now()
        valid = False
        retry_after: int | None = None
        result: SessionResult | None = None
        with self.store.transaction(immediate=True) as connection:
            retry_after = self._consume_rate_limits(
                connection,
                "password_change",
                client_key,
                iter((context.user_id,)),
                now,
            )
            if retry_after is not None:
                self._audit(
                    connection,
                    "RATE_LIMIT_REJECTED",
                    actor_user_id=context.user_id,
                    occurred_at=now,
                    metadata={"scope": "password_change", "reason": "RATE_LIMIT"},
                    once=True,
                )
            else:
                row = connection.execute("SELECT * FROM users WHERE id = ?", (context.user_id,)).fetchone()
                if row is not None:
                    valid = verify_password(current_password, str(row["password_hash"]))
                if row is not None and valid:
                    new_hash = hash_password(new_password)
                    next_version = int(row["password_version"]) + 1
                    connection.execute(
                        "UPDATE users SET password_hash = ?, password_version = ?, updated_at = ? WHERE id = ?",
                        (new_hash, next_version, now, context.user_id),
                    )
                    connection.execute(
                        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                        (now, context.user_id),
                    )
                    token, expires_at = self._insert_session(
                        connection,
                        user_id=context.user_id,
                        password_version=next_version,
                        created_at=now,
                    )
                    self._audit(
                        connection,
                        "PASSWORD_CHANGED",
                        actor_user_id=context.user_id,
                        occurred_at=now,
                        metadata={"session_rotation": True},
                    )
                    updated = connection.execute("SELECT * FROM users WHERE id = ?", (context.user_id,)).fetchone()
                    assert updated is not None
                    result = SessionResult(self._session_view(connection, updated, expires_at), token)
        if retry_after is not None:
            raise rate_limited(retry_after)
        if not valid or result is None:
            with self.store.transaction(immediate=True) as connection:
                self._audit(connection, "PASSWORD_CHANGE_FAILED", actor_user_id=context.user_id, occurred_at=now, metadata={"reason": "BAD_CURRENT_PASSWORD"})
            raise authentication_failed()
        return result

    password_change = change_password

    def update_profile(
        self,
        session_token: str,
        request: ProfileUpdateRequest | Mapping[str, Any] | None = None,
        **values: Any,
    ) -> UserView:
        request = self._coerce(ProfileUpdateRequest, request, values)
        context = self._require_authenticated(session_token)
        display_supplied = self._field_supplied(request, "display_name")
        avatar_supplied = self._field_supplied(request, "avatar_url")
        now = self._now()
        with self.store.transaction(immediate=True) as connection:
            assignments: list[str] = []
            parameters: list[Any] = []
            if display_supplied:
                assignments.append("display_name = ?")
                parameters.append(self._value(request, "display_name"))
            if avatar_supplied:
                assignments.append("avatar_url = ?")
                parameters.append(self._value(request, "avatar_url"))
            if assignments:
                assignments.append("updated_at = ?")
                parameters.extend((now, context.user_id))
                connection.execute(
                    f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
                    parameters,
                )
                self._audit(
                    connection,
                    "PROFILE_UPDATED",
                    actor_user_id=context.user_id,
                    occurred_at=now,
                    metadata={"fields": sorted(name for name, supplied in (("display_name", display_supplied), ("avatar_url", avatar_supplied)) if supplied)},
                )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (context.user_id,)).fetchone()
            assert row is not None
            return UserView(
                id=str(row["id"]),
                username=str(row["username"]),
                email=row["email"],
                display_name=row["display_name"],
                avatar_url=row["avatar_url"],
            )

    # ------------------------------------------------------------------
    # Community membership and RBAC
    # ------------------------------------------------------------------
    def _community_access(
        self,
        connection: sqlite3.Connection,
        *,
        user_id: str,
        community_id: str,
        permission: Permission,
        admin_operation: bool = False,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT c.id AS community_id, c.name AS community_name, c.slug AS community_slug,
                   c.created_at AS community_created_at, m.user_id, m.role,
                   m.created_at AS membership_created_at, m.updated_at AS membership_updated_at
            FROM communities AS c
            LEFT JOIN memberships AS m ON m.community_id = c.id AND m.user_id = ?
            WHERE c.id = ?
            """,
            (user_id, community_id),
        ).fetchone()
        if row is None or row["user_id"] is None:
            # Administrator-only operations deliberately do not disclose
            # whether a non-member knows a real community ID.
            raise community_not_found()
        role = CommunityRole(str(row["role"]))
        if permission not in ROLE_PERMISSIONS[role]:
            raise permission_denied()
        return row

    def create_community(
        self,
        session_token: str,
        request: CommunityCreateRequest | Mapping[str, Any] | None = None,
        **values: Any,
    ) -> CommunityView:
        request = self._coerce(CommunityCreateRequest, request, values)
        context = self._require_authenticated(session_token)
        name = str(self._value(request, "name"))
        slug = str(self._value(request, "slug"))
        now = self._now()
        duplicate = False
        result: CommunityView | None = None
        with self.store.transaction(immediate=True) as connection:
            community_id = self._new_id()
            try:
                connection.execute(
                    """
                    INSERT INTO communities(id, name, slug, created_by_user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (community_id, name, slug, context.user_id, now, now),
                )
            except sqlite3.IntegrityError:
                duplicate = True
            if not duplicate:
                connection.execute(
                    """
                    INSERT INTO memberships(
                        community_id, user_id, role, invited_by_user_id, created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, ?, ?)
                    """,
                    (community_id, context.user_id, CommunityRole.ADMINISTRATOR.value, now, now),
                )
                self._audit(
                    connection,
                    "COMMUNITY_CREATED",
                    actor_user_id=context.user_id,
                    community_id=community_id,
                    occurred_at=now,
                    metadata={"community_id": community_id},
                )
                self._audit(
                    connection,
                    "MEMBERSHIP_CREATED",
                    actor_user_id=context.user_id,
                    subject_user_id=context.user_id,
                    community_id=community_id,
                    occurred_at=now,
                    metadata={"role": CommunityRole.ADMINISTRATOR.value, "reason": "COMMUNITY_CREATOR"},
                )
                result = CommunityView(
                    id=community_id,
                    name=name,
                    slug=slug,
                    role=CommunityRole.ADMINISTRATOR,
                    created_at=now,
                )
        if duplicate:
            raise community_unavailable()
        assert result is not None
        return result

    def list_communities(self, session_token: str) -> list[CommunityView]:
        context = self._require_authenticated(session_token)
        with self.store.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.name, c.slug, c.created_at, m.role
                FROM memberships AS m
                JOIN communities AS c ON c.id = m.community_id
                WHERE m.user_id = ?
                ORDER BY c.slug, c.id
                """,
                (context.user_id,),
            ).fetchall()
            return [
                CommunityView(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    slug=str(row["slug"]),
                    role=CommunityRole(str(row["role"])),
                    created_at=int(row["created_at"]),
                )
                for row in rows
            ]

    get_communities = list_communities

    def get_community(self, session_token: str, community_id: str) -> CommunityView:
        context = self._require_authenticated(session_token)
        with self.store.transaction() as connection:
            row = self._community_access(
                connection,
                user_id=context.user_id,
                community_id=str(community_id),
                permission=Permission.COMMUNITY_READ,
            )
            return CommunityView(
                id=str(row["community_id"]),
                name=str(row["community_name"]),
                slug=str(row["community_slug"]),
                role=CommunityRole(str(row["role"])),
                created_at=int(row["community_created_at"]),
            )

    def list_members(self, session_token: str, community_id: str) -> list[MembershipView]:
        context = self._require_authenticated(session_token)
        with self.store.transaction() as connection:
            self._community_access(
                connection,
                user_id=context.user_id,
                community_id=str(community_id),
                permission=Permission.MEMBERS_LIST,
                admin_operation=True,
            )
            rows = connection.execute(
                """
                SELECT m.community_id, c.name AS community_name, c.slug AS community_slug,
                       m.user_id, u.username, m.role, m.created_at, m.updated_at
                FROM memberships AS m
                JOIN communities AS c ON c.id = m.community_id
                JOIN users AS u ON u.id = m.user_id
                WHERE m.community_id = ?
                ORDER BY u.username, u.id
                """,
                (community_id,),
            ).fetchall()
            return [self._membership_view(row) for row in rows]

    members = list_members

    @staticmethod
    def _role_request(request: RoleChangeRequest | CommunityRole | Mapping[str, Any]) -> CommunityRole:
        if isinstance(request, CommunityRole):
            return request
        if isinstance(request, Mapping):
            request = RoleChangeRequest.model_validate(request)
        role = getattr(request, "role", request)
        try:
            return role if isinstance(role, CommunityRole) else CommunityRole(str(role))
        except ValueError as exc:
            raise invalid_request("The role is invalid.") from exc

    def change_member_role(
        self,
        session_token: str,
        community_id: str,
        user_id: str,
        request: RoleChangeRequest | CommunityRole | Mapping[str, Any],
    ) -> MembershipView:
        context = self._require_authenticated(session_token)
        next_role = self._role_request(request)
        now = self._now()
        result: MembershipView | None = None
        last_admin = False
        target_missing = False
        with self.store.transaction(immediate=True) as connection:
            self._community_access(
                connection,
                user_id=context.user_id,
                community_id=str(community_id),
                permission=Permission.MEMBERS_ROLE_CHANGE,
                admin_operation=True,
            )
            target = connection.execute(
                """
                SELECT m.community_id, c.name AS community_name, c.slug AS community_slug,
                       m.user_id, u.username, m.role, m.created_at, m.updated_at
                FROM memberships AS m
                JOIN communities AS c ON c.id = m.community_id
                JOIN users AS u ON u.id = m.user_id
                WHERE m.community_id = ? AND m.user_id = ?
                """,
                (community_id, user_id),
            ).fetchone()
            if target is None:
                target_missing = True
            else:
                previous_role = CommunityRole(str(target["role"]))
                if previous_role == CommunityRole.ADMINISTRATOR and next_role != CommunityRole.ADMINISTRATOR:
                    self._expire_pending(connection, str(community_id), now)
                    admin_count = connection.execute(
                        "SELECT COUNT(*) AS count FROM memberships WHERE community_id = ? AND role = ?",
                        (community_id, CommunityRole.ADMINISTRATOR.value),
                    ).fetchone()
                    if admin_count is None or int(admin_count["count"]) <= 1:
                        last_admin = True
                    else:
                        connection.execute(
                            "UPDATE memberships SET role = ?, updated_at = ? WHERE community_id = ? AND user_id = ?",
                            (next_role.value, now, community_id, user_id),
                        )
                        pending_rows = connection.execute(
                            """
                            SELECT id FROM invitations
                            WHERE community_id = ? AND inviter_user_id = ? AND state = ?
                            ORDER BY created_at, id
                            """,
                            (community_id, user_id, InvitationState.PENDING.value),
                        ).fetchall()
                        connection.execute(
                            """
                            UPDATE invitations SET state = ?, revoked_at = ?
                            WHERE community_id = ? AND inviter_user_id = ? AND state = ?
                            """,
                            (
                                InvitationState.REVOKED.value,
                                now,
                                community_id,
                                user_id,
                                InvitationState.PENDING.value,
                            ),
                        )
                        for invitation in pending_rows:
                            self._audit(
                                connection,
                                "INVITATION_REVOKED",
                                actor_user_id=context.user_id,
                                subject_user_id=user_id,
                                community_id=str(community_id),
                                invitation_id=str(invitation["id"]),
                                occurred_at=now,
                                metadata={"reason": "INVITER_NO_LONGER_AUTHORISED"},
                            )
                        self._audit(
                            connection,
                            "MEMBERSHIP_ROLE_CHANGED",
                            actor_user_id=context.user_id,
                            subject_user_id=str(user_id),
                            community_id=str(community_id),
                            occurred_at=now,
                            metadata={"from_role": previous_role.value, "to_role": next_role.value},
                        )
                elif previous_role != next_role:
                    connection.execute(
                        "UPDATE memberships SET role = ?, updated_at = ? WHERE community_id = ? AND user_id = ?",
                        (next_role.value, now, community_id, user_id),
                    )
                    self._audit(
                        connection,
                        "MEMBERSHIP_ROLE_CHANGED",
                        actor_user_id=context.user_id,
                        subject_user_id=str(user_id),
                        community_id=str(community_id),
                        occurred_at=now,
                        metadata={"from_role": previous_role.value, "to_role": next_role.value},
                    )
                refreshed = connection.execute(
                    """
                    SELECT m.community_id, c.name AS community_name, c.slug AS community_slug,
                           m.user_id, u.username, m.role, m.created_at, m.updated_at
                    FROM memberships AS m
                    JOIN communities AS c ON c.id = m.community_id
                    JOIN users AS u ON u.id = m.user_id
                    WHERE m.community_id = ? AND m.user_id = ?
                    """,
                    (community_id, user_id),
                ).fetchone()
                assert refreshed is not None
                result = self._membership_view(refreshed)
        if target_missing:
            raise membership_not_found()
        if last_admin:
            raise last_administrator_required()
        assert result is not None
        return result

    change_role = change_member_role
    update_member_role = change_member_role

    # ------------------------------------------------------------------
    # Invitations
    # ------------------------------------------------------------------
    @staticmethod
    def _recipient_details(recipient: str) -> tuple[str, str]:
        if "@" in recipient:
            return "email", normalize_email(recipient)
        return "username", normalize_username(recipient)

    def _community_admin_row(
        self,
        connection: sqlite3.Connection,
        *,
        user_id: str,
        community_id: str,
    ) -> sqlite3.Row:
        return self._community_access(
            connection,
            user_id=user_id,
            community_id=community_id,
            permission=Permission.INVITATIONS_MANAGE,
            admin_operation=True,
        )

    def create_invitation(
        self,
        session_token: str,
        community_id: str,
        request: InvitationCreateRequest | Mapping[str, Any] | None = None,
        **values: Any,
    ) -> InvitationCreatedView:
        request = self._coerce(InvitationCreateRequest, request, values)
        context = self._require_authenticated(session_token)
        recipient_kind, recipient = self._recipient_details(str(self._value(request, "recipient")))
        role = CommunityRole(self._value(request, "role"))
        expires_in = int(self._value(request, "expires_in_seconds"))
        now = self._now()
        duplicate_member = False
        duplicate_pending = False
        result: InvitationCreatedView | None = None
        with self.store.transaction(immediate=True) as connection:
            self._community_admin_row(connection, user_id=context.user_id, community_id=str(community_id))
            self._expire_pending(connection, str(community_id), now)
            if recipient_kind == "email":
                member = connection.execute(
                    """
                    SELECT 1 FROM memberships AS m JOIN users AS u ON u.id = m.user_id
                    WHERE m.community_id = ? AND u.email = ?
                    """,
                    (community_id, recipient),
                ).fetchone()
            else:
                member = connection.execute(
                    """
                    SELECT 1 FROM memberships AS m JOIN users AS u ON u.id = m.user_id
                    WHERE m.community_id = ? AND u.username = ?
                    """,
                    (community_id, recipient),
                ).fetchone()
            if member is not None:
                duplicate_member = True
            else:
                pending = connection.execute(
                    """
                    SELECT id FROM invitations
                    WHERE community_id = ? AND recipient_kind = ? AND recipient = ? AND state = ?
                    """,
                    (community_id, recipient_kind, recipient, InvitationState.PENDING.value),
                ).fetchone()
                if pending is not None:
                    duplicate_pending = True
                else:
                    token = self._new_token()
                    invitation_id = self._new_id()
                    expires_at = now + expires_in
                    connection.execute(
                        """
                        INSERT INTO invitations(
                            id, token_hash, community_id, role, inviter_user_id,
                            recipient_kind, recipient, state, created_at, expires_at,
                            accepted_by_user_id, accepted_at, revoked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (
                            invitation_id,
                            token_digest(token),
                            community_id,
                            role.value,
                            context.user_id,
                            recipient_kind,
                            recipient,
                            InvitationState.PENDING.value,
                            now,
                            expires_at,
                        ),
                    )
                    self._audit(
                        connection,
                        "INVITATION_CREATED",
                        actor_user_id=context.user_id,
                        community_id=str(community_id),
                        invitation_id=invitation_id,
                        occurred_at=now,
                        metadata={"role": role.value, "recipient_kind": recipient_kind},
                    )
                    result = InvitationCreatedView(
                        id=invitation_id,
                        community_id=str(community_id),
                        role=role,
                        inviter_user_id=context.user_id,
                        recipient_kind=recipient_kind,
                        recipient=recipient,
                        state=InvitationState.PENDING,
                        created_at=now,
                        expires_at=expires_at,
                        accepted_by_user_id=None,
                        accepted_at=None,
                        revoked_at=None,
                        token=token,
                    )
        if duplicate_member:
            raise membership_exists()
        if duplicate_pending:
            raise pending_invitation_exists()
        assert result is not None
        return result

    create_invite = create_invitation

    def _expire_pending(self, connection: sqlite3.Connection, community_id: str, now: int) -> None:
        rows = connection.execute(
            """
            SELECT id FROM invitations
            WHERE community_id = ? AND state = ? AND ? >= expires_at
            ORDER BY created_at, id
            """,
            (community_id, InvitationState.PENDING.value, now),
        ).fetchall()
        if not rows:
            return
        connection.execute(
            """
            UPDATE invitations SET state = ?, revoked_at = NULL
            WHERE community_id = ? AND state = ? AND ? >= expires_at
            """,
            (InvitationState.EXPIRED.value, community_id, InvitationState.PENDING.value, now),
        )
        for row in rows:
            self._audit(
                connection,
                "INVITATION_EXPIRED",
                community_id=str(community_id),
                invitation_id=str(row["id"]),
                occurred_at=now,
                metadata={"reason": "EXPIRED"},
            )

    def list_invitations(self, session_token: str, community_id: str) -> list[InvitationView]:
        context = self._require_authenticated(session_token)
        now = self._now()
        with self.store.transaction(immediate=True) as connection:
            self._community_admin_row(connection, user_id=context.user_id, community_id=str(community_id))
            self._expire_pending(connection, str(community_id), now)
            rows = connection.execute(
                """
                SELECT id, community_id, role, inviter_user_id, recipient_kind, recipient,
                       state, created_at, expires_at, accepted_by_user_id, accepted_at, revoked_at
                FROM invitations
                WHERE community_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (community_id,),
            ).fetchall()
            return [self._invitation_view(row) for row in rows]

    list_invites = list_invitations

    def revoke_invitation(self, session_token: str, community_id: str, invitation_id: str) -> InvitationView:
        context = self._require_authenticated(session_token)
        now = self._now()
        result: InvitationView | None = None
        not_pending = False
        with self.store.transaction(immediate=True) as connection:
            self._community_admin_row(connection, user_id=context.user_id, community_id=str(community_id))
            row = connection.execute(
                """
                SELECT id, community_id, role, inviter_user_id, recipient_kind, recipient,
                       state, created_at, expires_at, accepted_by_user_id, accepted_at, revoked_at
                FROM invitations WHERE id = ? AND community_id = ?
                """,
                (invitation_id, community_id),
            ).fetchone()
            if row is None:
                raise invitation_not_available()
            if str(row["state"]) != InvitationState.PENDING.value:
                not_pending = True
            elif now >= int(row["expires_at"]):
                connection.execute(
                    "UPDATE invitations SET state = ?, revoked_at = NULL WHERE id = ?",
                    (InvitationState.EXPIRED.value, invitation_id),
                )
                self._audit(
                    connection,
                    "INVITATION_EXPIRED",
                    community_id=str(community_id),
                    invitation_id=str(invitation_id),
                    occurred_at=now,
                    metadata={"reason": "EXPIRED"},
                )
                not_pending = True
            else:
                connection.execute(
                    "UPDATE invitations SET state = ?, revoked_at = ? WHERE id = ?",
                    (InvitationState.REVOKED.value, now, invitation_id),
                )
                self._audit(
                    connection,
                    "INVITATION_REVOKED",
                    actor_user_id=context.user_id,
                    community_id=str(community_id),
                    invitation_id=str(invitation_id),
                    occurred_at=now,
                    metadata={"reason": "ADMIN_REVOKED"},
                )
                refreshed = connection.execute(
                    """
                    SELECT id, community_id, role, inviter_user_id, recipient_kind, recipient,
                           state, created_at, expires_at, accepted_by_user_id, accepted_at, revoked_at
                    FROM invitations WHERE id = ?
                    """,
                    (invitation_id,),
                ).fetchone()
                assert refreshed is not None
                result = self._invitation_view(refreshed)
        if not_pending:
            raise invitation_not_pending()
        assert result is not None
        return result

    revoke_invite = revoke_invitation

    def accept_invitation(
        self,
        session_token: str,
        request: InvitationAcceptRequest | Mapping[str, Any] | None = None,
        client_key: str = "",
        **values: Any,
    ) -> MembershipView:
        request = self._coerce(InvitationAcceptRequest, request, values)
        context = self._require_authenticated(session_token)
        token = str(self._value(request, "token"))
        now = self._now()
        retry_after: int | None = None
        unavailable = False
        result: MembershipView | None = None
        with self.store.transaction(immediate=True) as connection:
            retry_after = self._consume_rate_limits(connection, "invitation_accept", client_key, iter((context.user_id,)), now)
            if retry_after is not None:
                self._audit(
                    connection,
                    "RATE_LIMIT_REJECTED",
                    actor_user_id=context.user_id,
                    occurred_at=now,
                    metadata={"scope": "invitation_accept", "reason": "RATE_LIMIT"},
                    once=True,
                )
            else:
                row = connection.execute(
                    """
                    SELECT id, token_hash, community_id, role, inviter_user_id, recipient_kind,
                           recipient, state, created_at, expires_at, accepted_by_user_id,
                           accepted_at, revoked_at
                    FROM invitations WHERE token_hash = ?
                    """,
                    (token_digest(token),),
                ).fetchone()
                if row is None:
                    unavailable = True
                elif str(row["state"]) != InvitationState.PENDING.value:
                    unavailable = True
                elif now >= int(row["expires_at"]):
                    connection.execute(
                        "UPDATE invitations SET state = ?, revoked_at = NULL WHERE id = ?",
                        (InvitationState.EXPIRED.value, row["id"]),
                    )
                    self._audit(
                        connection,
                        "INVITATION_EXPIRED",
                        community_id=str(row["community_id"]),
                        invitation_id=str(row["id"]),
                        occurred_at=now,
                        metadata={"reason": "EXPIRED"},
                    )
                    unavailable = True
                else:
                    recipient_matches = (
                        context.user.email is not None and str(row["recipient"]) == str(context.user.email)
                        if str(row["recipient_kind"]) == "email"
                        else str(row["recipient"]) == context.user.username
                    )
                    existing = connection.execute(
                        "SELECT 1 FROM memberships WHERE community_id = ? AND user_id = ?",
                        (row["community_id"], context.user_id),
                    ).fetchone()
                    if not recipient_matches or existing is not None:
                        unavailable = True
                    else:
                        connection.execute(
                            """
                            INSERT INTO memberships(
                                community_id, user_id, role, invited_by_user_id, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                row["community_id"],
                                context.user_id,
                                row["role"],
                                row["inviter_user_id"],
                                now,
                                now,
                            ),
                        )
                        connection.execute(
                            """
                            UPDATE invitations
                            SET state = ?, accepted_by_user_id = ?, accepted_at = ?
                            WHERE id = ? AND state = ?
                            """,
                            (
                                InvitationState.ACCEPTED.value,
                                context.user_id,
                                now,
                                row["id"],
                                InvitationState.PENDING.value,
                            ),
                        )
                        self._audit(
                            connection,
                            "MEMBERSHIP_CREATED",
                            actor_user_id=context.user_id,
                            subject_user_id=context.user_id,
                            community_id=str(row["community_id"]),
                            invitation_id=str(row["id"]),
                            occurred_at=now,
                            metadata={"role": str(row["role"]), "reason": "INVITATION_ACCEPTED"},
                        )
                        self._audit(
                            connection,
                            "INVITATION_ACCEPTED",
                            actor_user_id=context.user_id,
                            subject_user_id=context.user_id,
                            community_id=str(row["community_id"]),
                            invitation_id=str(row["id"]),
                            occurred_at=now,
                            metadata={"role": str(row["role"])},
                        )
                        membership = connection.execute(
                            """
                            SELECT m.community_id, c.name AS community_name, c.slug AS community_slug,
                                   m.user_id, u.username, m.role, m.created_at, m.updated_at
                            FROM memberships AS m
                            JOIN communities AS c ON c.id = m.community_id
                            JOIN users AS u ON u.id = m.user_id
                            WHERE m.community_id = ? AND m.user_id = ?
                            """,
                            (row["community_id"], context.user_id),
                        ).fetchone()
                        assert membership is not None
                        result = self._membership_view(membership)
        if retry_after is not None:
            raise rate_limited(retry_after)
        if unavailable or result is None:
            raise invitation_not_available()
        return result

    accept_invite = accept_invitation

    # ------------------------------------------------------------------
    # Audit inspection
    # ------------------------------------------------------------------
    def list_audit_events(self, session_token: str, community_id: str, limit: int = 100) -> list[AuditEventView]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 200):
            raise invalid_request("Audit limit must be between 1 and 200.")
        context = self._require_authenticated(session_token)
        with self.store.transaction() as connection:
            self._community_access(
                connection,
                user_id=context.user_id,
                community_id=str(community_id),
                permission=Permission.AUDIT_READ,
                admin_operation=True,
            )
            rows = connection.execute(
                """
                SELECT id, event_type, actor_user_id, subject_user_id, community_id,
                       invitation_id, occurred_at, metadata_json
                FROM audit_events
                WHERE community_id = ?
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (community_id, limit),
            ).fetchall()
            return [
                AuditEventView(
                    id=str(row["id"]),
                    event_type=str(row["event_type"]),
                    actor_user_id=row["actor_user_id"],
                    subject_user_id=row["subject_user_id"],
                    community_id=row["community_id"],
                    invitation_id=row["invitation_id"],
                    occurred_at=int(row["occurred_at"]),
                    metadata=json.loads(str(row["metadata_json"])),
                )
                for row in rows
            ]

    audit_events = list_audit_events


__all__ = [
    "AuthService",
    "AuthenticatedSession",
    "SessionResult",
    "account_unavailable",
    "authentication_failed",
    "community_not_found",
    "community_unavailable",
    "invalid_request",
    "invitation_not_pending",
    "last_administrator_required",
    "membership_exists",
    "membership_not_found",
    "pending_invitation_exists",
    "rate_limited",
]
