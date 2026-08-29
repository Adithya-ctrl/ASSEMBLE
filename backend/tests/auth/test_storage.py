from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.auth import migrations
from app.auth.migrations import MigrationError, apply_migrations
from app.auth.storage import AuthStore, StoragePermissionError


NOW = 1_700_000_000


def _insert_user(connection: sqlite3.Connection, user_id: str, username: str) -> None:
    connection.execute(
        """
        INSERT INTO users (
            id, username, email, password_hash, password_version,
            display_name, avatar_url, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, f"{username}@example.test", "encoded", 1, None, None, NOW, NOW),
    )


def _insert_community(connection: sqlite3.Connection, community_id: str, creator_id: str) -> None:
    connection.execute(
        """
        INSERT INTO communities (
            id, name, slug, created_by_user_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (community_id, "A Community", community_id, creator_id, NOW, NOW),
    )


def _insert_pending_invitation(
    connection: sqlite3.Connection,
    invitation_id: str,
    community_id: str,
    inviter_id: str,
    recipient: str = "invitee",
) -> None:
    connection.execute(
        """
        INSERT INTO invitations (
            id, token_hash, community_id, role, inviter_user_id,
            recipient_kind, recipient, state, created_at, expires_at,
            accepted_by_user_id, accepted_at, revoked_at
        ) VALUES (?, ?, ?, 'MEMBER', ?, 'username', ?, 'PENDING', ?, ?, NULL, NULL, NULL)
        """,
        (invitation_id, f"hash-{invitation_id}", community_id, inviter_id, recipient, NOW, NOW + 3600),
    )


def test_cold_start_repeat_migration_and_restart_persist_state(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"

    AuthStore(database_path, now=NOW)
    with AuthStore(database_path, now=NOW + 1).transaction(immediate=True) as connection:
        _insert_user(connection, "USER-1", "alice")

    with AuthStore(database_path, now=NOW + 2).connect() as connection:
        assert connection.execute("SELECT username FROM users WHERE id = 'USER-1'").fetchone()[0] == "alice"
        assert [
            tuple(row)
            for row in connection.execute("SELECT version, applied_at FROM schema_migrations")
        ] == [(1, NOW)]


def test_connection_pragmas_schema_indexes_and_foreign_keys(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3", now=NOW)

    with store.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {
            "schema_migrations",
            "users",
            "sessions",
            "communities",
            "memberships",
            "invitations",
            "rate_limits",
            "audit_events",
            "sqlite_sequence",
        }

        invitation_columns = [
            row[1] for row in connection.execute("PRAGMA table_info(invitations)")
        ]
        assert invitation_columns == [
            "id",
            "token_hash",
            "community_id",
            "role",
            "inviter_user_id",
            "recipient_kind",
            "recipient",
            "state",
            "created_at",
            "expires_at",
            "accepted_by_user_id",
            "accepted_at",
            "revoked_at",
        ]

        indexes = {
            row[1]
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master WHERE type = 'index'"
            )
        }
        assert {
            "sessions_user_id_idx",
            "memberships_user_id_idx",
            "invitations_community_recipient_idx",
            "invitations_one_pending_recipient_idx",
            "audit_community_sequence_idx",
        } <= indexes

        foreign_keys = {
            (row[2], row[3], row[4], row[6])
            for row in connection.execute("PRAGMA foreign_key_list(sessions)")
        }
        assert ("users", "user_id", "id", "CASCADE") in foreign_keys

        trigger_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        assert trigger_names == {
            "audit_events_append_only_update",
            "audit_events_append_only_delete",
        }


def test_unknown_future_schema_version_fails_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    store = AuthStore(database_path, now=NOW)
    with store.transaction(immediate=True) as connection:
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (999, NOW + 1),
        )

    with pytest.raises(MigrationError, match="future schema version"):
        AuthStore(database_path, now=NOW + 2)

    with store.connect() as connection:
        assert [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")] == [
            1,
            999,
        ]


def test_failed_migration_rolls_back_ledger_and_partial_ddl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "auth.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    bad_migrations = ((1, "CREATE TABLE first_table (id INTEGER PRIMARY KEY); INVALID SQL;"),)
    monkeypatch.setattr(migrations, "MIGRATIONS", bad_migrations)

    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(connection, NOW)

    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'first_table'"
    ).fetchone() is None
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone() is None
    assert not connection.in_transaction
    connection.close()


def test_transaction_rolls_back_on_body_failure(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3", now=NOW)

    with pytest.raises(RuntimeError, match="abort"):
        with store.transaction(immediate=True) as connection:
            _insert_user(connection, "USER-1", "alice")
            raise RuntimeError("abort")

    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_audit_events_are_append_only_at_database_boundary(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3", now=NOW)
    with store.transaction(immediate=True) as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
                id, event_type, actor_user_id, subject_user_id, community_id,
                invitation_id, occurred_at, metadata_json
            ) VALUES ('EVENT-1', 'TEST', NULL, NULL, NULL, NULL, ?, '{}')
            """,
            (NOW,),
        )

    for statement in (
        "UPDATE audit_events SET event_type = 'CHANGED' WHERE id = 'EVENT-1'",
        "DELETE FROM audit_events WHERE id = 'EVENT-1'",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            with store.transaction(immediate=True) as connection:
                connection.execute(statement)

    with store.connect() as connection:
        row = connection.execute(
            "SELECT event_type FROM audit_events WHERE id = 'EVENT-1'"
        ).fetchone()
        assert row[0] == "TEST"


def test_pending_recipient_can_be_replaced_after_expiry(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3", now=NOW)
    with store.transaction(immediate=True) as connection:
        _insert_user(connection, "USER-1", "alice")
        _insert_community(connection, "COMMUNITY-1", "USER-1")
        _insert_pending_invitation(connection, "INV-1", "COMMUNITY-1", "USER-1")
        connection.execute(
            "UPDATE invitations SET state = 'EXPIRED' WHERE id = 'INV-1'"
        )
        _insert_pending_invitation(connection, "INV-2", "COMMUNITY-1", "USER-1")

    with store.connect() as connection:
        assert [
            tuple(row)
            for row in connection.execute("SELECT id, state FROM invitations ORDER BY id")
        ] == [("INV-1", "EXPIRED"), ("INV-2", "PENDING")]


def test_concurrent_pending_recipient_insert_has_one_winner(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    first_store = AuthStore(database_path, now=NOW)
    second_store = AuthStore(database_path, now=NOW)
    with first_store.transaction(immediate=True) as connection:
        _insert_user(connection, "USER-1", "alice")
        _insert_community(connection, "COMMUNITY-1", "USER-1")

    def insert(store: AuthStore, invitation_id: str) -> str:
        try:
            with store.transaction(immediate=True) as connection:
                _insert_pending_invitation(connection, invitation_id, "COMMUNITY-1", "USER-1")
            return "won"
        except sqlite3.IntegrityError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                insert,
                (first_store, second_store),
                ("INV-1", "INV-2"),
            )
        )

    assert sorted(outcomes) == ["duplicate", "won"]
    with first_store.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM invitations WHERE state = 'PENDING'"
        ).fetchone()[0] == 1


def test_existing_broad_auth_file_fails_closed_on_posix(tmp_path: Path) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "auth.sqlite3"
    database_path.touch(mode=0o644)
    database_path.chmod(0o644)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(database_path, now=NOW)
