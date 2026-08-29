"""Strict HTTP and domain models for the auth slice."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.crypto import normalize_email, normalize_username, validate_password


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommunityRole(StrEnum):
    ADMINISTRATOR = "ADMINISTRATOR"
    COORDINATOR = "COORDINATOR"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class Permission(StrEnum):
    COMMUNITY_READ = "community:read"
    PLANNING_USE = "planning:use"
    PROJECT_PARTICIPATE = "project:participate"
    MEMBERS_LIST = "members:list"
    MEMBERS_ROLE_CHANGE = "members:role-change"
    INVITATIONS_MANAGE = "invitations:manage"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[CommunityRole, frozenset[Permission]] = {
    CommunityRole.ADMINISTRATOR: frozenset(Permission),
    CommunityRole.COORDINATOR: frozenset({
        Permission.COMMUNITY_READ,
        Permission.PLANNING_USE,
        Permission.PROJECT_PARTICIPATE,
    }),
    CommunityRole.MEMBER: frozenset({Permission.COMMUNITY_READ, Permission.PROJECT_PARTICIPATE}),
    CommunityRole.VIEWER: frozenset({Permission.COMMUNITY_READ}),
}


class InvitationState(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class SignupRequest(ContractModel):
    username: str = Field(min_length=3, max_length=64)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("username")
    @classmethod
    def username_valid(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str | None) -> str | None:
        return normalize_email(value) if value is not None else None

    @field_validator("password")
    @classmethod
    def password_valid(cls, value: str) -> str:
        return validate_password(value)

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized


class LoginRequest(ContractModel):
    identity: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identity")
    @classmethod
    def identity_valid(cls, value: str) -> str:
        return normalize_email(value) if "@" in value else normalize_username(value)


class PasswordChangeRequest(ContractModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_valid(cls, value: str) -> str:
        return validate_password(value)


class ProfileUpdateRequest(ContractModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=512)

    @field_validator("display_name")
    @classmethod
    def display_name_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized

    @field_validator("avatar_url")
    @classmethod
    def avatar_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        has_forbidden_character = any(
            ord(character) <= 0x20 or ord(character) == 0x7F
            for character in value
        )
        normalized = value.strip()
        try:
            parsed = urlsplit(normalized)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("avatar_url must be an https URL without credentials") from exc
        if normalized and (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or (port is not None and not 1 <= port <= 65535)
            or has_forbidden_character
        ):
            raise ValueError("avatar_url must be an https URL without credentials")
        return normalized or None


class CommunityCreateRequest(ContractModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?$")

    @field_validator("name")
    @classmethod
    def name_valid(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("slug", mode="before")
    @classmethod
    def slug_normalized(cls, value: object) -> object:
        return value.strip().casefold() if isinstance(value, str) else value


class RoleChangeRequest(ContractModel):
    role: CommunityRole


class InvitationCreateRequest(ContractModel):
    recipient: str = Field(min_length=3, max_length=254)
    role: CommunityRole
    expires_in_seconds: int = Field(default=24 * 60 * 60, ge=5 * 60, le=7 * 24 * 60 * 60, strict=True)

    @field_validator("recipient")
    @classmethod
    def recipient_valid(cls, value: str) -> str:
        return normalize_email(value) if "@" in value else normalize_username(value)


class InvitationAcceptRequest(ContractModel):
    token: str = Field(min_length=40, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class UserView(ContractModel):
    id: str
    username: str
    email: str | None
    display_name: str | None
    avatar_url: str | None


class MembershipView(ContractModel):
    community_id: str
    community_name: str
    community_slug: str
    user_id: str
    username: str
    role: CommunityRole
    created_at: int
    updated_at: int


class SessionView(ContractModel):
    user: UserView
    memberships: list[MembershipView]
    session_expires_at: int


class CommunityView(ContractModel):
    id: str
    name: str
    slug: str
    role: CommunityRole
    created_at: int


class InvitationView(ContractModel):
    id: str
    community_id: str
    role: CommunityRole
    inviter_user_id: str
    recipient_kind: str
    recipient: str
    state: InvitationState
    created_at: int
    expires_at: int
    accepted_by_user_id: str | None = None
    accepted_at: int | None = None
    revoked_at: int | None = None


class InvitationCreatedView(InvitationView):
    token: str
    delivery: str = "local_copy"


class AuditEventView(ContractModel):
    id: str
    event_type: str
    actor_user_id: str | None
    subject_user_id: str | None
    community_id: str | None
    invitation_id: str | None
    occurred_at: int
    metadata: dict[str, Any]


class MessageView(ContractModel):
    message: str
