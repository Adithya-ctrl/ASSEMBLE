"""Numbered SQLite migrations for restart-safe local identity state."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            password_version INTEGER NOT NULL DEFAULT 1 CHECK (password_version >= 1),
            display_name TEXT,
            avatar_url TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            password_version INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            last_seen_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER
        );
        CREATE INDEX sessions_user_id_idx ON sessions(user_id);

        CREATE TABLE communities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            created_by_user_id TEXT NOT NULL REFERENCES users(id),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE memberships (
            community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('ADMINISTRATOR','COORDINATOR','MEMBER','VIEWER')),
            invited_by_user_id TEXT REFERENCES users(id),
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (community_id, user_id)
        );
        CREATE INDEX memberships_user_id_idx ON memberships(user_id);

        CREATE TABLE invitations (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            community_id TEXT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('ADMINISTRATOR','COORDINATOR','MEMBER','VIEWER')),
            inviter_user_id TEXT NOT NULL REFERENCES users(id),
            recipient_kind TEXT NOT NULL CHECK (recipient_kind IN ('username','email')),
            recipient TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('PENDING','ACCEPTED','REVOKED','EXPIRED')),
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            accepted_by_user_id TEXT REFERENCES users(id),
            accepted_at INTEGER,
            revoked_at INTEGER
        );
        CREATE INDEX invitations_community_recipient_idx
            ON invitations(community_id, recipient_kind, recipient, state);
        CREATE UNIQUE INDEX invitations_one_pending_recipient_idx
            ON invitations(community_id, recipient_kind, recipient)
            WHERE state = 'PENDING';

        CREATE TABLE rate_limits (
            bucket_hash TEXT PRIMARY KEY,
            window_start INTEGER NOT NULL,
            count INTEGER NOT NULL CHECK (count >= 0)
        );

        CREATE TABLE audit_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            actor_user_id TEXT REFERENCES users(id),
            subject_user_id TEXT REFERENCES users(id),
            community_id TEXT REFERENCES communities(id) ON DELETE SET NULL,
            invitation_id TEXT REFERENCES invitations(id) ON DELETE SET NULL,
            occurred_at INTEGER NOT NULL,
            metadata_json TEXT NOT NULL
        );
        CREATE INDEX audit_community_sequence_idx ON audit_events(community_id, sequence DESC);

        CREATE TRIGGER audit_events_append_only_update
        BEFORE UPDATE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit_events are append-only');
        END;

        CREATE TRIGGER audit_events_append_only_delete
        BEFORE DELETE ON audit_events
        BEGIN
            SELECT RAISE(ABORT, 'audit_events are append-only');
        END;
        """,
    ),
)


class MigrationError(RuntimeError):
    """Raised when the on-disk schema cannot be safely migrated."""


def _migration_versions() -> tuple[int, ...]:
    """Validate the migration catalogue before touching the database."""

    versions = tuple(version for version, _ in MIGRATIONS)
    if not versions:
        raise MigrationError("no database migrations are available")
    if any(version < 1 for version in versions):
        raise MigrationError("database migration versions must be positive")
    if versions != tuple(sorted(set(versions))):
        raise MigrationError("database migration versions must be unique and ordered")
    return versions


def _iter_statements(script: str) -> Iterator[str]:
    """Yield complete SQL statements without ``executescript`` autocommit.

    ``sqlite3.Connection.executescript`` commits any open transaction before it
    runs.  Migrations need the opposite guarantee, so statements are fed to
    ``Connection.execute`` one at a time while the caller owns a transaction.
    ``sqlite3.complete_statement`` also handles trigger bodies, whose internal
    semicolons must not split the trigger into invalid fragments.
    """

    buffer: list[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    index = 0

    while index < len(script):
        char = script[index]
        next_char = script[index + 1] if index + 1 < len(script) else ""
        buffer.append(char)

        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                buffer.append(next_char)
                index += 1
                block_comment = False
        elif quote is not None:
            if char == quote:
                if next_char == quote:
                    buffer.append(next_char)
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "[":
            quote = "]"
        elif char == "-" and next_char == "-":
            buffer.append(next_char)
            index += 1
            line_comment = True
        elif char == "/" and next_char == "*":
            buffer.append(next_char)
            index += 1
            block_comment = True
        elif char == ";":
            candidate = "".join(buffer)
            if sqlite3.complete_statement(candidate):
                if candidate.strip() and not _comment_only(candidate):
                    yield candidate
                buffer.clear()

        index += 1

    trailing = "".join(buffer)
    if trailing.strip() and not _comment_only(trailing):
        if sqlite3.complete_statement(f"{trailing};"):
            yield trailing
        else:
            raise MigrationError("database migration contains an incomplete SQL statement")


def _comment_only(statement: str) -> bool:
    """Return whether a statement contains comments/whitespace only."""

    index = 0
    while index < len(statement):
        if statement[index].isspace():
            index += 1
            continue
        if statement.startswith("--", index):
            newline = statement.find("\n", index + 2)
            index = len(statement) if newline == -1 else newline + 1
            continue
        if statement.startswith("/*", index):
            end = statement.find("*/", index + 2)
            if end == -1:
                return False
            index = end + 2
            continue
        return False
    return True


def apply_migrations(connection: sqlite3.Connection, now: int) -> None:
    versions = _migration_versions()
    supported_latest = versions[-1]

    if connection.in_transaction:
        raise MigrationError("cannot apply migrations inside an existing transaction")

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations")
        }
        unknown = sorted(applied.difference(versions))
        if unknown:
            future = [version for version in unknown if version > supported_latest]
            if future:
                raise MigrationError(
                    "unsupported future schema version(s) "
                    f"{future}; latest supported version is {supported_latest}"
                )
            raise MigrationError(f"unsupported schema version(s) {unknown}")

        for version, script in MIGRATIONS:
            if version in applied:
                continue
            for statement in _iter_statements(script):
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, now),
            )

        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
