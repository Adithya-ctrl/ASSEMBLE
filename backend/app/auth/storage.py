"""Small SQLite adapter with explicit transaction ownership."""

from __future__ import annotations

import errno
import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.auth.migrations import apply_migrations


class StorageBusyError(RuntimeError):
    """Raised when SQLite cannot obtain its bounded local lock."""


class StoragePermissionError(RuntimeError):
    """Raised when durable auth state has unsafe POSIX permissions."""


def _is_busy(exc: sqlite3.OperationalError) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    return code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} or "locked" in str(exc).casefold()


class AuthStore:
    def __init__(self, database_path: Path, *, now: int) -> None:
        self.database_path = Path(database_path)
        self._prepare_private_path()
        connection = self.connect()
        try:
            try:
                apply_migrations(connection, now)
            except sqlite3.OperationalError as exc:
                if _is_busy(exc):
                    raise StorageBusyError("auth storage is busy") from exc
                raise
        finally:
            connection.close()

    def _prepare_private_path(self) -> None:
        parent = self.database_path.parent
        parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if os.name != "posix":
            return
        parent_mode = stat.S_IMODE(parent.stat().st_mode)
        if parent_mode != 0o700:
            raise StoragePermissionError(
                f"auth database directory must have mode 0700: {parent}"
            )
        if self._private_file_exists(self.database_path, "existing auth database"):
            self._validate_existing_runtime_files()
            return
        try:
            descriptor = os.open(
                self.database_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            self._validate_private_regular_file(self.database_path, "existing auth database")
        else:
            os.close(descriptor)
        self._validate_existing_runtime_files()

    @staticmethod
    def _validate_file_stat(file_stat: os.stat_result, label: str) -> None:
        if not stat.S_ISREG(file_stat.st_mode) or stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise StoragePermissionError(f"{label} must be a private regular file with mode 0600")

    @classmethod
    def _validate_private_regular_file(cls, path: Path, label: str) -> None:
        try:
            file_stat = os.lstat(path)
        except FileNotFoundError as exc:
            raise StoragePermissionError(f"{label} disappeared during permission validation") from exc
        cls._validate_file_stat(file_stat, label)

    @classmethod
    def _private_file_exists(cls, path: Path, label: str) -> bool:
        try:
            file_stat = os.lstat(path)
        except FileNotFoundError:
            return False
        cls._validate_file_stat(file_stat, label)
        return True

    def _validate_existing_runtime_files(self) -> None:
        for suffix in ("-wal", "-shm"):
            path = Path(f"{self.database_path}{suffix}")
            self._private_file_exists(path, "auth database runtime file")

    def _secure_runtime_files(self) -> None:
        if os.name != "posix":
            return
        self._validate_private_regular_file(
            self.database_path,
            "auth database runtime file",
        )
        for suffix in ("-wal", "-shm"):
            path = Path(f"{self.database_path}{suffix}")
            self._private_file_exists(path, "auth database runtime file")

    def connect(self) -> sqlite3.Connection:
        self._secure_runtime_files()
        connection = sqlite3.connect(self.database_path, timeout=5.0, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA journal_mode=WAL")
            self._secure_runtime_files()
            return connection
        except sqlite3.OperationalError as exc:
            connection.close()
            if _is_busy(exc):
                raise StorageBusyError("auth storage is busy") from exc
            raise
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            except sqlite3.OperationalError as exc:
                if _is_busy(exc):
                    raise StorageBusyError("auth storage is busy") from exc
                raise
            self._secure_runtime_files()
            yield connection
            connection.commit()
            self._secure_runtime_files()
        except sqlite3.OperationalError as exc:
            connection.rollback()
            if _is_busy(exc):
                raise StorageBusyError("auth storage is busy") from exc
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
