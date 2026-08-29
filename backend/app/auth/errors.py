"""Stable domain errors for identity and invitation operations."""

from __future__ import annotations

from typing import Any


class AuthProblem(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after


def authentication_required() -> AuthProblem:
    return AuthProblem(401, "AUTHENTICATION_REQUIRED", "A current authenticated session is required.")


def permission_denied() -> AuthProblem:
    return AuthProblem(403, "PERMISSION_DENIED", "The current membership does not permit this operation.")


def invitation_not_available() -> AuthProblem:
    return AuthProblem(404, "INVITATION_NOT_AVAILABLE", "The invitation is not available.")
