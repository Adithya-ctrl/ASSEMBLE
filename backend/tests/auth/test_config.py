from __future__ import annotations

from pathlib import Path

import pytest

from app.auth.config import AuthSettings


def test_allowed_browser_origins_are_configurable_and_defaults_are_localhost(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ASSEMBLE_AUTH_DB_PATH", str(tmp_path / "auth.sqlite3"))
    monkeypatch.delenv("ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS", raising=False)
    defaults = AuthSettings.from_env()
    assert defaults.allowed_browser_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    monkeypatch.setenv(
        "ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS",
        "http://localhost:4173,https://app.example.test",
    )
    configured = AuthSettings.from_env()
    assert configured.allowed_browser_origins == (
        "http://localhost:4173",
        "https://app.example.test",
    )


@pytest.mark.parametrize(
    "value",
    (
        "",
        "*",
        "null",
        "ftp://localhost:4173",
        "http://user@localhost:4173",
        "http://localhost:4173/",
        "http://localhost:4173/path",
        "http://localhost:4173?query=yes",
        "http://localhost:4173#fragment",
        "http://localhost:99999",
        "http://local_host:4173",
        "http://LOCALHOST:4173",
        "http://localhost%2f.evil:4173",
        "http://999.999.999.999:4173",
        "http://localhost:4173,,https://app.example.test",
        " http://localhost:4173",
        "http://localhost:4173 ",
        "http://localhost:4173, https://app.example.test",
        "http://localhost:4173\t",
        "http://localhost:4173\n",
        "http://localhost:4173\x1f",
        "http://local host:4173",
    ),
)
def test_malformed_allowed_browser_origin_environment_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str,
) -> None:
    monkeypatch.setenv("ASSEMBLE_AUTH_DB_PATH", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS", value)
    with pytest.raises(ValueError, match="ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS"):
        AuthSettings.from_env()


@pytest.mark.parametrize(
    "value",
    (
        ",".join("http://localhost:4173" for _ in range(33)),
        "http://" + ("a" * 4096),
    ),
)
def test_allowed_browser_origin_environment_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str,
) -> None:
    monkeypatch.setenv("ASSEMBLE_AUTH_DB_PATH", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS", value)
    with pytest.raises(ValueError, match="ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS"):
        AuthSettings.from_env()
