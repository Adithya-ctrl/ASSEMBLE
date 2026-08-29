"""Test-owned expectations for the structural resilience acceptance gaps.

This module intentionally does not import the production compiler, solver,
transition, resilience, recompiler, frontier, or witness helpers.  It is a
small, deliberately boring model used to calculate expected feasibility,
burden, catalogue entries, action applicability, and counterfactual receipts.
The production implementations are exercised by the tests that consume these
helpers, never by the helpers themselves.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from hashlib import sha256
import itertools
import json
from typing import Any

from app.api_models import (
    PersonUnavailablePerturbation,
    PerturbationType,
    ResourceAvailabilityPerturbation,
    StateDiff,
    VenueUnavailablePerturbation,
)
from app.models import (
    AddCapabilityEffect,
    AddPersonEffect,
    AddResourceQuantityEffect,
    CatalystAction,
    CommunityState,
    InitiativeBlueprint,
    ORDERED_TIME_SLOTS,
    PersonBlock,
    RoleRequirement,
    TimeSlot,
    occupied_slots,
)


def _json_value(value: Any) -> Any:
    """Canonicalise JSON values the same way the wire contract does.

    This is intentionally a local implementation.  In particular, no
    production state-hash helper is used to derive any expected value.
    """

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_json_value(item) for item in value]
        return sorted(
            values,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )
    return value


def canonical_content(state: CommunityState) -> dict[str, Any]:
    """Return state content without operational identity or lineage."""

    payload = state.model_dump(mode="json")
    payload.pop("state_id", None)
    payload.pop("parent_state_id", None)
    return _json_value(payload)


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def content_hash(state: CommunityState) -> str:
    return sha256(canonical_json(canonical_content(state)).encode("utf-8")).hexdigest()


def state_id(state: CommunityState) -> str:
    return f"S{content_hash(state).upper()}"


def _slot_set(slots: Iterable[TimeSlot | str]) -> set[TimeSlot]:
    return {
        slot if isinstance(slot, TimeSlot) else TimeSlot(str(slot))
        for slot in slots
    }


def occupied(start: TimeSlot, duration: int) -> tuple[TimeSlot, ...]:
    """Independent horizon arithmetic for the tiny oracle."""

    index = ORDERED_TIME_SLOTS.index(start)
    end = index + duration
    if end > len(ORDERED_TIME_SLOTS):
        raise ValueError("occupied slots exceed the declared horizon")
    return ORDERED_TIME_SLOTS[index:end]


def _role_person_pairs(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Iterable[str] = (),
) -> Iterable[tuple[tuple[str, str], ...]]:
    relaxed = {getattr(group, "value", str(group)) for group in relaxed_groups}
    people = sorted(state.people, key=lambda item: item.id)
    candidate_lists: list[list[PersonBlock]] = []
    for role in initiative.roles:
        candidates = []
        for person in people:
            if (
                "role_capability" not in relaxed
                and not role.required_capabilities <= person.capabilities
            ):
                continue
            if (
                "language" not in relaxed
                and not role.required_languages <= person.languages
            ):
                continue
            candidates.append(person)
        candidate_lists.append(candidates)

    for selected in itertools.product(*candidate_lists):
        yield tuple(
            (role.id, person.id)
            for role, person in zip(initiative.roles, selected)
        )


def legal_assemblies(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Iterable[str] = (),
) -> list[tuple[tuple[tuple[str, str], ...], str, TimeSlot, int]]:
    """Enumerate every legal tiny-domain assembly and its burden.

    This enumerator mirrors the *declared domain facts* directly.  It does
    not ask CP-SAT for a witness or call any production replay implementation.
    """

    relaxed = {getattr(group, "value", str(group)) for group in relaxed_groups}
    people = {item.id: item for item in state.people}
    spaces = {item.id: item for item in state.spaces}
    resources = {item.id: item for item in state.resources}
    role_by_id = {role.id: role for role in initiative.roles}
    assemblies: list[tuple[tuple[tuple[str, str], ...], str, TimeSlot, int]] = []

    try:
        starts = [
            (start, occupied(start, initiative.duration_slots))
            for start in initiative.candidate_start_slots
        ]
    except ValueError:
        return []

    for pair_tuple in _role_person_pairs(
        state,
        initiative,
        relaxed_groups=relaxed,
    ):
        assignment = dict(pair_tuple)
        selected_people = {role_id: people[person_id] for role_id, person_id in pair_tuple if person_id in people}
        if len(selected_people) != len(pair_tuple):
            continue

        # A person may be shared only when at least one of the two role
        # declarations explicitly permits it.
        by_person: dict[str, list[RoleRequirement]] = {}
        for role_id, person_id in pair_tuple:
            by_person.setdefault(person_id, []).append(role_by_id[role_id])
        invalid_sharing = any(
            not all(
                left.allow_shared_person or right.allow_shared_person
                for left, right in itertools.combinations(roles, 2)
            )
            for roles in by_person.values()
            if len(roles) > 1
        )
        if invalid_sharing:
            continue

        if "maximum_contribution" not in relaxed:
            # Contribution depends on the selected start when sharing is
            # enabled, so it is checked inside the start loop below.
            pass

        for start, occupied_slots in starts:
            occupied_set = set(occupied_slots)

            if "availability" not in relaxed:
                if any(
                    not occupied_set <= person.available_slots
                    for person in selected_people.values()
                ):
                    continue

            if "maximum_contribution" not in relaxed:
                contribution_bad = False
                for person_id, roles in by_person.items():
                    shared = any(
                        left.allow_shared_person or right.allow_shared_person
                        for left, right in itertools.combinations(roles, 2)
                    )
                    contribution = (
                        len(occupied_slots)
                        if shared
                        else initiative.duration_slots * len(roles)
                    )
                    if contribution > people[person_id].max_contribution_slots:
                        contribution_bad = True
                        break
                if contribution_bad:
                    continue

            for venue in sorted(state.spaces, key=lambda item: item.id):
                if (
                    "venue_capacity" not in relaxed
                    and venue.capacity < initiative.venue.minimum_capacity
                ):
                    continue
                if (
                    "venue_feature" not in relaxed
                    and not initiative.venue.required_features <= venue.features
                ):
                    continue
                if (
                    "availability" not in relaxed
                    and not occupied_set <= venue.available_slots
                ):
                    continue

                resource_ok = True
                for requirement in initiative.resources:
                    resource = resources.get(requirement.resource_id)
                    # Missing references are integrity failures, never a
                    # relaxable quantity/availability fact.
                    if resource is None:
                        resource_ok = False
                        break
                    if (
                        "resource_quantity" not in relaxed
                        and resource.quantity < requirement.quantity
                    ):
                        resource_ok = False
                        break
                    if (
                        "availability" not in relaxed
                        and not occupied_set <= resource.available_slots
                    ):
                        resource_ok = False
                        break
                if not resource_ok:
                    continue

                burden = 10 * len(set(assignment.values())) + 2 * len(pair_tuple)
                assemblies.append((pair_tuple, venue.id, start, burden))

    return assemblies


def is_feasible(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Iterable[str] = (),
) -> bool:
    return bool(legal_assemblies(state, initiative, relaxed_groups=relaxed_groups))


def minimum_burden(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Iterable[str] = (),
) -> int | None:
    assemblies = legal_assemblies(state, initiative, relaxed_groups=relaxed_groups)
    return min((item[3] for item in assemblies), default=None)


def assignment_tuple(result: Any) -> tuple[tuple[str, str], ...]:
    """Extract a SUT witness without validating it through production code."""

    return tuple(
        (item.role_instance_id, item.person_id)
        for item in result.assignments
    )


def oracle_spec_dicts(
    state: CommunityState,
    initiative: InitiativeBlueprint,
    baseline_assignments: Sequence[tuple[str, str]],
    venue_id: str,
) -> list[dict[str, Any]]:
    """Build the complete witness-derived perturbation catalogue locally."""

    source_hash = content_hash(state)
    people = {person.id: person for person in state.people}
    spaces = {space.id: space for space in state.spaces}
    requirements = {
        requirement.resource_id: requirement
        for requirement in initiative.resources
    }
    selected_people = sorted({person_id for _, person_id in baseline_assignments})
    specs: list[dict[str, Any]] = []
    for person_id in selected_people:
        person = people[person_id]
        perturbation_type = PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE.value
        specs.append(
            {
                "id": f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_hash.upper()}_{perturbation_type}_{person_id}",
                "type": perturbation_type,
                "initiative_id": initiative.id,
                "target_id": person_id,
                "label": f"{person.name} becomes unavailable",
                "source_content_hash": source_hash,
                "before_available_slots": sorted(
                    (slot.value for slot in person.available_slots)
                ),
                "after_available_slots": [],
            }
        )
    venue = spaces[venue_id]
    perturbation_type = PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE.value
    specs.append(
        {
            "id": f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_hash.upper()}_{perturbation_type}_{venue_id}",
            "type": perturbation_type,
            "initiative_id": initiative.id,
            "target_id": venue_id,
            "label": f"{venue.name} becomes unavailable",
            "source_content_hash": source_hash,
            "before_available_slots": sorted(
                (slot.value for slot in venue.available_slots)
            ),
            "after_available_slots": [],
        }
    )
    for resource_id in sorted(requirements):
        requirement = requirements[resource_id]
        resource = next(item for item in state.resources if item.id == resource_id)
        perturbation_type = PerturbationType.REDUCE_AVAILABLE_RESOURCE.value
        specs.append(
            {
                "id": f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_hash.upper()}_{perturbation_type}_{resource_id}",
                "type": perturbation_type,
                "initiative_id": initiative.id,
                "target_id": resource_id,
                "label": f"{resource.name} availability reduced",
                "source_content_hash": source_hash,
                "requirement_id": resource_id,
                "required_quantity": requirement.quantity,
                "before_quantity": resource.quantity,
                "after_quantity": max(0, requirement.quantity - 1),
            }
        )
    return specs


def apply_perturbation_locally(
    state: CommunityState,
    perturbation: Any,
) -> CommunityState:
    """Apply only the declared one-fact mutation to a fresh state copy."""

    result = state.model_copy(deep=True)
    if perturbation.type is PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE:
        target = next(person for person in result.people if person.id == perturbation.target_id)
        target.available_slots = set()
    elif perturbation.type is PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE:
        target = next(space for space in result.spaces if space.id == perturbation.target_id)
        target.available_slots = set()
    elif perturbation.type is PerturbationType.REDUCE_AVAILABLE_RESOURCE:
        target = next(resource for resource in result.resources if resource.id == perturbation.target_id)
        target.quantity = perturbation.after_quantity
    else:  # pragma: no cover - Pydantic's discriminated union is exhaustive.
        raise ValueError(f"unsupported perturbation type {perturbation.type!r}")
    return result


def perturbation_receipt_id(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: Any,
    scenario: CommunityState,
) -> str:
    payload = {
        "namespace": "CF_STRESS_V1",
        "source_content_hash": content_hash(source),
        "initiative_id": initiative.id,
        "perturbation": perturbation.model_dump(mode="json"),
        "perturbed_content": canonical_content(scenario),
    }
    digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest().upper()
    return f"CF_STRESS_V1_{digest}"


def changed_fields(
    before: CommunityState,
    after: CommunityState,
) -> list[tuple[str, str, str]]:
    """Compare entity facts while ignoring operational identity/lineage."""

    changes: list[tuple[str, str, str]] = []
    for collection in ("organisations", "people", "spaces", "resources"):
        before_items = {
            item["id"]: item
            for item in before.model_dump(mode="json")[collection]
        }
        after_items = {
            item["id"]: item
            for item in after.model_dump(mode="json")[collection]
        }
        if before_items.keys() != after_items.keys():
            changes.append((collection, "<identity>", "<collection>"))
            continue
        for item_id in before_items:
            left = before_items[item_id]
            right = after_items[item_id]
            for field in left:
                if field == "id":
                    continue
                left_value = _json_value(left[field])
                right_value = _json_value(right[field])
                if left_value != right_value:
                    changes.append((collection, item_id, field))
    return changes


def action_is_applicable(state: CommunityState, action: CatalystAction) -> bool:
    people = {person.id: person for person in state.people}
    spaces = {space.id: space for space in state.spaces}
    resources = {resource.id: resource for resource in state.resources}
    for requirement in action.preconditions.person_capabilities:
        person = people.get(requirement.person_id)
        if person is None or requirement.capability_id not in person.capabilities:
            return False
    for requirement in action.preconditions.willing_learners:
        person = people.get(requirement.person_id)
        if person is None or requirement.capability_id not in person.willing_to_learn:
            return False
    for requirement in action.preconditions.space_availability:
        space = spaces.get(requirement.space_id)
        if space is None or not set(requirement.slots) <= space.available_slots:
            return False
    for effect in action.effects:
        if isinstance(effect, AddCapabilityEffect):
            person = people.get(effect.person_id)
            if person is None:
                return False
        elif isinstance(effect, AddPersonEffect):
            if effect.person.id in people:
                return False
            if effect.person.organisation_id not in {
                organisation.id for organisation in state.organisations
            }:
                return False
        elif isinstance(effect, AddResourceQuantityEffect):
            if effect.resource_id not in resources:
                return False
    # A valid action must actually change at least one declared fact.
    return any(
        (
            isinstance(effect, AddCapabilityEffect)
            and effect.capability_id not in people[effect.person_id].capabilities
        )
        or isinstance(effect, AddPersonEffect)
        or isinstance(effect, AddResourceQuantityEffect)
        for effect in action.effects
    )


def apply_action_locally(
    state: CommunityState,
    action: CatalystAction,
) -> tuple[CommunityState, StateDiff]:
    """Apply additive catalyst effects without invoking production actions."""

    if not action_is_applicable(state, action):
        raise ValueError(f"action {action.id} is not applicable")
    result = state.model_copy(deep=True)
    people = {person.id: person for person in result.people}
    resources = {resource.id: resource for resource in result.resources}
    added_capabilities: dict[str, set[str]] = {}
    added_people: set[str] = set()
    resource_changes: dict[str, int] = {}
    for effect in action.effects:
        if isinstance(effect, AddCapabilityEffect):
            person = people[effect.person_id]
            if effect.capability_id not in person.capabilities:
                person.capabilities.add(effect.capability_id)
                added_capabilities.setdefault(person.id, set()).add(effect.capability_id)
        elif isinstance(effect, AddPersonEffect):
            person = effect.person.model_copy(deep=True)
            result.people.append(person)
            people[person.id] = person
            added_people.add(person.id)
        elif isinstance(effect, AddResourceQuantityEffect):
            resource = resources[effect.resource_id]
            resource.quantity += effect.quantity
            resource_changes[resource.id] = resource_changes.get(resource.id, 0) + effect.quantity
    result.organisations.sort(key=lambda item: item.id)
    result.people.sort(key=lambda item: item.id)
    result.spaces.sort(key=lambda item: item.id)
    result.resources.sort(key=lambda item: item.id)
    predecessor = state.state_id
    result.parent_state_id = predecessor
    result.state_id = state_id(result)
    return result, StateDiff(
        added_capabilities={
            person_id: sorted(values)
            for person_id, values in sorted(added_capabilities.items())
        },
        added_people=sorted(added_people),
        resource_quantity_changes=dict(sorted(resource_changes.items())),
    )


def reconstruct_path_locally(
    base: CommunityState,
    path: Sequence[str],
    actions: Sequence[CatalystAction],
) -> CommunityState:
    actions_by_id = {action.id: action for action in actions}
    result = base.model_copy(deep=True)
    for action_id in path:
        result, _ = apply_action_locally(result, actions_by_id[action_id])
    return result


def frontier_receipt_id(
    source: CommunityState,
    action: CatalystAction,
    scenario: CommunityState,
) -> str:
    payload = {
        "namespace": "CF_FRONTIER_V1",
        "source_content_hash": content_hash(source),
        "action": action.model_dump(mode="json"),
        "counterfactual_content": canonical_content(scenario),
    }
    digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest().upper()
    return f"CF_FRONTIER_V1_{digest}"


def recompile_oracle(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    scenario: CommunityState,
    baseline_assignment: Mapping[str, str],
) -> dict[str, Any] | None:
    """Calculate the exact two-stage objective for a tiny scenario."""

    assemblies = legal_assemblies(scenario, initiative)
    if not assemblies:
        return None
    scored = [
        (
            sum(
                person_id != baseline_assignment[role_id]
                for role_id, person_id in assignment
            ),
            burden,
            assignment,
            venue_id,
            start,
        )
        for assignment, venue_id, start, burden in assemblies
    ]
    minimum_changes = min(item[0] for item in scored)
    minimum_burden = min(item[1] for item in scored if item[0] == minimum_changes)
    # The custom fixture used by the recompile tests has a unique assignment
    # at both stages.  Keep the deterministic tie selection explicit for
    # diagnostics if a future tiny fixture introduces another exact tie.
    chosen = min(
        (
            item
            for item in scored
            if item[0] == minimum_changes and item[1] == minimum_burden
        ),
        key=lambda item: (item[2], item[3], item[4].value),
    )
    return {
        "minimum_changes": minimum_changes,
        "burden": minimum_burden,
        "assignment": chosen[2],
        "venue_id": chosen[3],
        "start": chosen[4],
    }
