from __future__ import annotations

import re
from pathlib import Path

from app.auth.api import create_auth_app
from app.auth.config import AuthSettings


ROOT = Path(__file__).parents[3]


def test_documented_auth_routes_match_isolated_openapi(tmp_path: Path) -> None:
    reference = (ROOT / "docs/reference/identity-community-invitations.md").read_text(encoding="utf-8")
    documented = {
        (method, route, status)
        for method, route, status in re.findall(
            r"^\| (GET|POST|PATCH) \| `(/api/[^`]+)` \| (\d{3}) \|",
            reference,
            flags=re.MULTILINE,
        )
    }
    openapi = create_auth_app(AuthSettings(database_path=tmp_path / "auth.sqlite3")).openapi()
    executable = {
        (
            method.upper(),
            route,
            "204"
            if route == "/api/auth/logout"
            else "201"
            if method.upper() == "POST"
            and route in {"/api/auth/signup", "/api/communities", "/api/communities/{community_id}/invitations"}
            else "200",
        )
        for route, operations in openapi["paths"].items()
        for method in operations
    }
    assert documented == executable


def test_secret_bearing_fields_are_confined_to_one_time_invitation_schema(tmp_path: Path) -> None:
    schemas = create_auth_app(AuthSettings(database_path=tmp_path / "auth.sqlite3")).openapi()["components"]["schemas"]
    assert "token" not in schemas["SessionView"]["properties"]
    assert "token" not in schemas["InvitationView"]["properties"]
    assert "token_hash" not in str(schemas)
    assert "password_hash" not in str(schemas)
    assert "token" in schemas["InvitationCreatedView"]["properties"]


def test_frozen_errors_and_security_assumptions_are_documented() -> None:
    reference = (ROOT / "docs/reference/identity-community-invitations.md").read_text(encoding="utf-8")
    for code in (
        "ACCOUNT_UNAVAILABLE",
        "AUTHENTICATION_FAILED",
        "AUTHENTICATION_REQUIRED",
        "PERMISSION_DENIED",
        "COMMUNITY_UNAVAILABLE",
        "COMMUNITY_NOT_FOUND",
        "MEMBERSHIP_NOT_FOUND",
        "MEMBERSHIP_EXISTS",
        "PENDING_INVITATION_EXISTS",
        "INVITATION_NOT_AVAILABLE",
        "INVITATION_NOT_PENDING",
        "LAST_ADMINISTRATOR_REQUIRED",
        "RATE_LIMITED",
        "SERVICE_BUSY",
        "UNSUPPORTED_MEDIA_TYPE",
        "BROWSER_ORIGIN_REJECTED",
    ):
        assert f"`{code}`" in reference
    for assumption in (
        "does not prove ownership of that mailbox",
        "X-Forwarded-For",
        "same-origin proxy",
        "no-store",
        "INVITER_NO_LONGER_AUTHORISED",
    ):
        assert assumption in reference or assumption in (
            ROOT / "docs/how-to/integrate-auth-backend.md"
        ).read_text(encoding="utf-8")
