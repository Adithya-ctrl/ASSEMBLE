"""SQLite migration, lock, restart and POSIX permission adversaries."""

from __future__ import annotations

import os
import sqlite3
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.auth import migrations
from app.auth.migrations import MigrationError, apply_migrations
from app.auth.storage import AuthStore, StoragePermissionError


NOW = 2_300_000_000


def test_existing_database_requires_exact_private_regular_mode_on_posix(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode contract")
    for mode in (0o400, 0o600, 0o640, 0o660, 0o644):
        database_path = tmp_path / f"auth-{mode:o}.sqlite3"
        database_path.touch(mode=mode)
        database_path.chmod(mode)
        if mode == 0o600:
            AuthStore(database_path, now=NOW)
        else:
            with pytest.raises(StoragePermissionError, match="private regular file"):
                AuthStore(database_path, now=NOW)


def test_existing_database_directory_requires_private_parent_on_posix(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode contract")
    for mode in (0o700, 0o750, 0o710, 0o701):
        parent = tmp_path / f"parent-{mode:o}"
        parent.mkdir(mode=mode)
        parent.chmod(mode)
        database_path = parent / "auth.sqlite3"
        if mode == 0o700:
            AuthStore(database_path, now=NOW)
        else:
            with pytest.raises(StoragePermissionError, match="directory"):
                AuthStore(database_path, now=NOW)


def test_database_symlink_and_nonregular_targets_fail_closed(tmp_path: Path) -> None:
    real = tmp_path / "real.sqlite3"
    real.touch(mode=0o600)
    real.chmod(0o600)
    symlink = tmp_path / "auth.sqlite3"
    symlink.symlink_to(real)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(symlink, now=NOW)

    directory_target = tmp_path / "database-directory"
    directory_target.mkdir(mode=0o700)
    with pytest.raises(StoragePermissionError, match="private regular file"):
        AuthStore(directory_target, now=NOW)


def test_runtime_wal_shm_permission_checks_are_fail_closed(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode contract")
    database_path = tmp_path / "auth.sqlite3"
    store = AuthStore(database_path, now=NOW)
    # _secure_runtime_files is deliberately a small, deterministic unit of the
    # startup boundary; constructing arbitrary SQLite WAL pages is unnecessary
    # for proving its permission decision.
    for suffix in ("-wal", "-shm"):
        runtime_path = Path(f"{database_path}{suffix}")
        runtime_path.touch(mode=0o644)
        runtime_path.chmod(0o644)
        with pytest.raises(StoragePermissionError, match="runtime file"):
            store._secure_runtime_files()
        runtime_path.unlink()


def test_concurrent_cold_start_migration_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    barrier = threading.Barrier(4)

    def start(_: int) -> str:
        barrier.wait()
        try:
            AuthStore(database_path, now=NOW)
            return "OK"
        except Exception as exc:  # pragma: no cover - assertion below reports unexpected classes
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(start, range(4)))
    assert results == ["OK"] * 4
    with AuthStore(database_path, now=NOW + 1).connect() as connection:
        assert [row[0] for row in connection.execute("SELECT version FROM schema_migrations")] == [1]


def test_schema_ledger_cannot_claim_a_missing_schema_without_failing_closed(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    connection = sqlite3.connect(database_path, isolation_level=None)
    connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL)")
    connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)", (NOW,))
    connection.close()
    with pytest.raises((MigrationError, sqlite3.DatabaseError, RuntimeError)):
        AuthStore(database_path, now=NOW + 1)


def test_migration_catalogue_must_be_positive_unique_and_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    for catalogue in (
        ((0, "CREATE TABLE zero (id INTEGER);"),),
        ((1, "CREATE TABLE one (id INTEGER);"), (1, "CREATE TABLE duplicate (id INTEGER);")),
        ((2, "CREATE TABLE two (id INTEGER);"), (1, "CREATE TABLE one (id INTEGER);")),
    ):
        monkeypatch.setattr(migrations, "MIGRATIONS", catalogue)
        with pytest.raises(MigrationError, match="migration versions"):
            apply_migrations(connection, NOW)
        assert not connection.in_transaction
    connection.close()


def test_migration_statement_iterator_handles_comments_quotes_and_trigger_semicolons() -> None:
    script = """
        -- semicolon in a line comment ;
        CREATE TABLE sample (value TEXT);
        INSERT INTO sample(value) VALUES ('literal;semicolon');
        /* block comment ; with another ; */
        CREATE TRIGGER sample_guard
        BEFORE INSERT ON sample
        BEGIN
            SELECT CASE WHEN NEW.value = 'reject;me' THEN RAISE(ABORT, 'blocked') END;
        END;
    """
    statements = list(migrations._iter_statements(script))
    assert len(statements) == 3
    connection = sqlite3.connect(":memory:")
    for statement in statements:
        connection.execute(statement)
    connection.execute("INSERT INTO sample(value) VALUES ('ok')")
    with pytest.raises(sqlite3.IntegrityError, match="blocked"):
        connection.execute("INSERT INTO sample(value) VALUES ('reject;me')")
    connection.close()


def test_apply_migrations_refuses_an_existing_transaction(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "auth.sqlite3", isolation_level=None)
    connection.execute("BEGIN")
    with pytest.raises(MigrationError, match="existing transaction"):
        apply_migrations(connection, NOW)
    assert connection.in_transaction
    connection.rollback()
    connection.close()


def test_unknown_past_schema_versions_fail_closed_without_erasing_the_ledger(tmp_path: Path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    AuthStore(database_path, now=NOW)
    with AuthStore(database_path, now=NOW + 1).transaction(immediate=True) as connection:
        connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (0, ?)", (NOW + 1,))
    with pytest.raises(MigrationError, match="unsupported schema version"):
        AuthStore(database_path, now=NOW + 2)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [(0,), (1,)]


def test_sqlite_foreign_keys_and_transaction_rollback_leave_no_partial_membership(tmp_path: Path) -> None:
    store = AuthStore(tmp_path / "auth.sqlite3", now=NOW)
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO memberships(community_id, user_id, role, invited_by_user_id, created_at, updated_at) VALUES ('missing', 'missing', 'MEMBER', NULL, ?, ?)",
                (NOW, NOW),
            )
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM memberships").fetchone()[0] == 0


def test_mode_assertion_uses_lstat_for_runtime_symlinks(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode contract")
    database_path = tmp_path / "auth.sqlite3"
    store = AuthStore(database_path, now=NOW)
    target = tmp_path / "runtime-target"
    target.touch(mode=0o600)
    target.chmod(0o600)
    runtime = Path(f"{database_path}-wal")
    runtime.symlink_to(target)
    with pytest.raises(StoragePermissionError, match="runtime file"):
        store._secure_runtime_files()
    runtime.unlink()
