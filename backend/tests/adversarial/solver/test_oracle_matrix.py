"""Independent, deterministic solver/orchestration oracles.

This namespace is intentionally separate from the product's fixture-oriented
tests.  The cases below generate tiny valid domains from fixed seeds and use a
plain-Python exhaustive oracle for the assignment/venue/start semantics.  The
matrix is the Tier-0 adversarial lane for the A-I solver dimensions (role
eligibility, language, availability, venue, resources, sharing, contribution,
objective, and witness replay), plus P (planning/projects), U (UNKNOWN), and X
(counterfactual/frontier/recompiler boundaries).

The oracle never imports compiler internals or CP-SAT variable maps.  It only
implements the declared domain predicates and the public burden formula.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from itertools import permutations, product
import random

import pytest
from pydantic import ValidationError

from app import resilience
from app.api_models import (
    CapabilityFrontierRequest,
    RecompileRequest,
    SolverStatus,
)
from app.compiler import (
    AVAILABILITY,
    LANGUAGE,
    MAXIMUM_CONTRIBUTION,
    RESOURCE_QUANTITY,
    ROLE_CAPABILITY,
    VENUE_CAPACITY,
    VENUE_FEATURE,
    REQUIREMENT_GROUPS,
    compile_initiative,
    normalise_relax_groups,
)
from app.fixture import fresh_demo_fixture
from app.frontier import evaluate_capability_frontier
from app.interventions import (
    ActionAlreadyApplied,
    apply_action,
    apply_action_ids,
    canonical_state_hash,
    ordered_action_paths,
    state_id_for,
)
from app.models import (
    AddCapabilityEffect,
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
from app.project_models import CreateProjectRequest
from app.projects import create_project_from_plan
from app.planner import plan_catalyst
from app.interventions import find_minimum_unlock
from app.recompiler import recompile_minimum_disruption
from app.solver import (
    replay_assignment,
    solve_initiative,
    validate_analysis_witness,
)


SLOT_VALUES = tuple(TimeSlot)
CAPABILITIES = ("cap_a", "cap_b", "cap_c")
LANGUAGES = ("en", "ar")
FEATURES = ("wifi", "power", "accessible")


def _subset(rng: random.Random, values: Sequence[str], *, allow_empty: bool = True) -> set[str]:
    choices = [value for value in values if rng.randrange(2)]
    if not allow_empty and not choices:
        choices.append(values[rng.randrange(len(values))])
    return set(choices)


def _slot_subset(rng: random.Random, *, allow_empty: bool = True) -> set[TimeSlot]:
    choices = [slot for slot in SLOT_VALUES if rng.randrange(2)]
    if not allow_empty and not choices:
        choices.append(SLOT_VALUES[rng.randrange(len(SLOT_VALUES))])
    return set(choices)


def _tiny_case(seed: int) -> tuple[CommunityState, InitiativeBlueprint]:
    """Build one small but semantically varied valid model from ``seed``."""

    rng = random.Random(seed)
    people: list[PersonBlock] = []
    for index in range(rng.randint(1, 4)):
        available = _slot_subset(rng, allow_empty=False)
        people.append(
            PersonBlock(
                id=f"P{index}",
                name=f"Person {index}",
                organisation_id="ORG",
                capabilities=_subset(rng, CAPABILITIES),
                languages=_subset(rng, LANGUAGES),
                willing_to_learn=_subset(rng, CAPABILITIES),
                available_slots=available,
                max_contribution_slots=rng.randint(1, len(available)),
            )
        )

    spaces: list[SpaceBlock] = []
    for index in range(rng.randint(1, 2)):
        spaces.append(
            SpaceBlock(
                id=f"V{index}",
                name=f"Venue {index}",
                organisation_id="ORG",
                available_slots=_slot_subset(rng),
                capacity=rng.randint(0, 10),
                features=_subset(rng, FEATURES),
            )
        )

    resources: list[ResourceBlock] = []
    for index in range(rng.randint(0, 2)):
        resources.append(
            ResourceBlock(
                id=f"RES{index}",
                name=f"Resource {index}",
                organisation_id="ORG",
                quantity=rng.randint(0, 5),
                available_slots=_slot_subset(rng),
                shareable=bool(rng.randrange(2)),
            )
        )

    duration = rng.randint(1, 3)
    valid_starts = [
        slot
        for slot in SLOT_VALUES
        if SLOT_VALUES.index(slot) + duration <= len(SLOT_VALUES)
    ]
    starts = rng.sample(valid_starts, rng.randint(1, len(valid_starts)))
    roles: list[RoleRequirement] = []
    for index in range(rng.randint(1, 3)):
        roles.append(
            RoleRequirement(
                id=f"R{index}",
                label=f"Role {index}",
                required_capabilities=_subset(rng, CAPABILITIES),
                required_languages=_subset(rng, LANGUAGES),
                allow_shared_person=bool(rng.randrange(2)),
            )
        )

    requirements: list[ResourceRequirement] = []
    if resources:
        selected_resources = rng.sample(resources, rng.randint(0, len(resources)))
        requirements = [
            ResourceRequirement(resource_id=resource.id, quantity=rng.randint(1, 5))
            for resource in selected_resources
        ]

    community = CommunityState(
        state_id=f"S{seed:08X}",
        organisations=[OrganisationBlock(id="ORG", name="Org")],
        people=people,
        spaces=spaces,
        resources=resources,
    )
    initiative = InitiativeBlueprint(
        id=f"I{seed:08X}",
        name="Tiny initiative",
        roles=roles,
        venue=VenueRequirement(
            minimum_capacity=rng.randint(0, 10),
            required_features=_subset(rng, FEATURES),
        ),
        resources=requirements,
        candidate_start_slots=starts,
        duration_slots=duration,
    )
    return community, initiative


def _tiny_oracle(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    relaxed_groups: Iterable[str] = (),
) -> list[tuple[tuple[tuple[str, str], ...], str, str, int]]:
    """Enumerate every legal witness without using compiler/solver internals."""

    relaxed = set(relaxed_groups)
    people = {person.id: person for person in community.people}
    roles = list(initiative.roles)
    role_candidates = [
        [
            person
            for person in people.values()
            if (
                ROLE_CAPABILITY in relaxed
                or role.required_capabilities <= person.capabilities
            )
            and (
                LANGUAGE in relaxed
                or role.required_languages <= person.languages
            )
        ]
        for role in roles
    ]

    witnesses: list[tuple[tuple[tuple[str, str], ...], str, str, int]] = []
    for selected_people in product(*role_candidates):
        assigned: dict[str, list[RoleRequirement]] = {}
        for role, person in zip(roles, selected_people, strict=True):
            assigned.setdefault(person.id, []).append(role)
        if any(
            not (
                left.allow_shared_person
                or right.allow_shared_person
            )
            for person_roles in assigned.values()
            for left, right in permutations(person_roles, 2)
            if person_roles.index(left) < person_roles.index(right)
        ):
            continue

        for start in initiative.candidate_start_slots:
            start_index = SLOT_VALUES.index(start)
            occupied = SLOT_VALUES[start_index : start_index + initiative.duration_slots]
            if AVAILABILITY not in relaxed and any(
                not set(occupied) <= people[person.id].available_slots
                for person in selected_people
            ):
                continue
            if MAXIMUM_CONTRIBUTION not in relaxed:
                contribution_ok = True
                for person_id, person_roles in assigned.items():
                    shareable_pair = any(
                        left.allow_shared_person or right.allow_shared_person
                        for left, right in permutations(person_roles, 2)
                        if person_roles.index(left) < person_roles.index(right)
                    )
                    contribution = (
                        len(set(occupied))
                        if shareable_pair
                        else initiative.duration_slots * len(person_roles)
                    )
                    if contribution > people[person_id].max_contribution_slots:
                        contribution_ok = False
                        break
                if not contribution_ok:
                    continue

            assignment_pairs = tuple(
                (role.id, person.id)
                for role, person in zip(roles, selected_people, strict=True)
            )
            # Keep the oracle formula local: the product's burden helper is
            # deliberately not used to calculate the expected objective.
            objective = 10 * len({person_id for _, person_id in assignment_pairs}) + 2 * len(
                assignment_pairs
            )
            for venue in community.spaces:
                if (
                    VENUE_CAPACITY not in relaxed
                    and venue.capacity < initiative.venue.minimum_capacity
                ):
                    continue
                if (
                    VENUE_FEATURE not in relaxed
                    and not initiative.venue.required_features <= venue.features
                ):
                    continue
                if AVAILABILITY not in relaxed and not set(occupied) <= venue.available_slots:
                    continue
                resource_ok = True
                for requirement in initiative.resources:
                    resource = next(
                        (item for item in community.resources if item.id == requirement.resource_id),
                        None,
                    )
                    if resource is None:
                        resource_ok = False
                        break
                    if (
                        RESOURCE_QUANTITY not in relaxed
                        and resource.quantity < requirement.quantity
                    ):
                        resource_ok = False
                        break
                    if AVAILABILITY not in relaxed and not set(occupied) <= resource.available_slots:
                        resource_ok = False
                        break
                if resource_ok:
                    witnesses.append((assignment_pairs, venue.id, start.value, objective))
    return witnesses


def _result_witness(result) -> tuple[tuple[tuple[str, str], ...], str, str]:
    assignments = tuple(
        (item.role_instance_id, item.person_id) for item in result.assignments
    )
    venue = next(item for item in result.assembly_trace if item.requirement_kind == "venue")
    time = next(item for item in result.assembly_trace if item.requirement_kind == "time")
    return assignments, venue.selected_ids[0], time.selected_ids[0]


ORACLE_SEEDS = tuple(0xA100 + index * 37 for index in range(192))


@pytest.mark.parametrize("seed", ORACLE_SEEDS, ids=lambda seed: f"seed_{seed:04X}")
def test_tiny_solver_matches_exhaustive_legal_witness_oracle(seed: int) -> None:
    community, initiative = _tiny_case(seed)
    expected = _tiny_oracle(community, initiative)
    result = solve_initiative(
        community,
        initiative,
        time_limit_seconds=2.0,
        random_seed=seed,
        num_search_workers=1,
    )

    if not expected:
        assert result.status is SolverStatus.INFEASIBLE, f"seed={seed}"
        assert result.objective_value is None
        assert result.assignments == []
        assert result.assembly_trace == []
        return

    assert result.status is SolverStatus.OPTIMAL, f"seed={seed}"
    minimum = min(item[3] for item in expected)
    assert result.objective_value == minimum, f"seed={seed}"
    witness = _result_witness(result)
    legal_at_minimum = {
        (item[0], item[1], item[2])
        for item in expected
        if item[3] == minimum
    }
    assert witness in legal_at_minimum, f"seed={seed} witness={witness!r}"
    assert replay_assignment(community, initiative, result)


RELAXED_SEEDS = tuple(0xC200 + index * 53 for index in range(64))
RELAXATION_GROUPS = tuple(sorted(REQUIREMENT_GROUPS))


@pytest.mark.parametrize(
    ("seed", "group"),
    tuple((seed, RELAXATION_GROUPS[index % len(RELAXATION_GROUPS)]) for index, seed in enumerate(RELAXED_SEEDS)),
    ids=lambda value: value if isinstance(value, str) else f"seed_{value:04X}",
)
def test_tiny_solver_relaxation_matches_independent_predicate_oracle(
    seed: int,
    group: str,
) -> None:
    community, initiative = _tiny_case(seed)
    expected = _tiny_oracle(community, initiative, {group})
    result = solve_initiative(
        community,
        initiative,
        relax_groups={group},
        time_limit_seconds=2.0,
        random_seed=seed,
        num_search_workers=1,
    )
    if not expected:
        assert result.status is SolverStatus.INFEASIBLE, f"seed={seed} group={group}"
        return
    assert result.status is SolverStatus.OPTIMAL, f"seed={seed} group={group}"
    minimum = min(item[3] for item in expected)
    assert result.objective_value == minimum
    assert _result_witness(result) in {
        (item[0], item[1], item[2]) for item in expected if item[3] == minimum
    }
    assert validate_analysis_witness(
        community,
        initiative,
        result,
        relaxed_groups={group},
    )


@pytest.mark.parametrize("seed", ORACLE_SEEDS[:32], ids=lambda seed: f"seed_{seed:04X}")
def test_solver_repeat_and_entity_order_are_metamorphic(seed: int) -> None:
    community, initiative = _tiny_case(seed)
    first = solve_initiative(community, initiative, random_seed=seed)
    second = solve_initiative(community, initiative, random_seed=seed)
    assert first.status is second.status
    assert first.objective_value == second.objective_value
    assert first.assignments == second.assignments
    assert first.assembly_trace == second.assembly_trace

    reordered_community = community.model_copy(deep=True)
    reordered_community.organisations.reverse()
    reordered_community.people.reverse()
    reordered_community.spaces.reverse()
    reordered_community.resources.reverse()
    reordered = solve_initiative(reordered_community, initiative, random_seed=seed)
    assert reordered.status is first.status
    assert reordered.objective_value == first.objective_value
    if first.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        assert _result_witness(reordered) in {
            item[:3] for item in _tiny_oracle(reordered_community, initiative)
            if item[3] == reordered.objective_value
        }


def test_single_fact_witness_tampering_is_rejected() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)
    assert baseline.status is SolverStatus.OPTIMAL

    def mutate(result, kind: str) -> None:
        role = result.assembly_trace[0]
        venue = next(item for item in result.assembly_trace if item.requirement_kind == "venue")
        resource = next(item for item in result.assembly_trace if item.requirement_kind == "resource")
        time = next(item for item in result.assembly_trace if item.requirement_kind == "time")
        if kind == "role_label":
            role.facts["label"] = "FORGED"
        elif kind == "role_capabilities":
            role.facts["required_capabilities"] = []
        elif kind == "role_compact_capability":
            role.facts["capability"] = "forged"
        elif kind == "venue_capacity":
            venue.facts["capacity"] = int(venue.facts["capacity"]) + 1
        elif kind == "venue_features":
            venue.facts["features"] = []
        elif kind == "resource_quantity":
            resource.facts["quantity_available"] = int(resource.facts["quantity_available"]) + 1
        elif kind == "resource_shareable":
            resource.facts["shareable"] = not resource.facts["shareable"]
        elif kind == "time_slots":
            time.facts["occupied_slots"] = ["SAT_12", "SAT_13"]
        elif kind == "time_start":
            time.selected_ids = ["SAT_10"]
            time.facts["start_slot"] = "SAT_10"
        elif kind == "assignment_person":
            result.assignments[0].person_id = "MIA"
        elif kind == "assignment_role":
            result.assignments[0].role_instance_id = "FORGED_ROLE"
        elif kind == "objective":
            result.objective_value = int(result.objective_value or 0) + 2
        else:  # pragma: no cover - parameter list is exhaustive.
            raise AssertionError(kind)

    mutations = (
        "role_label",
        "role_capabilities",
        "role_compact_capability",
        "venue_capacity",
        "venue_features",
        "resource_quantity",
        "resource_shareable",
        "time_slots",
        "time_start",
        "assignment_person",
        "assignment_role",
        "objective",
    )
    for mutation in mutations:
        tampered = baseline.model_copy(deep=True)
        mutate(tampered, mutation)
        assert not validate_analysis_witness(fixture.community, initiative, tampered), mutation


def test_replay_accepts_public_assignment_shapes_and_rejects_missing_receipts() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    result = solve_initiative(fixture.community, initiative)
    venue = next(item for item in result.assembly_trace if item.requirement_kind == "venue")
    start = next(item for item in result.assembly_trace if item.requirement_kind == "time")
    mapping = {item.role_instance_id: item.person_id for item in result.assignments}
    sequence = [item.model_dump(mode="json") for item in result.assignments]
    assert replay_assignment(
        fixture.community,
        initiative,
        mapping,
        venue_id=venue.selected_ids[0],
        start_slot=start.selected_ids[0],
    )
    assert replay_assignment(
        fixture.community,
        initiative,
        sequence,
        venue_id=venue.selected_ids[0],
        start_slot=start.selected_ids[0],
    )
    assert not replay_assignment(fixture.community, initiative, mapping)
    assert not replay_assignment(
        fixture.community,
        initiative,
        {**mapping, "DIGITAL_HELPER": "MIA"},
        venue_id=venue.selected_ids[0],
        start_slot=start.selected_ids[0],
    )


def test_compiler_counts_and_relaxation_aliases_are_truthful() -> None:
    for seed in ORACLE_SEEDS[:24]:
        community, initiative = _tiny_case(seed)
        compiled = compile_initiative(community, initiative)
        expected_candidates = sum(
            1
            for role in initiative.roles
            for person in community.people
            if role.required_capabilities <= person.capabilities
            and role.required_languages <= person.languages
        )
        assert compiled.assignment_variable_count == expected_candidates
        assert compiled.venue_variable_count == len(community.spaces)
        assert compiled.start_variable_count == len(initiative.candidate_start_slots)
        assert compiled.decision_variables == len(compiled.model.Proto().variables)
        assert compiled.hard_constraints == len(compiled.model.Proto().constraints)
    assert normalise_relax_groups(ROLE_CAPABILITY) == frozenset({ROLE_CAPABILITY})
    assert normalise_relax_groups({LANGUAGE, AVAILABILITY}) == frozenset(
        {LANGUAGE, AVAILABILITY}
    )
    with pytest.raises(ValueError, match="unknown requirement"):
        normalise_relax_groups({"not_a_requirement"})
    with pytest.raises(ValueError, match="disagree"):
        compile_initiative(
            fresh_demo_fixture().community,
            next(item for item in fresh_demo_fixture().initiatives if item.id == "BASIC_WORKSHOP"),
            relax_groups={ROLE_CAPABILITY},
            relaxed_groups={LANGUAGE},
        )


def test_all_fixture_action_paths_are_pure_and_order_independent_when_executable() -> None:
    fixture = fresh_demo_fixture()
    actions = {action.id: action for action in fixture.actions}
    before = fixture.community.model_dump(mode="json")
    paths = ordered_action_paths(tuple(reversed(fixture.actions)), max_depth=2)
    assert [tuple(action.id for action in path) for path in paths] == [
        tuple(action.id for action in path)
        for path in ordered_action_paths(fixture.actions, max_depth=2)
    ]

    valid_paths = []
    for path in paths:
        try:
            successor, diff = apply_action_ids(fixture.community, actions, [item.id for item in path])
        except (ActionAlreadyApplied, ValueError):
            continue
        valid_paths.append(path)
        assert successor.state_id == state_id_for(successor)
        assert diff.model_dump(mode="json") == apply_action_ids(
            fixture.community,
            actions,
            [item.id for item in path],
        )[1].model_dump(mode="json")
        assert fixture.community.model_dump(mode="json") == before

    assert valid_paths
    first, first_diff = apply_action_ids(
        fixture.community,
        actions,
        ["RECRUIT_HELPER_A", "BORROW_TWO_LAPTOPS"],
    )
    second, second_diff = apply_action_ids(
        fixture.community,
        actions,
        ["BORROW_TWO_LAPTOPS", "RECRUIT_HELPER_A"],
    )
    assert canonical_state_hash(first) == canonical_state_hash(second)
    assert first.state_id == second.state_id
    assert first_diff == second_diff
    with pytest.raises(ValueError, match="unknown action"):
        apply_action_ids(fixture.community, actions, ["UNKNOWN_ACTION"])


def test_planner_and_unlock_match_an_independent_depth_two_path_oracle() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")
    actions = tuple(fixture.actions)
    expected: list[tuple[tuple[int, int, tuple[str, ...]], tuple[str, ...]]] = []
    for path in ordered_action_paths(actions, max_depth=2):
        current = fixture.community
        try:
            for action in path:
                current, _ = apply_action(current, action)
        except ValueError:
            continue
        status = solve_initiative(current, initiative).status
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            ids = tuple(action.id for action in path)
            expected.append(((sum(action.cost for action in path), len(path), ids), ids))
    assert expected
    expected_ids = min(expected, key=lambda item: item[0])[1]

    planned = plan_catalyst(
        fixture.community,
        initiative,
        actions,
        solve_initiative,
        max_depth=2,
        max_expanded_states=20,
    )
    unlocked = find_minimum_unlock(
        fixture.community,
        initiative,
        actions,
        solve_initiative,
    )
    assert tuple(planned.path) == tuple(unlocked.interventions) == expected_ids
    assert planned.total_cost == unlocked.total_cost == sum(
        action.cost for action in actions if action.id in expected_ids
    )
    assert planned.target_status_before is SolverStatus.INFEASIBLE
    assert planned.target_status_after in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert unlocked.candidate_paths_evaluated == len(ordered_action_paths(actions, max_depth=2))


def test_project_creation_is_pure_and_its_operational_fields_follow_the_witness() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")
    request = CreateProjectRequest(
        base_community=fixture.community.model_copy(deep=True),
        initiative_id=initiative.id,
        catalyst_path=["TRAIN_DIGITAL_HELPERS"],
        title="Saturday digital help clinic",
        short_description="A solver-verified clinic assembled from local capacity and training.",
        objective="Deliver accessible digital help with every operational dependency verified.",
    )
    base_before = fixture.community.model_dump(mode="json")
    actions_before = [item.model_dump(mode="json") for item in fixture.actions]
    initiative_before = initiative.model_dump(mode="json")
    response = create_project_from_plan(
        request,
        initiative,
        fixture.actions,
        fixture.community,
    )
    assert fixture.community.model_dump(mode="json") == base_before
    assert [item.model_dump(mode="json") for item in fixture.actions] == actions_before
    assert initiative.model_dump(mode="json") == initiative_before
    assignment_by_role = {
        item.role_instance_id: item.person_id for item in response.verification.assignments
    }
    project_by_role = {
        item.role_id: item.person_id for item in response.project.operational_assignments
    }
    assert project_by_role == assignment_by_role
    assert response.project.verified_state_id != response.project.base_state_id
    assert response.project.readiness.status.value == "READY"
    assert response.project.created_at == response.project.updated_at


def test_counterfactual_receipts_are_repeatable_and_source_order_metamorphic() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)
    catalogue = resilience.generate_canonical_perturbations(
        fixture.community,
        initiative,
        baseline,
    )
    reordered = fixture.community.model_copy(deep=True)
    reordered.people.reverse()
    reordered.spaces.reverse()
    reordered.resources.reverse()
    assert canonical_state_hash(reordered) == canonical_state_hash(fixture.community)
    for perturbation in catalogue:
        source_before = fixture.community.model_dump(mode="json")
        initiative_before = initiative.model_dump(mode="json")
        first = resilience.apply_canonical_perturbation(fixture.community, initiative, perturbation)
        second = resilience.apply_canonical_perturbation(fixture.community, initiative, perturbation)
        reordered_env = resilience.apply_canonical_perturbation(reordered, initiative, perturbation)
        resilience.validate_counterfactual_scenario(
            fixture.community,
            initiative,
            perturbation,
            first,
        )
        assert first.scenario_state_id == second.scenario_state_id == reordered_env.scenario_state_id
        assert first.scenario_content_hash == second.scenario_content_hash == reordered_env.scenario_content_hash
        assert first.state.model_dump(mode="json") == second.state.model_dump(mode="json")
        assert fixture.community.model_dump(mode="json") == source_before
        assert initiative.model_dump(mode="json") == initiative_before


def _frontier_fixture() -> tuple[CommunityState, list[InitiativeBlueprint], list[CatalystAction]]:
    community = CommunityState(
        state_id="S0",
        organisations=[OrganisationBlock(id="ORG", name="Org")],
        people=[
            PersonBlock(
                id="P0",
                name="Base",
                organisation_id="ORG",
                capabilities={"cap_a"},
                available_slots={TimeSlot.SAT_10},
                max_contribution_slots=1,
            ),
            PersonBlock(
                id="P1",
                name="Learner",
                organisation_id="ORG",
                willing_to_learn={"cap_b", "cap_c"},
                available_slots={TimeSlot.SAT_10},
                max_contribution_slots=1,
            ),
        ],
        spaces=[
            SpaceBlock(
                id="V0",
                name="Room",
                organisation_id="ORG",
                available_slots={TimeSlot.SAT_10},
                capacity=10,
                features={"wifi"},
            )
        ],
        resources=[],
    )

    def initiative(identifier: str, capability: str) -> InitiativeBlueprint:
        return InitiativeBlueprint(
            id=identifier,
            name=identifier,
            roles=[
                RoleRequirement(
                    id=f"{identifier}_ROLE",
                    label="Role",
                    required_capabilities={capability},
                )
            ],
            venue=VenueRequirement(minimum_capacity=1, required_features={"wifi"}),
            candidate_start_slots=[TimeSlot.SAT_10],
            duration_slots=1,
        )

    actions = [
        CatalystAction(
            id="A_ADD_B",
            name="Add B",
            cost=2,
            effects=[AddCapabilityEffect(type="add_capability", person_id="P1", capability_id="cap_b")],
        ),
        CatalystAction(
            id="B_ADD_C",
            name="Add C",
            cost=1,
            effects=[AddCapabilityEffect(type="add_capability", person_id="P1", capability_id="cap_c")],
        ),
        CatalystAction(
            id="C_ADD_BC",
            name="Add B and C",
            cost=5,
            effects=[
                AddCapabilityEffect(type="add_capability", person_id="P1", capability_id="cap_b"),
                AddCapabilityEffect(type="add_capability", person_id="P1", capability_id="cap_c"),
            ],
        ),
        CatalystAction(
            id="D_DEPENDENT",
            name="Dependent action",
            cost=0,
            preconditions={
                "person_capabilities": [
                    {"person_id": "P1", "capability_id": "cap_b"}
                ]
            },
            effects=[AddCapabilityEffect(type="add_capability", person_id="P1", capability_id="cap_d")],
        ),
    ]
    return community, [initiative("I_B", "cap_b"), initiative("I_C", "cap_c"), initiative("I_A", "cap_a")], actions


def test_frontier_matches_independent_status_sets_and_action_order_metamorphism() -> None:
    community, initiatives, actions = _frontier_fixture()
    request = CapabilityFrontierRequest(base_community=community.model_copy(deep=True))
    response = evaluate_capability_frontier(
        request,
        initiatives,
        community,
        list(reversed(actions)),
    )
    baseline = {
        initiative.id: solve_initiative(community, initiative).status
        for initiative in initiatives
    }
    assert response.baseline_statuses == baseline
    assert response.baseline_buildable_ids == ["I_A"]
    assert response.baseline_blocked_ids == ["I_B", "I_C"]
    by_id = {item.id: item for item in actions}
    for item in response.action_results:
        action = by_id[item.action_id]
        if item.action_id == "D_DEPENDENT":
            assert item.applicable is False
            continue
        successor, expected_diff = apply_action(community, action)
        expected_statuses = {
            initiative.id: solve_initiative(successor, initiative).status
            for initiative in initiatives
        }
        assert item.applicable is True
        assert item.statuses_after == expected_statuses
        assert item.produced_diff == expected_diff
        assert item.newly_feasible_initiatives == sorted(
            initiative_id
            for initiative_id, status in expected_statuses.items()
            if baseline[initiative_id] is SolverStatus.INFEASIBLE
            and status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        )
    assert response.highest_leverage_action_id == "C_ADD_BC"
    assert response.pareto_action_ids == ["C_ADD_BC", "B_ADD_C"]

    reordered = evaluate_capability_frontier(
        CapabilityFrontierRequest(base_community=community.model_copy(deep=True)),
        list(reversed(initiatives)),
        community,
        actions,
    )
    assert {
        item.action_id: item.model_dump(mode="json")
        for item in reordered.action_results
    } == {
        item.action_id: item.model_dump(mode="json")
        for item in response.action_results
    }
    assert reordered.baseline_statuses == response.baseline_statuses
    assert reordered.baseline_buildable_ids == response.baseline_buildable_ids
    assert reordered.baseline_blocked_ids == response.baseline_blocked_ids
    assert reordered.highest_leverage_action_id == response.highest_leverage_action_id
    assert reordered.pareto_action_ids == response.pareto_action_ids


def _recompiler_fixture(seed: int) -> tuple[CommunityState, InitiativeBlueprint]:
    """Tiny all-capability domain used by the independent lexicographic oracle."""

    people = [
        PersonBlock(
            id=f"P{index}",
            name=f"Person {index}",
            organisation_id="ORG",
            capabilities={"cap_a"},
            available_slots={TimeSlot.SAT_10},
            max_contribution_slots=1,
        )
        for index in range(3 + seed % 2)
    ]
    roles = [
        RoleRequirement(
            id=f"R{index}",
            label=f"Role {index}",
            required_capabilities={"cap_a"},
            allow_shared_person=False,
        )
        for index in range(1 + seed % 2)
    ]
    return (
        CommunityState(
            state_id=f"S{seed:08X}",
            organisations=[OrganisationBlock(id="ORG", name="Org")],
            people=people,
            spaces=[
                SpaceBlock(
                    id="V0",
                    name="Room",
                    organisation_id="ORG",
                    available_slots={TimeSlot.SAT_10},
                    capacity=4,
                    features=set(),
                )
            ],
            resources=[],
        ),
        InitiativeBlueprint(
            id=f"I{seed:08X}",
            name="Recovery initiative",
            roles=roles,
            venue=VenueRequirement(minimum_capacity=1),
            candidate_start_slots=[TimeSlot.SAT_10],
            duration_slots=1,
        ),
    )


@pytest.mark.parametrize("seed", tuple(0xD300 + index for index in range(12)), ids=lambda seed: f"seed_{seed:04X}")
def test_recompiler_matches_independent_min_change_then_burden_oracle(seed: int) -> None:
    community, initiative = _recompiler_fixture(seed)
    baseline = solve_initiative(community, initiative)
    assert baseline.status is SolverStatus.OPTIMAL
    perturbations = resilience.generate_canonical_perturbations(community, initiative, baseline)
    target = next(
        item
        for item in perturbations
        if item.type.value == "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
    )
    scenario = resilience.apply_canonical_perturbation(community, initiative, target).state
    scenario_witnesses = _tiny_oracle(scenario, initiative)
    assert scenario_witnesses, f"seed={seed} target={target.target_id}"
    baseline_pairs = tuple(
        (item.role_instance_id, item.person_id) for item in baseline.assignments
    )
    expected_lexicographic = min(
        (
            sum(left != right for left, right in zip(item[0], baseline_pairs, strict=True)),
            item[3],
        )
        for item in scenario_witnesses
    )
    request = RecompileRequest(
        base_community=community.model_copy(deep=True),
        initiative_id=initiative.id,
        catalyst_path=[],
        perturbation_id=target.id,
    )
    base_before = community.model_dump(mode="json")
    response = recompile_minimum_disruption(
        request,
        initiative,
        community,
        [],
    )
    assert response.status is SolverStatus.OPTIMAL
    assert response.minimum_assignment_changes == expected_lexicographic[0]
    assert response.new_result is not None
    assert response.new_result.objective_value == expected_lexicographic[1]
    final_pairs = tuple(
        (item.role_instance_id, item.person_id)
        for item in response.new_result.assignments
    )
    assert any(
        item[0] == final_pairs
        and item[3] == expected_lexicographic[1]
        and sum(left != right for left, right in zip(item[0], baseline_pairs, strict=True))
        == expected_lexicographic[0]
        for item in scenario_witnesses
    )
    assert community.model_dump(mode="json") == base_before


def test_unknown_solver_results_never_emit_partial_witnesses() -> None:
    fixture = fresh_demo_fixture()
    seen_unknown = False
    for initiative in fixture.initiatives:
        result = solve_initiative(
            fixture.community,
            initiative,
            time_limit_seconds=0,
            random_seed=0,
        )
        assert result.status in (SolverStatus.UNKNOWN, SolverStatus.INFEASIBLE)
        seen_unknown |= result.status is SolverStatus.UNKNOWN
        assert result.objective_value is None
        assert result.assignments == []
        assert result.assembly_trace == []
    assert seen_unknown


def test_time_limit_alias_and_model_request_boundaries_fail_closed() -> None:
    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    same = solve_initiative(
        fixture.community,
        initiative,
        time_limit_seconds=0,
        max_time_seconds=0,
    )
    assert same.status is SolverStatus.UNKNOWN
    with pytest.raises(ValueError, match="disagree"):
        solve_initiative(
            fixture.community,
            initiative,
            time_limit_seconds=1,
            max_time_seconds=0,
        )
    with pytest.raises(ValueError, match="must be non-negative"):
        solve_initiative(fixture.community, initiative, time_limit_seconds=-1)
    with pytest.raises(ValueError, match="positive"):
        solve_initiative(fixture.community, initiative, num_search_workers=0)
    with pytest.raises(ValidationError):
        InitiativeBlueprint.model_validate(
            {
                **initiative.model_dump(mode="json"),
                "unknown_field": True,
            }
        )
    with pytest.raises(ValidationError):
        RecompileRequest(
            base_community=fixture.community,
            initiative_id=initiative.id,
            catalyst_path=["A", "A"],
            perturbation_id="P",
        )
