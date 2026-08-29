from __future__ import annotations

import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.auth import migrations, storage as storage_module
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


@pytest.mark.parametrize("mode", (0o000, 0o200, 0o400, 0o640, 0o644, 0o660, 0o700))
def test_existing_auth_file_requires_exact_writable_private_mode_on_posix(
    tmp_path: Path,
    mode: int,
) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "auth.sqlite3"
    database_path.touch(mode=0o600)
    database_path.chmod(mode)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(database_path, now=NOW)


@pytest.mark.parametrize("mode", (0o400, 0o500, 0o600, 0o710, 0o750, 0o777))
def test_existing_auth_directory_requires_exact_0700_on_posix(
    tmp_path: Path,
    mode: int,
) -> None:
    if os.name != "posix":
        return
    parent = tmp_path / "auth-state"
    parent.mkdir(mode=0o700)
    parent.chmod(mode)
    try:
        with pytest.raises(StoragePermissionError, match="mode 0700"):
            AuthStore(parent / "auth.sqlite3", now=NOW)
    finally:
        parent.chmod(0o700)


def test_read_only_auth_file_is_rejected_before_sqlite_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "auth.sqlite3"
    database_path.touch(mode=0o600)
    database_path.chmod(0o400)

    def unexpected_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        raise AssertionError("permission validation must run before sqlite open")

    monkeypatch.setattr(sqlite3, "connect", unexpected_connect)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(database_path, now=NOW)


@pytest.mark.parametrize("suffix", ("-wal", "-shm"))
@pytest.mark.parametrize("mode", (0o000, 0o400, 0o640, 0o644, 0o660, 0o700))
def test_preexisting_runtime_files_require_exact_writable_private_mode(
    tmp_path: Path,
    suffix: str,
    mode: int,
) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "auth.sqlite3"
    AuthStore(database_path, now=NOW)
    runtime_path = Path(f"{database_path}{suffix}")
    runtime_path.touch(mode=0o600)
    runtime_path.chmod(mode)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(database_path, now=NOW)


@pytest.mark.parametrize("suffix", ("", "-wal", "-shm"))
@pytest.mark.parametrize("path_kind", ("symlink", "directory"))
def test_preexisting_auth_paths_reject_symlinks_and_nonregular_files(
    tmp_path: Path,
    suffix: str,
    path_kind: str,
) -> None:
    if os.name != "posix":
        return
    database_path = tmp_path / "auth.sqlite3"
    if suffix:
        AuthStore(database_path, now=NOW)
    target = Path(f"{database_path}{suffix}")
    if target.exists():
        target.unlink()
    if path_kind == "symlink":
        target.symlink_to(tmp_path / "missing")
    else:
        target.mkdir(mode=0o700)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(database_path, now=NOW)


def test_simultaneous_fresh_store_constructors_are_idempotent(tmp_path: Path) -> None:
    for round_number in range(100):
        database_path = tmp_path / f"round-{round_number}" / "auth.sqlite3"
        start = threading.Barrier(8)

        def construct_store(_: int) -> AuthStore:
            start.wait(timeout=5)
            return AuthStore(database_path, now=NOW)

        with ThreadPoolExecutor(max_workers=8) as executor:
            stores = list(executor.map(construct_store, range(8)))

        with stores[0].connect() as connection:
            assert [
                tuple(row)
                for row in connection.execute(
                    "SELECT version, COUNT(*) FROM schema_migrations GROUP BY version"
                )
            ] == [(1, 1)]


def test_constructor_retries_only_busy_initialization_and_closes_each_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_apply = storage_module.apply_migrations
    connections: list[sqlite3.Connection] = []

    def transient_busy(connection: sqlite3.Connection, now: int) -> None:
        connections.append(connection)
        if len(connections) == 1:
            raise sqlite3.OperationalError("database is locked")
        original_apply(connection, now)

    monkeypatch.setattr(storage_module, "apply_migrations", transient_busy)
    AuthStore(tmp_path / "auth.sqlite3", now=NOW)

    assert len(connections) == 2
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_nonbusy_initialization_failure_propagates_closes_and_releases_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_apply = storage_module.apply_migrations
    connections: list[sqlite3.Connection] = []

    def fail_nonbusy(connection: sqlite3.Connection, now: int) -> None:
        connections.append(connection)
        raise sqlite3.OperationalError("disk I/O failure")

    monkeypatch.setattr(storage_module, "apply_migrations", fail_nonbusy)
    database_path = tmp_path / "auth.sqlite3"
    with pytest.raises(sqlite3.OperationalError, match="disk I/O failure"):
        AuthStore(database_path, now=NOW)

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")

    monkeypatch.setattr(storage_module, "apply_migrations", original_apply)
    AuthStore(database_path, now=NOW)
