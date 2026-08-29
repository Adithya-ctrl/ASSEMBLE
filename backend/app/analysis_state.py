"""Shared authoritative reconstruction boundary for counterfactual analysis."""

from __future__ import annotations

from collections.abc import Sequence

from app.interventions import canonical_state_hash, transition_state
from app.models import CatalystAction, CommunityState


class AuthoritativeBaseMismatch(ValueError):
    """Raised when a supplied base is not exact authoritative S0."""


class InvalidCatalystPath(ValueError):
    """Raised when a path is outside the frozen ordered unique 0..2 contract."""


def reconstruct_authoritative_state(
    provided_base: CommunityState,
    catalyst_path: Sequence[str],
    authoritative_base: CommunityState,
    authoritative_actions: Sequence[CatalystAction],
) -> CommunityState:
    """Validate the base, then replay only authoritative actions from S0.

    The provided model is used solely as a proof of exact S0 identity and
    content. Reconstruction always begins from a fresh authoritative copy.
    """

    same_identity = (
        provided_base.state_id == authoritative_base.state_id
        and provided_base.parent_state_id == authoritative_base.parent_state_id
    )
    same_content = canonical_state_hash(provided_base) == canonical_state_hash(authoritative_base)
    if not same_identity or not same_content:
        raise AuthoritativeBaseMismatch(
            "base_community does not match the authoritative demo fixture state"
        )
    if len(catalyst_path) > 2:
        raise InvalidCatalystPath("catalyst_path must contain at most two action IDs")
    if len(catalyst_path) != len(set(catalyst_path)):
        raise InvalidCatalystPath("catalyst_path must not contain duplicate action IDs")

    actions_by_id = {action.id: action for action in authoritative_actions}
    if len(actions_by_id) != len(authoritative_actions):
        raise InvalidCatalystPath("authoritative action catalogue contains duplicate IDs")
    unknown = [action_id for action_id in catalyst_path if action_id not in actions_by_id]
    if unknown:
        raise InvalidCatalystPath(f"unknown action {unknown[0]}")

    current = authoritative_base.model_copy(deep=True)
    for action_id in catalyst_path:
        current = transition_state(current, action_id, authoritative_actions).successor_state
    return current
