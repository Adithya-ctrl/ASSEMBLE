"""Bounded, deterministic catalyst planning over immutable community states."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from app.api_models import PlanNode, PlanResponse, SolverStatus
from app.explain import AnalysisCallable, call_analyser, coerce_status, is_feasible
from app.interventions import TransitionError, apply_action, can_apply_action
from app.models import CatalystAction, CommunityState, InitiativeBlueprint


class NoPlanFound(LookupError):
    """Raised when no valid path is found within the disclosed BFS bounds."""


@dataclass(frozen=True)
class _QueueNode:
    state: CommunityState
    action_path: tuple[str, ...]
    cumulative_cost: int
    target_status: SolverStatus
    depth: int


def _path_key(node: _QueueNode) -> tuple[int, int, tuple[str, ...]]:
    return (node.cumulative_cost, node.depth, node.action_path)


def plan_catalyst(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    actions: Iterable[CatalystAction],
    analyser: AnalysisCallable | None = None,
    *,
    max_depth: int = 2,
    max_expanded_states: int = 20,
) -> PlanResponse:
    """Search action paths with depth-two BFS and a hard expansion cap.

    The search is intentionally generic: it never branches on an initiative
    identifier.  Every successor is produced through the same validated,
    immutable transition and re-analysed by the authoritative analyser.
    """

    if max_depth < 0 or max_depth > 2:
        raise ValueError("max_depth must be between 0 and 2")
    if max_expanded_states < 1 or max_expanded_states > 20:
        raise ValueError("max_expanded_states must be between 1 and 20")

    catalogue = sorted(list(actions), key=lambda action: action.id)
    ids = [action.id for action in catalogue]
    if len(ids) != len(set(ids)):
        raise ValueError("action catalogue contains duplicate ids")

    baseline_result = call_analyser(analyser, community, initiative)
    baseline_status = coerce_status(baseline_result)
    root = _QueueNode(
        state=community,
        action_path=(),
        cumulative_cost=0,
        target_status=baseline_status,
        depth=0,
    )
    queue: deque[_QueueNode] = deque([root])
    nodes: list[PlanNode] = [
        PlanNode(
            state_id=community.state_id,
            action_path=[],
            cumulative_cost=0,
            target_status=baseline_status,
            prune_reason="target_already_satisfied" if is_feasible(baseline_result) else None,
        )
    ]
    successes: list[_QueueNode] = []
    expanded_states = 0
    expanded_state_ids: set[str] = set()

    # Keep queue ordering breadth-first.  Candidate paths are sorted by action
    # ID; successful paths are ranked independently after the bounded search.
    while queue and expanded_states < max_expanded_states:
        current = queue.popleft()
        if current.state.state_id not in expanded_state_ids:
            expanded_state_ids.add(current.state.state_id)
            expanded_states += 1

        if current.action_path and is_feasible(current.target_status):
            successes.append(current)
            continue
        if is_feasible(current.target_status):
            # The frozen PlanResponse requires a non-empty path, so a target
            # already feasible at S0 is reported as no catalyst path.
            continue
        if current.depth >= max_depth:
            continue

        for action in catalogue:
            if action.id in current.action_path:
                continue
            if not can_apply_action(current.state, action):
                continue
            if expanded_states >= max_expanded_states and len(nodes) >= max_expanded_states:
                break
            try:
                successor, _ = apply_action(current.state, action)
            except (TransitionError, ValueError):
                # Preconditions are checked above; this catch preserves a
                # bounded search if a malformed external catalogue slips in.
                continue
            result = call_analyser(analyser, successor, initiative)
            successor_status = coerce_status(result)
            child = _QueueNode(
                state=successor,
                action_path=(*current.action_path, action.id),
                cumulative_cost=current.cumulative_cost + action.cost,
                target_status=successor_status,
                depth=current.depth + 1,
            )
            if len(nodes) < max_expanded_states:
                nodes.append(
                    PlanNode(
                        state_id=successor.state_id,
                        action_path=list(child.action_path),
                        cumulative_cost=child.cumulative_cost,
                        target_status=successor_status,
                        prune_reason=None,
                    )
                )
                queue.append(child)
            else:
                # The state was analysed (and therefore remains evidence), but
                # cannot be queued once the response's node cap is reached.
                break

    if not successes:
        raise NoPlanFound(
            f"no catalyst path for {initiative.id} within depth {max_depth} and "
            f"{max_expanded_states} expanded states"
        )

    best = min(successes, key=_path_key)
    states = [community.state_id]
    current = community
    for action_id in best.action_path:
        action = next(action for action in catalogue if action.id == action_id)
        current, _ = apply_action(current, action)
        states.append(current.state_id)
    return PlanResponse(
        target_initiative_id=initiative.id,
        path=list(best.action_path),
        total_cost=best.cumulative_cost,
        states=states,
        nodes=nodes,
        target_status_before=baseline_status,
        target_status_after=best.target_status,
    )


plan = plan_catalyst
catalyst_plan = plan_catalyst

