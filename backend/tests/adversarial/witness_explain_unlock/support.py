"""Independent test oracles and compact fixtures for Sets C, D, and E.

The helpers in this module intentionally do not import the product compiler,
solver, explanation, planner, or intervention implementation.  They model the
small declared predicates directly so expectations remain independent of the
system under test.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import itertools
import json
from typing import Any

from app.api_models import RequirementGroup, SolverStatus
from app.models import (
    AddCapabilityEffect,
    AddPersonEffect,
    AddResourceQuantityEffect,
    CatalystAction,
    CommunityState,
    InitiativeBlueprint,
    OrganisationBlock,
    PersonBlock,
    ResourceBlock,
    ResourceRequirement,
    RoleRequirement,
    SpaceBlock,
    TimeSlot,
    VenueRequirement,
)


def witness_fixture() -> tuple[CommunityState, InitiativeBlueprint]:
    """Return one feasible witness exercising every canonical trace category."""

    community = CommunityState(
        state_id="S0",
        organisations=[OrganisationBlock(id="ORG", name="Test organisation")],
        people=[
            PersonBlock(
                id="ALICE",
                name="Alice",
                organisation_id="ORG",
                capabilities={"host"},
                languages={"en", "ar"},
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11, TimeSlot.SAT_12},
                max_contribution_slots=2,
            ),
            PersonBlock(
                id="BOB",
                name="Bob",
                organisation_id="ORG",
                capabilities={"helper"},
                languages={"en"},
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11, TimeSlot.SAT_12},
                max_contribution_slots=2,
            ),
        ],
        spaces=[
            SpaceBlock(
                id="ROOM_GOOD",
                name="Good room",
                organisation_id="ORG",
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11, TimeSlot.SAT_12},
                capacity=8,
                features={"wifi", "power"},
            ),
            SpaceBlock(
                id="ROOM_BAD",
                name="Small room",
                organisation_id="ORG",
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11, TimeSlot.SAT_12},
                capacity=4,
                features={"wifi"},
            ),
        ],
        resources=[
            ResourceBlock(
                id="KIT",
                name="Workshop kit",
                organisation_id="ORG",
                quantity=2,
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11, TimeSlot.SAT_12},
                shareable=True,
            )
        ],
    )
    initiative = InitiativeBlueprint(
        id="WITNESS_INITIATIVE",
        name="Witness initiative",
        roles=[
            RoleRequirement(
                id="HOST",
                label="Host",
                required_capabilities={"host"},
                required_languages={"ar"},
            )
        ],
        venue=VenueRequirement(minimum_capacity=8, required_features={"wifi", "power"}),
        resources=[ResourceRequirement(resource_id="KIT", quantity=2)],
        candidate_start_slots=[TimeSlot.SAT_10],
        duration_slots=2,
    )
    return community, initiative


def model_json(model: Any) -> Any:
    """Obtain JSON-compatible Pydantic data without product canonical helpers."""

    return model.model_dump(mode="json") if hasattr(model, "model_dump") else model


def _json_canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_json_canonical(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    return value


def independent_state_hash(state: CommunityState) -> str:
    payload = model_json(state)
    payload.pop("state_id", None)
    payload.pop("parent_state_id", None)
    encoded = json.dumps(_json_canonical(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def independent_state_id(state: CommunityState) -> str:
    return f"S{independent_state_hash(state).upper()}"


def _occupied(start: TimeSlot, duration: int) -> tuple[TimeSlot, ...]:
    slots = tuple(TimeSlot)
    index = slots.index(start)
    end = index + duration
    if end > len(slots):
        raise ValueError("occupied slots exceed horizon")
    return slots[index:end]


def independent_witness_legal(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    result: Any,
) -> bool:
    """Plain-Python canonical witness oracle, independent of product replay."""

    if result.initiative_id != initiative.id:
        return False
    if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        return False
    if result.objective_value is None:
        return False

    role_ids = [role.id for role in initiative.roles]
    assignments = list(result.assignments)
    if [item.role_instance_id for item in assignments] != role_ids:
        return False
    if len({item.role_instance_id for item in assignments}) != len(assignments):
        return False
    people = {person.id: person for person in community.people}
    roles = {role.id: role for role in initiative.roles}
    assigned_people: dict[str, PersonBlock] = {}
    for item in assignments:
        person = people.get(item.person_id)
        role = roles.get(item.role_instance_id)
        if person is None or role is None:
            return False
        if not role.required_capabilities.issubset(person.capabilities):
            return False
        if not role.required_languages.issubset(person.languages):
            return False
        assigned_people[item.role_instance_id] = person

    venue_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "venue"]
    time_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "time"]
    resource_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "resource"]
    role_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "role"]
    if len(venue_entries) != 1 or len(time_entries) != 1:
        return False
    if len(role_entries) != len(initiative.roles):
        return False
    if len(resource_entries) != len(initiative.resources):
        return False
    venue_entry, time_entry = venue_entries[0], time_entries[0]
    if len(venue_entry.selected_ids) != 1 or len(time_entry.selected_ids) != 1:
        return False
    venue_id = venue_entry.selected_ids[0]
    try:
        start = TimeSlot(time_entry.selected_ids[0])
        occupied = _occupied(start, initiative.duration_slots)
    except (TypeError, ValueError):
        return False
    if start not in initiative.candidate_start_slots:
        return False

    venue = next((space for space in community.spaces if space.id == venue_id), None)
    if venue is None:
        return False
    if venue.capacity < initiative.venue.minimum_capacity:
        return False
    if not initiative.venue.required_features.issubset(venue.features):
        return False
    if not set(occupied).issubset(venue.available_slots):
        return False
    for person in assigned_people.values():
        if not set(occupied).issubset(person.available_slots):
            return False

    people_roles: dict[str, list[RoleRequirement]] = {}
    for item in assignments:
        people_roles.setdefault(item.person_id, []).append(roles[item.role_instance_id])
    for person_id, person_roles in people_roles.items():
        for left, right in itertools.combinations(person_roles, 2):
            if not (left.allow_shared_person or right.allow_shared_person):
                return False
        shareable = any(
            left.allow_shared_person or right.allow_shared_person
            for left, right in itertools.combinations(person_roles, 2)
        )
        contribution = len(set(occupied)) if shareable else initiative.duration_slots * len(person_roles)
        if contribution > people[person_id].max_contribution_slots:
            return False

    resources = {resource.id: resource for resource in community.resources}
    expected_resource_ids = [requirement.resource_id for requirement in initiative.resources]
    if [entry.requirement_id for entry in resource_entries] != expected_resource_ids:
        return False
    for requirement, entry in zip(initiative.resources, resource_entries, strict=True):
        resource = resources.get(requirement.resource_id)
        if resource is None or resource.quantity < requirement.quantity:
            return False
        if not set(occupied).issubset(resource.available_slots):
            return False

    expected_trace: list[dict[str, Any]] = []
    for role, assignment in zip(initiative.roles, assignments, strict=True):
        facts: dict[str, Any] = {
            "label": role.label,
            "required_capabilities": sorted(role.required_capabilities),
            "required_languages": sorted(role.required_languages),
        }
        if len(role.required_capabilities) == 1:
            facts["capability"] = sorted(role.required_capabilities)[0]
        if len(role.required_languages) == 1:
            facts["language"] = sorted(role.required_languages)[0]
        expected_trace.append(
            {
                "requirement_kind": "role",
                "requirement_id": role.id,
                "selected_ids": [assignment.person_id],
                "facts": facts,
            }
        )
    expected_trace.append(
        {
            "requirement_kind": "venue",
            "requirement_id": "VENUE",
            "selected_ids": [venue.id],
            "facts": {
                "minimum_capacity": initiative.venue.minimum_capacity,
                "required_features": sorted(initiative.venue.required_features),
                "capacity": venue.capacity,
                "features": sorted(venue.features),
            },
        }
    )
    for requirement in initiative.resources:
        resource = resources[requirement.resource_id]
        expected_trace.append(
            {
                "requirement_kind": "resource",
                "requirement_id": requirement.resource_id,
                "selected_ids": [requirement.resource_id],
                "facts": {
                    "quantity_required": requirement.quantity,
                    "quantity_available": resource.quantity,
                    "shareable": resource.shareable,
                },
            }
        )
    expected_trace.append(
        {
            "requirement_kind": "time",
            "requirement_id": "TIME",
            "selected_ids": [start.value],
            "facts": {
                "start_slot": start.value,
                "occupied_slots": [slot.value for slot in occupied],
                "duration_slots": initiative.duration_slots,
            },
        }
    )
    actual_trace = [model_json(entry) for entry in result.assembly_trace]
    if actual_trace != expected_trace:
        return False
    expected_objective = 10 * len({item.person_id for item in assignments}) + 2 * len(assignments)
    return result.objective_value == expected_objective


def _role_status(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    relaxed: Iterable[RequirementGroup] = (),
) -> bool:
    """Independent feasibility predicate used by explanation and planner tests."""

    relaxed_set = set(relaxed)
    people = {person.id: person for person in community.people}
    role_candidates: list[list[PersonBlock]] = []
    for role in initiative.roles:
        role_candidates.append(
            [
                person
                for person in people.values()
                if (RequirementGroup.ROLE_CAPABILITY in relaxed_set or role.required_capabilities <= person.capabilities)
                and (RequirementGroup.LANGUAGE in relaxed_set or role.required_languages <= person.languages)
            ]
        )
    if any(not candidates for candidates in role_candidates):
        return False
    starts: list[tuple[TimeSlot, ...]] = []
    try:
        starts = [_occupied(start, initiative.duration_slots) for start in initiative.candidate_start_slots]
    except ValueError:
        return False
    for selected in itertools.product(*role_candidates):
        by_person: dict[str, list[RoleRequirement]] = {}
        for role, person in zip(initiative.roles, selected, strict=True):
            by_person.setdefault(person.id, []).append(role)
        if any(
            not (left.allow_shared_person or right.allow_shared_person)
            for role_list in by_person.values()
            for left, right in itertools.combinations(role_list, 2)
        ):
            continue
        for occupied in starts:
            if RequirementGroup.AVAILABILITY not in relaxed_set and any(
                not set(occupied).issubset(person.available_slots) for person in selected
            ):
                continue
            if RequirementGroup.MAXIMUM_CONTRIBUTION not in relaxed_set:
                too_much = False
                for person_id, role_list in by_person.items():
                    shareable = any(
                        left.allow_shared_person or right.allow_shared_person
                        for left, right in itertools.combinations(role_list, 2)
                    )
                    contribution = len(set(occupied)) if shareable else initiative.duration_slots * len(role_list)
                    if contribution > people[person_id].max_contribution_slots:
                        too_much = True
                        break
                if too_much:
                    continue
            for venue in community.spaces:
                if RequirementGroup.VENUE_CAPACITY not in relaxed_set and venue.capacity < initiative.venue.minimum_capacity:
                    continue
                if RequirementGroup.VENUE_FEATURE not in relaxed_set and not initiative.venue.required_features <= venue.features:
                    continue
                if RequirementGroup.AVAILABILITY not in relaxed_set and not set(occupied).issubset(venue.available_slots):
                    continue
                resource_ok = True
                resources = {resource.id: resource for resource in community.resources}
                for requirement in initiative.resources:
                    resource = resources.get(requirement.resource_id)
                    if resource is None:
                        resource_ok = False
                        break
                    if RequirementGroup.RESOURCE_QUANTITY not in relaxed_set and resource.quantity < requirement.quantity:
                        resource_ok = False
                        break
                    if RequirementGroup.AVAILABILITY not in relaxed_set and not set(occupied).issubset(resource.available_slots):
                        resource_ok = False
                        break
                if resource_ok:
                    return True
    return False


def status_for(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    relaxed: Iterable[RequirementGroup] = (),
) -> dict[str, str]:
    return {"status": SolverStatus.OPTIMAL.value if _role_status(community, initiative, relaxed) else SolverStatus.INFEASIBLE.value}


def explanation_fixtures() -> dict[RequirementGroup, tuple[CommunityState, InitiativeBlueprint, dict[str, Any]]]:
    """Construct one independently-described singleton blocker per group."""

    fixtures: dict[RequirementGroup, tuple[CommunityState, InitiativeBlueprint, dict[str, Any]]] = {}
    base_community, base_initiative = witness_fixture()

    role_cap_community = base_community.model_copy(deep=True)
    role_cap_community.people[0].capabilities.remove("host")
    fixtures[RequirementGroup.ROLE_CAPABILITY] = (
        role_cap_community,
        base_initiative.model_copy(deep=True),
        {"required": 1, "available": 0, "capability": "host", "relevant_ids": []},
    )

    language_community = base_community.model_copy(deep=True)
    language_community.people[0].languages.remove("ar")
    language_initiative = base_initiative.model_copy(deep=True)
    fixtures[RequirementGroup.LANGUAGE] = (
        language_community,
        language_initiative,
        {"required": 1, "available": 0, "language": "ar", "relevant_ids": []},
    )

    availability_community = base_community.model_copy(deep=True)
    availability_community.people[0].available_slots.remove(TimeSlot.SAT_10)
    availability_initiative = base_initiative.model_copy(deep=True)
    fixtures[RequirementGroup.AVAILABILITY] = (
        availability_community,
        availability_initiative,
        {"required": 1, "available": 0, "requirement_id": "HOST", "relevant_ids": ["ALICE"]},
    )

    feature_community = base_community.model_copy(deep=True)
    feature_community.spaces[0].features.remove("power")
    feature_initiative = base_initiative.model_copy(deep=True)
    fixtures[RequirementGroup.VENUE_FEATURE] = (
        feature_community,
        feature_initiative,
        {"required": 1, "available": 0, "capability": "power", "relevant_ids": []},
    )

    capacity_community = base_community.model_copy(deep=True)
    capacity_community.spaces[0].capacity = 7
    capacity_initiative = base_initiative.model_copy(deep=True)
    fixtures[RequirementGroup.VENUE_CAPACITY] = (
        capacity_community,
        capacity_initiative,
        {"required": 8, "available": 7, "requirement_id": "venue", "relevant_ids": ["ROOM_GOOD"]},
    )

    resource_community = base_community.model_copy(deep=True)
    resource_community.resources[0].quantity = 1
    resource_initiative = base_initiative.model_copy(deep=True)
    fixtures[RequirementGroup.RESOURCE_QUANTITY] = (
        resource_community,
        resource_initiative,
        {"required": 2, "available": 1, "requirement_id": "KIT", "relevant_ids": ["KIT"]},
    )

    contribution_community = base_community.model_copy(deep=True)
    contribution_community.people[0].max_contribution_slots = 1
    contribution_initiative = base_initiative.model_copy(deep=True)
    contribution_initiative.roles.append(
        RoleRequirement(
            id="SECOND_HOST",
            label="Second host",
            required_capabilities={"host"},
            required_languages={"ar"},
            allow_shared_person=True,
        )
    )
    contribution_initiative.roles[0].allow_shared_person = True
    fixtures[RequirementGroup.MAXIMUM_CONTRIBUTION] = (
        contribution_community,
        contribution_initiative,
        {"required": 2, "available": 0, "requirement_id": "roles", "relevant_ids": []},
    )
    return fixtures


@dataclass(frozen=True)
class PathCandidate:
    actions: tuple[CatalystAction, ...]
    key: tuple[int, int, tuple[str, ...]]


def independent_action_paths(
    actions: Sequence[CatalystAction],
    *,
    max_depth: int = 2,
) -> list[PathCandidate]:
    if max_depth < 0 or max_depth > 2:
        raise ValueError("max_depth must be between 0 and 2")
    ordered = sorted(actions, key=lambda action: action.id)
    paths = [
        tuple(path)
        for size in range(1, min(max_depth, len(ordered)) + 1)
        for path in itertools.permutations(ordered, size)
    ]
    return [
        PathCandidate(path, (sum(action.cost for action in path), len(path), tuple(action.id for action in path)))
        for path in sorted(paths, key=lambda path: (sum(action.cost for action in path), len(path), tuple(action.id for action in path)))
    ]


def independent_apply(state: CommunityState, action: CatalystAction) -> CommunityState:
    """Apply the declared additive effects on a copy using plain predicates."""

    successor = state.model_copy(deep=True)
    people = {person.id: person for person in successor.people}
    spaces = {space.id: space for space in successor.spaces}
    resources = {resource.id: resource for resource in successor.resources}
    for requirement in action.preconditions.person_capabilities:
        if requirement.person_id not in people or requirement.capability_id not in people[requirement.person_id].capabilities:
            raise ValueError("person capability precondition failed")
    for requirement in action.preconditions.willing_learners:
        if requirement.person_id not in people or requirement.capability_id not in people[requirement.person_id].willing_to_learn:
            raise ValueError("learner precondition failed")
    for requirement in action.preconditions.space_availability:
        if requirement.space_id not in spaces or not requirement.slots.issubset(spaces[requirement.space_id].available_slots):
            raise ValueError("space precondition failed")

    changed = False
    organisation_ids = {organisation.id for organisation in successor.organisations}
    for effect in action.effects:
        if isinstance(effect, AddCapabilityEffect):
            person = people.get(effect.person_id)
            if person is None:
                raise ValueError("missing effect person")
            if effect.capability_id in person.capabilities:
                continue
            person.capabilities.add(effect.capability_id)
            changed = True
        elif isinstance(effect, AddPersonEffect):
            if effect.person.id in people or effect.person.organisation_id not in organisation_ids:
                raise ValueError("duplicate or missing effect reference")
            person = effect.person.model_copy(deep=True)
            successor.people.append(person)
            people[person.id] = person
            changed = True
        elif isinstance(effect, AddResourceQuantityEffect):
            resource = resources.get(effect.resource_id)
            if resource is None:
                raise ValueError("missing effect resource")
            resource.quantity += effect.quantity
            changed = True
        else:
            raise ValueError("unsupported effect")
    if not changed:
        raise ValueError("no-op action")
    successor.organisations.sort(key=lambda item: item.id)
    successor.people.sort(key=lambda item: item.id)
    successor.spaces.sort(key=lambda item: item.id)
    successor.resources.sort(key=lambda item: item.id)
    successor.parent_state_id = state.state_id
    successor.state_id = independent_state_id(successor)
    return successor


def action(
    identifier: str,
    *,
    cost: int,
    effects: Sequence[Any],
    person_capabilities: Sequence[tuple[str, str]] = (),
    willing_learners: Sequence[tuple[str, str]] = (),
    space_slots: Sequence[tuple[str, set[TimeSlot]]] = (),
) -> CatalystAction:
    return CatalystAction(
        id=identifier,
        name=identifier,
        cost=cost,
        preconditions={
            "person_capabilities": [
                {"person_id": person_id, "capability_id": capability}
                for person_id, capability in person_capabilities
            ],
            "willing_learners": [
                {"person_id": person_id, "capability_id": capability}
                for person_id, capability in willing_learners
            ],
            "space_availability": [
                {"space_id": space_id, "slots": slots}
                for space_id, slots in space_slots
            ],
        },
        effects=list(effects),
    )


def planner_fixture() -> tuple[CommunityState, InitiativeBlueprint]:
    community = CommunityState(
        state_id="S0",
        organisations=[OrganisationBlock(id="ORG", name="Org")],
        people=[
            PersonBlock(
                id="TRAINER",
                name="Trainer",
                organisation_id="ORG",
                capabilities={"train"},
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11},
                max_contribution_slots=2,
            ),
            PersonBlock(
                id="LEARNER",
                name="Learner",
                organisation_id="ORG",
                willing_to_learn={"target"},
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11},
                max_contribution_slots=2,
            ),
        ],
        spaces=[
            SpaceBlock(
                id="ROOM",
                name="Room",
                organisation_id="ORG",
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11},
                capacity=10,
                features={"wifi"},
            )
        ],
        resources=[
            ResourceBlock(
                id="KIT",
                name="Kit",
                organisation_id="ORG",
                quantity=1,
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11},
                shareable=True,
            ),
            ResourceBlock(
                id="NOISE",
                name="Noise resource",
                organisation_id="ORG",
                quantity=0,
                available_slots={TimeSlot.SAT_10, TimeSlot.SAT_11},
                shareable=True,
            ),
        ],
    )
    initiative = InitiativeBlueprint(
        id="TARGET_INITIATIVE",
        name="Target initiative",
        roles=[RoleRequirement(id="TARGET_ROLE", label="Target role", required_capabilities={"target"})],
        venue=VenueRequirement(minimum_capacity=1, required_features={"wifi"}),
        resources=[ResourceRequirement(resource_id="KIT", quantity=2)],
        candidate_start_slots=[TimeSlot.SAT_10],
        duration_slots=1,
    )
    return community, initiative


def training_action() -> CatalystAction:
    return action(
        "Z_TRAIN",
        cost=1,
        person_capabilities=[("TRAINER", "train")],
        willing_learners=[("LEARNER", "target")],
        space_slots=[("ROOM", {TimeSlot.SAT_10})],
        effects=[AddCapabilityEffect(type="add_capability", person_id="LEARNER", capability_id="target")],
    )


def resource_action() -> CatalystAction:
    return action(
        "A_RESOURCE",
        cost=1,
        person_capabilities=[("LEARNER", "target")],
        effects=[AddResourceQuantityEffect(type="add_resource_quantity", resource_id="KIT", quantity=1)],
    )


def irrelevant_action() -> CatalystAction:
    return action(
        "CHEAP_NOISE",
        cost=0,
        effects=[AddResourceQuantityEffect(type="add_resource_quantity", resource_id="NOISE", quantity=1)],
    )


def direct_target_action(identifier: str = "DIRECT_TARGET", *, cost: int = 2) -> CatalystAction:
    return action(
        identifier,
        cost=cost,
        effects=[AddCapabilityEffect(type="add_capability", person_id="LEARNER", capability_id="target")],
    )


def independent_target_status(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed: Iterable[RequirementGroup] = (),
) -> dict[str, str]:
    return status_for(community, initiative, relaxed)


def diff_paths(before: Any, after: Any) -> list[tuple[tuple[Any, ...], Any, Any]]:
    """Return leaf/collection changes for asserting one named witness mutation."""

    changes: list[tuple[tuple[Any, ...], Any, Any]] = []

    def walk(left: Any, right: Any, path: tuple[Any, ...]) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            keys = set(left) | set(right)
            for key in sorted(keys, key=str):
                if key not in left or key not in right:
                    changes.append((path + (key,), left.get(key), right.get(key)))
                else:
                    walk(left[key], right[key], path + (key,))
            return
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                changes.append((path + ("<length>",), len(left), len(right)))
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                walk(left_item, right_item, path + (index,))
            return
        if left != right:
            changes.append((path, left, right))

    walk(model_json(before), model_json(after), ())
    return changes
