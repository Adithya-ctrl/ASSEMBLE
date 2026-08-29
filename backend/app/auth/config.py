"""Explicit local configuration for the isolated auth slice."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_ALLOWED_BROWSER_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
_ALLOWED_ORIGINS_ENV = "ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS"
_MAX_ALLOWED_ORIGINS = 32
_MAX_ALLOWED_ORIGINS_ENV_BYTES = 4096
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _is_valid_origin_hostname(hostname: str) -> bool:
    try:
        ip_address(hostname)
        return True
    except ValueError:
        looks_like_ipv4 = all(character.isdigit() or character == "." for character in hostname)
        if ":" in hostname or len(hostname) > 253 or looks_like_ipv4:
            return False
        labels = hostname.split(".")
        return bool(labels) and all(_DNS_LABEL.fullmatch(label) for label in labels)


def _parse_allowed_browser_origins(configured: str | None) -> tuple[str, ...]:
    if configured is None:
        return DEFAULT_ALLOWED_BROWSER_ORIGINS
    if not configured or len(configured.encode("utf-8")) > _MAX_ALLOWED_ORIGINS_ENV_BYTES:
        raise ValueError(f"{_ALLOWED_ORIGINS_ENV} must contain a bounded comma-separated origin list")

    candidates = configured.split(",")
    if len(candidates) > _MAX_ALLOWED_ORIGINS:
        raise ValueError(f"{_ALLOWED_ORIGINS_ENV} contains too many origins")

    origins: list[str] = []
    for candidate in candidates:
        origin = candidate.strip()
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"{_ALLOWED_ORIGINS_ENV} contains an invalid origin") from exc
        hostname = parsed.hostname
        has_forbidden_character = any(ord(character) <= 0x20 or ord(character) == 0x7F for character in origin)
        if (
            not origin
            or has_forbidden_character
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or hostname is None
            or not hostname.isascii()
            or hostname != hostname.lower()
            or parsed.netloc != parsed.netloc.lower()
            or not _is_valid_origin_hostname(hostname)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.netloc.endswith(":")
            or (port is not None and not 1 <= port <= 65535)
            or origin != f"{parsed.scheme}://{parsed.netloc}"
        ):
            raise ValueError(f"{_ALLOWED_ORIGINS_ENV} contains an invalid origin")
        if origin not in origins:
            origins.append(origin)

    if not origins:
        raise ValueError(f"{_ALLOWED_ORIGINS_ENV} must contain at least one origin")
    return tuple(origins)


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
    allowed_browser_origins: tuple[str, ...] = DEFAULT_ALLOWED_BROWSER_ORIGINS

    @classmethod
    def from_env(cls) -> "AuthSettings":
        backend_root = Path(__file__).resolve().parents[2]
        configured_path = os.getenv("ASSEMBLE_AUTH_DB_PATH")
        database_path = Path(configured_path).expanduser() if configured_path else backend_root / ".data" / "auth.sqlite3"
        secure_value = os.getenv("ASSEMBLE_AUTH_COOKIE_SECURE", "0").strip().lower()
        if secure_value not in {"0", "1", "false", "true"}:
            raise ValueError("ASSEMBLE_AUTH_COOKIE_SECURE must be 0, 1, false, or true")
        allowed_browser_origins = _parse_allowed_browser_origins(os.getenv(_ALLOWED_ORIGINS_ENV))
        return cls(
            database_path=database_path,
            cookie_secure=secure_value in {"1", "true"},
            allowed_browser_origins=allowed_browser_origins,
        )
