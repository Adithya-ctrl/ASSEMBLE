"""Isolated identity, community membership and invitation backend."""

from typing import Any

from app.auth.config import AuthSettings
from app.auth.models import CommunityRole, Permission


def install_auth_api(*args: Any, **kwargs: Any) -> Any:
    """Load the HTTP registration boundary without import-time app mutation."""
    from app.auth.api import install_auth_api as install

    return install(*args, **kwargs)

__all__ = ["AuthSettings", "CommunityRole", "Permission", "install_auth_api"]
