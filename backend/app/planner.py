"""Bounded, deterministic catalyst planning over immutable community states."""

from __future__ import annotations

from collections.abc import Iterable

from app.api_models import PlanNode, PlanResponse, SolverStatus
from app.explain import AnalysisCallable, call_analyser, coerce_status, is_feasible
from app.interventions import TransitionError, apply_action, ordered_action_paths
from app.models import CatalystAction, CommunityState, InitiativeBlueprint


class NoPlanFound(LookupError):
    """Raised when no valid path is found within the disclosed BFS bounds."""


def _path_key(
    path: tuple[CatalystAction, ...],
) -> tuple[int, int, tuple[str, ...]]:
    return (sum(action.cost for action in path), len(path), tuple(action.id for action in path))


def plan_catalyst(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    actions: Iterable[CatalystAction],
    analyser: AnalysisCallable | None = None,
    *,
    max_depth: int = 2,
    max_expanded_states: int = 20,
) -> PlanResponse:
    """Evaluate the same ordered depth-two action paths used by unlock.

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
    nodes: list[PlanNode] = [
        PlanNode(
            state_id=community.state_id,
            action_path=[],
            cumulative_cost=0,
            target_status=baseline_status,
            prune_reason="target_already_satisfied" if is_feasible(baseline_result) else None,
        )
    ]
    if is_feasible(baseline_result):
        raise NoPlanFound(f"initiative {initiative.id} is already feasible at the base state")
    successes: list[tuple[tuple[CatalystAction, ...], CommunityState, SolverStatus]] = []
    candidates = ordered_action_paths(catalogue, max_depth=max_depth)
    for path in candidates[: max(0, max_expanded_states - 1)]:
        successor = community
        try:
            for action in path:
                successor, _ = apply_action(successor, action)
        except (TransitionError, ValueError):
            continue
        result = call_analyser(analyser, successor, initiative)
        status = coerce_status(result)
        nodes.append(
            PlanNode(
                state_id=successor.state_id,
                action_path=[action.id for action in path],
                cumulative_cost=sum(action.cost for action in path),
                target_status=status,
                prune_reason=None,
            )
        )
        if is_feasible(result):
            successes.append((path, successor, status))

    if not successes:
        raise NoPlanFound(
            f"no catalyst path for {initiative.id} within depth {max_depth} and "
            f"{max_expanded_states} expanded states"
        )

    best_path, _, best_status = min(successes, key=lambda item: _path_key(item[0]))
    states = [community.state_id]
    current = community
    for action in best_path:
        current, _ = apply_action(current, action)
        states.append(current.state_id)
    return PlanResponse(
        target_initiative_id=initiative.id,
        path=[action.id for action in best_path],
        total_cost=sum(action.cost for action in best_path),
        states=states,
        nodes=nodes,
        target_status_before=baseline_status,
        target_status_after=best_status,
    )


plan = plan_catalyst
catalyst_plan = plan_catalyst
