"""Explicit local configuration for the isolated auth slice."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuthSettings:
    database_path: Path
    cookie_name: str = "assemble_session"
    cookie_secure: bool = False
    session_ttl_seconds: int = 7 * 24 * 60 * 60
    invitation_default_ttl_seconds: int = 24 * 60 * 60
    rate_limit_attempts: int = 10
    rate_limit_window_seconds: int = 60
    request_body_limit_bytes: int = 16 * 1024
    allowed_browser_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    @classmethod
    def from_env(cls) -> "AuthSettings":
        backend_root = Path(__file__).resolve().parents[2]
        configured_path = os.getenv("ASSEMBLE_AUTH_DB_PATH")
        database_path = Path(configured_path).expanduser() if configured_path else backend_root / ".data" / "auth.sqlite3"
        secure_value = os.getenv("ASSEMBLE_AUTH_COOKIE_SECURE", "0").strip().lower()
        if secure_value not in {"0", "1", "false", "true"}:
            raise ValueError("ASSEMBLE_AUTH_COOKIE_SECURE must be 0, 1, false, or true")
        return cls(database_path=database_path, cookie_secure=secure_value in {"1", "true"})
