from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.auth.models import (
    CommunityCreateRequest,
    CommunityRole,
    InvitationCreateRequest,
    ProfileUpdateRequest,
    ROLE_PERMISSIONS,
    SignupRequest,
)


def test_signup_normalizes_ascii_identity_and_preserves_display_case() -> None:
    request = SignupRequest(
        username="  Alice.Admin  ",
        email="  ALICE@EXAMPLE.COM ",
        password="Correct-Horse-42",
        display_name="  Alice Admin  ",
    )
    assert request.username == "alice.admin"
    assert request.email == "alice@example.com"
    assert request.display_name == "Alice Admin"


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "Correct-Horse-42"},
        {"username": "-alice", "password": "Correct-Horse-42"},
        {"username": "alice!", "password": "Correct-Horse-42"},
        {"username": "alice", "password": "alllowercaseonly"},
        {"username": "alice", "password": "Correct-Horse-42", "admin": True},
    ],
)
def test_signup_rejects_invalid_or_extra_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(payload)


def test_profile_avatar_requires_https_host_without_credentials() -> None:
    assert ProfileUpdateRequest(avatar_url="https://images.example/avatar.png").avatar_url
    for value in ("http://images.example/avatar.png", "https://", "https://user:pass@example.com/a"):
        with pytest.raises(ValidationError):
            ProfileUpdateRequest(avatar_url=value)


def test_community_slug_and_invitation_expiry_boundaries() -> None:
    assert CommunityCreateRequest(name=" Group ", slug="MY-GROUP").slug == "my-group"
    assert InvitationCreateRequest(
        recipient="member@example.com",
        role=CommunityRole.MEMBER,
        expires_in_seconds=300,
    ).expires_in_seconds == 300
    assert InvitationCreateRequest(
        recipient="member",
        role=CommunityRole.VIEWER,
        expires_in_seconds=604800,
    ).expires_in_seconds == 604800
    for seconds in (299, 604801):
        with pytest.raises(ValidationError):
            InvitationCreateRequest(
                recipient="member",
                role=CommunityRole.MEMBER,
                expires_in_seconds=seconds,
            )


def test_role_permission_matrix_has_no_admin_permissions_for_lower_roles() -> None:
    assert len(ROLE_PERMISSIONS[CommunityRole.ADMINISTRATOR]) > len(
        ROLE_PERMISSIONS[CommunityRole.COORDINATOR]
    )
    assert {permission.value for permission in ROLE_PERMISSIONS[CommunityRole.VIEWER]} == {
        "community:read"
    }
