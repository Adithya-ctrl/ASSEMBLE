"""Validated, immutable catalyst transitions and bounded unlock search."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256
import itertools
import json
from typing import Any

from app.api_models import (
    StateDiff,
    SolverStatus,
    TransitionResponse,
    UnlockResponse,
)
from app.explain import AnalysisCallable, call_analyser, coerce_status, is_feasible
from app.models import (
    AddCapabilityEffect,
    AddPersonEffect,
    AddResourceQuantityEffect,
    CatalystAction,
    CommunityState,
    InitiativeBlueprint,
    PersonBlock,
    ResourceBlock,
    SpaceBlock,
)


class TransitionError(ValueError):
    """Raised when an action cannot be safely applied to a state."""


class ActionAlreadyApplied(TransitionError):
    """Raised when an additive action would create no state change."""


class AlreadyFeasible(ValueError):
    """Raised when unlock search is requested for a satisfied target."""


class NoUnlockPath(LookupError):
    """Raised when no depth-two ordered catalogue path yields a feasible target."""


def _canonical_value(value: Any) -> Any:
    """Canonicalise model JSON, including order-insensitive block lists."""

    if isinstance(value, Mapping):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_canonical_value(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    return value


def canonical_state_payload(state: CommunityState) -> dict[str, Any]:
    """Return state content without identity/lineage fields."""

    payload = state.model_dump(mode="json")
    payload.pop("state_id", None)
    payload.pop("parent_state_id", None)
    return _canonical_value(payload)


def canonical_state_json(state: CommunityState) -> str:
    return json.dumps(canonical_state_payload(state), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_state_hash(state: CommunityState) -> str:
    """Return the lowercase SHA-256 digest of canonical state content."""

    return sha256(canonical_state_json(state).encode("utf-8")).hexdigest()


def state_id_for(state: CommunityState) -> str:
    """Return a stable contract-valid hash identity for a state."""

    # StableId requires an initial uppercase letter.  Prefixing the uppercase
    # digest keeps all 256 bits while preserving that frozen contract.
    return f"S{canonical_state_hash(state).upper()}"


def _person_index(state: CommunityState) -> dict[str, PersonBlock]:
    return {person.id: person for person in state.people}


def _space_index(state: CommunityState) -> dict[str, SpaceBlock]:
    return {space.id: space for space in state.spaces}


def _resource_index(state: CommunityState) -> dict[str, ResourceBlock]:
    return {resource.id: resource for resource in state.resources}


def _require_action_preconditions(state: CommunityState, action: CatalystAction) -> None:
    people = _person_index(state)
    spaces = _space_index(state)
    for requirement in action.preconditions.person_capabilities:
        person = people.get(requirement.person_id)
        if person is None:
            raise TransitionError(
                f"action {action.id} requires missing person {requirement.person_id}"
            )
        if requirement.capability_id not in person.capabilities:
            raise TransitionError(
                f"action {action.id} requires {requirement.capability_id} on {requirement.person_id}"
            )
    for requirement in action.preconditions.willing_learners:
        person = people.get(requirement.person_id)
        if person is None:
            raise TransitionError(
                f"action {action.id} requires missing learner {requirement.person_id}"
            )
        if requirement.capability_id not in person.willing_to_learn:
            raise TransitionError(
                f"action {action.id} requires {requirement.capability_id} willingness on {requirement.person_id}"
            )
    for requirement in action.preconditions.space_availability:
        space = spaces.get(requirement.space_id)
        if space is None:
            raise TransitionError(
                f"action {action.id} requires missing space {requirement.space_id}"
            )
        missing = set(requirement.slots) - set(space.available_slots)
        if missing:
            missing_ids = ", ".join(sorted(slot.value for slot in missing))
            raise TransitionError(
                f"action {action.id} space {requirement.space_id} unavailable at {missing_ids}"
            )


def _apply_effects(state: CommunityState, action: CatalystAction) -> StateDiff:
    people = _person_index(state)
    resources = _resource_index(state)
    existing_people = set(people)
    organisation_ids = {organisation.id for organisation in state.organisations}
    added_capabilities: dict[str, set[str]] = {}
    added_people: set[str] = set()
    resource_quantity_changes: dict[str, int] = {}

    for effect in action.effects:
        if isinstance(effect, AddCapabilityEffect):
            person = people.get(effect.person_id)
            if person is None:
                raise TransitionError(
                    f"action {action.id} effect references missing person {effect.person_id}"
                )
            if effect.capability_id not in person.capabilities:
                person.capabilities.add(effect.capability_id)
                added_capabilities.setdefault(person.id, set()).add(effect.capability_id)
        elif isinstance(effect, AddPersonEffect):
            if effect.person.id in existing_people:
                raise TransitionError(
                    f"action {action.id} effect would duplicate person {effect.person.id}"
                )
            if effect.person.organisation_id not in organisation_ids:
                raise TransitionError(
                    f"action {action.id} effect references missing organisation "
                    f"{effect.person.organisation_id}"
                )
            state.people.append(effect.person.model_copy(deep=True))
            existing_people.add(effect.person.id)
            people[effect.person.id] = state.people[-1]
            added_people.add(effect.person.id)
        elif isinstance(effect, AddResourceQuantityEffect):
            resource = resources.get(effect.resource_id)
            if resource is None:
                raise TransitionError(
                    f"action {action.id} effect references missing resource {effect.resource_id}"
                )
            resource.quantity += effect.quantity
            resource_quantity_changes[resource.id] = resource_quantity_changes.get(resource.id, 0) + effect.quantity
        else:  # pragma: no cover - Pydantic's discriminated union is exhaustive.
            raise TransitionError(f"action {action.id} has unsupported effect")

    return StateDiff(
        added_capabilities={
            person_id: sorted(capabilities)
            for person_id, capabilities in sorted(added_capabilities.items())
        },
        added_people=sorted(added_people),
        resource_quantity_changes=dict(sorted(resource_quantity_changes.items())),
    )


def apply_action(state: CommunityState, action: CatalystAction) -> tuple[CommunityState, StateDiff]:
    """Apply a validated action to a deep copy and return successor plus diff."""

    _require_action_preconditions(state, action)
    successor = state.model_copy(deep=True)
    diff = _apply_effects(successor, action)
    if not (
        diff.added_capabilities
        or diff.added_people
        or diff.resource_quantity_changes
    ):
        raise ActionAlreadyApplied(
            f"action {action.id} has no unapplied effects on state {state.state_id}"
        )
    successor.organisations.sort(key=lambda item: item.id)
    successor.people.sort(key=lambda item: item.id)
    successor.spaces.sort(key=lambda item: item.id)
    successor.resources.sort(key=lambda item: item.id)
    successor.parent_state_id = state.state_id
    successor.state_id = state_id_for(successor)
    return successor, diff


def _resolve_action(
    action_or_id: CatalystAction | str,
    actions: Iterable[CatalystAction] | None = None,
) -> CatalystAction:
    if isinstance(action_or_id, CatalystAction):
        return action_or_id
    if actions is not None:
        for action in actions:
            if action.id == action_or_id:
                return action
    raise TransitionError(f"unknown action {action_or_id}")


def transition_state(
    state: CommunityState,
    action_or_id: CatalystAction | str,
    actions: Iterable[CatalystAction] | None = None,
) -> TransitionResponse:
    action = _resolve_action(action_or_id, actions)
    successor, diff = apply_action(state, action)
    return TransitionResponse(
        action_id=action.id,
        predecessor_state_id=state.state_id,
        successor_state=successor,
        diff=diff,
    )


def can_apply_action(state: CommunityState, action: CatalystAction) -> bool:
    try:
        _require_action_preconditions(state, action)
        # Validate effect references without mutating the supplied state.  The
        # actual duplicate check is exercised by apply_action on a copy.
        apply_action(state, action)
    except (TransitionError, ValueError):
        return False
    return True


def apply_action_ids(
    state: CommunityState,
    actions_by_id: Mapping[str, CatalystAction],
    action_ids: Iterable[str],
) -> tuple[CommunityState, StateDiff]:
    """Apply an ordered action path immutably, combining machine-readable diffs."""

    current = state
    capability_diff: dict[str, set[str]] = {}
    people_diff: set[str] = set()
    resource_diff: dict[str, int] = {}
    for action_id in action_ids:
        try:
            action = actions_by_id[action_id]
        except KeyError as exc:
            raise TransitionError(f"unknown action {action_id}") from exc
        current, diff = apply_action(current, action)
        for person_id, capabilities in diff.added_capabilities.items():
            capability_diff.setdefault(person_id, set()).update(capabilities)
        people_diff.update(diff.added_people)
        for resource_id, quantity in diff.resource_quantity_changes.items():
            resource_diff[resource_id] = resource_diff.get(resource_id, 0) + quantity
    return current, StateDiff(
        added_capabilities={key: sorted(value) for key, value in sorted(capability_diff.items())},
        added_people=sorted(people_diff),
        resource_quantity_changes=dict(sorted(resource_diff.items())),
    )


def _path_key(path: tuple[CatalystAction, ...]) -> tuple[int, int, tuple[str, ...]]:
    return (
        sum(action.cost for action in path),
        len(path),
        tuple(action.id for action in path),
    )


def ordered_action_paths(
    actions: Iterable[CatalystAction],
    *,
    max_depth: int = 2,
) -> list[tuple[CatalystAction, ...]]:
    """Return every unique non-repeating action path up to the frozen depth."""

    if max_depth < 0 or max_depth > 2:
        raise ValueError("max_depth must be between 0 and 2")
    catalogue = list(actions)
    action_ids = [action.id for action in catalogue]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("action catalogue contains duplicate ids")
    ordered = sorted(catalogue, key=lambda action: action.id)
    paths = [
        tuple(path)
        for size in range(1, min(max_depth, len(ordered)) + 1)
        for path in itertools.permutations(ordered, size)
    ]
    return sorted(paths, key=_path_key)


def find_minimum_unlock(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    actions: Iterable[CatalystAction],
    analyser: AnalysisCallable | None = None,
) -> UnlockResponse:
    """Exhaustively evaluate executable ordered paths up to depth two."""

    catalogue = list(actions)
    action_ids = [action.id for action in catalogue]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("intervention catalogue contains duplicate action ids")
    if not catalogue:
        raise NoUnlockPath(f"no interventions are available for {initiative.id}")

    baseline = call_analyser(analyser, community, initiative)
    if is_feasible(baseline):
        raise AlreadyFeasible(f"initiative {initiative.id} is already feasible")

    candidates = ordered_action_paths(catalogue)
    evaluated = 0
    valid: list[tuple[tuple[int, int, tuple[str, ...]], tuple[CatalystAction, ...], SolverStatus]] = []
    for path in candidates:
        evaluated += 1
        try:
            successor = community
            for action in path:
                successor, _ = apply_action(successor, action)
        except (TransitionError, ValueError):
            continue
        result = call_analyser(analyser, successor, initiative)
        status = coerce_status(result)
        if is_feasible(result):
            valid.append((_path_key(path), path, status))

    if not valid:
        raise NoUnlockPath(
            f"no ordered intervention path makes {initiative.id} feasible after {evaluated} candidates"
        )
    _, path, status = min(valid, key=lambda item: item[0])
    return UnlockResponse(
        label="minimum_modelled_unlock",
        target_initiative_id=initiative.id,
        interventions=[action.id for action in path],
        total_cost=sum(action.cost for action in path),
        catalogue_size=len(catalogue),
        candidate_paths_evaluated=evaluated,
        resulting_status=status,
    )


minimum_modelled_unlock = find_minimum_unlock
enumerate_interventions = find_minimum_unlock
apply_intervention = apply_action
state_hash = canonical_state_hash


def apply_transition(
    state: CommunityState,
    action_or_id: CatalystAction | str,
    actions: Iterable[CatalystAction] | None = None,
) -> TransitionResponse:
    """API-friendly transition wrapper accepting an action or catalogue ID."""

    return transition_state(state, action_or_id, actions)


transition = apply_transition
