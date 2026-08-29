"""Independent Set-B solver assurance.

This module deliberately keeps the oracle small and transparent.  The only
product solver call is the system under test; the expected status, legal
witness set, objective, and optimum tie set are computed by the plain-Python
enumerator below.  In particular, this file does not import compiler internals,
CP-SAT variable maps, the production burden/replay validator, action
application, planner, or ranking helpers.

The generated domains stay within the gauntlet's tiny bounds:

* 1--5 people;
* 1--3 roles;
* 1--2 spaces;
* 0--2 resources; and
* 2--4 declared time slots.

The production contract does not declare an implementation-specific lexical
preference between equal-burden witnesses.  Therefore the independent tie
oracle computes the complete optimum tie set and requires CP-SAT to return a
member of that set; a separate 100-execution gate proves the configured
single-worker result is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import random
from types import SimpleNamespace
from typing import Iterable, Sequence

import pytest
from ortools.sat.python import cp_model

from app.api_models import (
    CapabilityFrontierRequest,
    InitiativeAnalysisResult,
    SolverStats,
    SolverStatus,
    StressCriticality,
    StressTestRequest,
)
from app.fixture import fresh_demo_fixture
from app.frontier import evaluate_capability_frontier
from app.models import (
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
from app.resilience import run_stress_test
from app.solver import analyse_initiatives, solve_initiative


# These are test-oracle declarations, intentionally not imported from the
# compiler.  The weights are the frozen public objective contract: ten per
# distinct person and two per role assignment.
DISTINCT_PERSON_WEIGHT = 10
ASSIGNMENT_WEIGHT = 2

SLOT_ORDER: tuple[TimeSlot, ...] = tuple(TimeSlot)
CAPABILITY_POOL: tuple[str, ...] = ("cap_a", "cap_b", "cap_c")
LANGUAGE_POOL: tuple[str, ...] = ("en", "ar")
FEATURE_POOL: tuple[str, ...] = ("feature_a", "feature_b", "feature_c")
DETERMINISTIC_SEED = 20260830
REPEAT_EXECUTIONS = 100


@dataclass(frozen=True)
class OracleWitness:
    """One complete legal witness produced by the independent enumeration."""

    assignments: tuple[tuple[str, str], ...]
    venue_id: str
    start_slot: TimeSlot
    objective: int

    @property
    def tie_key(self) -> tuple[tuple[tuple[str, str], ...], str, str]:
        """A stable representation for comparing equal-objective witnesses."""

        return self.assignments, self.venue_id, self.start_slot.value


def _random_subset(
    rng: random.Random,
    values: Sequence[str],
    *,
    allow_empty: bool = True,
) -> set[str]:
    selected = {value for value in values if rng.randrange(2)}
    if not selected and not allow_empty:
        selected.add(values[rng.randrange(len(values))])
    return selected


def _random_slots(
    rng: random.Random,
    slots: Sequence[TimeSlot],
    *,
    allow_empty: bool = True,
) -> set[TimeSlot]:
    selected = {slot for slot in slots if rng.randrange(2)}
    if not selected and not allow_empty:
        selected.add(slots[rng.randrange(len(slots))])
    return selected


def _tiny_case(
    seed: int,
    *,
    people_count: int | None = None,
    role_count: int | None = None,
    space_count: int | None = None,
    resource_count: int | None = None,
    slot_count: int | None = None,
) -> tuple[CommunityState, InitiativeBlueprint]:
    """Generate one valid bounded instance from ``seed``.

    The generator uses only domain models and ``random.Random``.  It never
    asks the product compiler or solver to construct an expected case.
    """

    rng = random.Random(seed)
    people_count = people_count if people_count is not None else 1 + seed % 5
    role_count = role_count if role_count is not None else 1 + (seed // 5) % 3
    space_count = space_count if space_count is not None else 1 + (seed // 15) % 2
    resource_count = (
        resource_count if resource_count is not None else (seed // 30) % 3
    )
    slot_count = slot_count if slot_count is not None else 2 + (seed // 90) % 3
    slots = SLOT_ORDER[:slot_count]
    # Half of the corpus deliberately has a guaranteed feasible corridor so
    # the oracle exercises witness/objective/tie handling as well as blocked
    # status.  The other half keeps fully seeded adversarial sparsity.  Both
    # branches remain within the same published size bounds.
    guaranteed_feasible = seed % 2 == 0

    people: list[PersonBlock] = []
    for index in range(people_count):
        available = set(slots) if guaranteed_feasible else _random_slots(
            rng,
            slots,
            allow_empty=False,
        )
        people.append(
            PersonBlock(
                id=f"P{index}",
                name=f"Person {index}",
                organisation_id="ORG",
                capabilities=(
                    set(CAPABILITY_POOL)
                    if guaranteed_feasible
                    else _random_subset(rng, CAPABILITY_POOL)
                ),
                languages=(
                    set(LANGUAGE_POOL)
                    if guaranteed_feasible
                    else _random_subset(rng, LANGUAGE_POOL)
                ),
                willing_to_learn=_random_subset(rng, CAPABILITY_POOL),
                available_slots=available,
                max_contribution_slots=(
                    len(available)
                    if guaranteed_feasible
                    else rng.randint(1, len(available))
                ),
            )
        )

    spaces: list[SpaceBlock] = []
    for index in range(space_count):
        spaces.append(
            SpaceBlock(
                id=f"V{index}",
                name=f"Venue {index}",
                organisation_id="ORG",
                available_slots=(
                    set(slots)
                    if guaranteed_feasible
                    else _random_slots(rng, slots)
                ),
                capacity=8 if guaranteed_feasible else rng.randint(0, 8),
                features=(
                    set(FEATURE_POOL)
                    if guaranteed_feasible
                    else _random_subset(rng, FEATURE_POOL)
                ),
            )
        )

    resources: list[ResourceBlock] = []
    for index in range(resource_count):
        resources.append(
            ResourceBlock(
                id=f"RES{index}",
                name=f"Resource {index}",
                organisation_id="ORG",
                quantity=5 if guaranteed_feasible else rng.randint(0, 5),
                available_slots=(
                    set(slots)
                    if guaranteed_feasible
                    else _random_slots(rng, slots)
                ),
                shareable=bool(rng.randrange(2)),
            )
        )

    duration = rng.randint(1, min(3, slot_count))
    valid_starts = [
        slot
        for slot in slots
        if SLOT_ORDER.index(slot) + duration <= slot_count
    ]
    candidate_starts = rng.sample(valid_starts, rng.randint(1, len(valid_starts)))

    roles = [
        RoleRequirement(
            id=f"R{index}",
            label=f"Role {index}",
            required_capabilities=_random_subset(rng, CAPABILITY_POOL),
            required_languages=_random_subset(rng, LANGUAGE_POOL),
            allow_shared_person=(
                True
                if guaranteed_feasible and people_count < role_count
                else bool(rng.randrange(2))
            ),
        )
        for index in range(role_count)
    ]

    requirements: list[ResourceRequirement] = []
    if resources:
        selected_resources = rng.sample(resources, rng.randint(0, len(resources)))
        requirements = [
            ResourceRequirement(
                resource_id=resource.id,
                quantity=rng.randint(1, 3) if guaranteed_feasible else rng.randint(1, 5),
            )
            for resource in selected_resources
        ]

    community = CommunityState(
        state_id=f"S{seed:08X}",
        organisations=[OrganisationBlock(id="ORG", name="Organisation")],
        people=people,
        spaces=spaces,
        resources=resources,
    )
    initiative = InitiativeBlueprint(
        id=f"I{seed:08X}",
        name=f"Initiative {seed}",
        roles=roles,
        venue=VenueRequirement(
            minimum_capacity=rng.randint(0, 8),
            required_features=_random_subset(rng, FEATURE_POOL),
        ),
        resources=requirements,
        candidate_start_slots=candidate_starts,
        duration_slots=duration,
    )
    return community, initiative


def _occupied(start: TimeSlot, duration: int) -> tuple[TimeSlot, ...]:
    """Compute contiguous occupied slots from the declared test slot order."""

    start_index = SLOT_ORDER.index(start)
    return SLOT_ORDER[start_index : start_index + duration]


def _is_subset(required: Iterable[object], available: Iterable[object]) -> bool:
    """Avoid relying on Pydantic/container implementation details in checks."""

    return set(required) <= set(available)


def _enumerate_legal_witnesses(
    community: CommunityState,
    initiative: InitiativeBlueprint,
) -> list[OracleWitness]:
    """Exhaustively enumerate assignments, venue choices, and starts.

    Every predicate is written directly from the domain contract: role
    capability/language eligibility, simultaneous-role sharing, person/venue/
    resource availability, contribution, venue facts, and resource quantity.
    The objective is evaluated locally from decoded assignment pairs.
    """

    people = {person.id: person for person in community.people}
    roles = tuple(initiative.roles)
    role_candidates: list[tuple[PersonBlock, ...]] = []
    for role in roles:
        candidates = tuple(
            sorted(
                (
                    person
                    for person in people.values()
                    if _is_subset(role.required_capabilities, person.capabilities)
                    and _is_subset(role.required_languages, person.languages)
                ),
                key=lambda person: person.id,
            )
        )
        role_candidates.append(candidates)

    if any(not candidates for candidates in role_candidates):
        return []

    spaces = tuple(sorted(community.spaces, key=lambda space: space.id))
    resources = {resource.id: resource for resource in community.resources}
    starts = tuple(sorted(initiative.candidate_start_slots, key=lambda slot: slot.value))
    witnesses: list[OracleWitness] = []

    for selected_people in product(*role_candidates):
        assigned_roles: dict[str, list[RoleRequirement]] = {}
        for role, person in zip(roles, selected_people, strict=True):
            assigned_roles.setdefault(person.id, []).append(role)

        # A person may fill a simultaneous pair only if either role permits
        # sharing.  This is checked on the selected mapping, independently of
        # the product's candidate-variable construction.
        if any(
            not (
                left.allow_shared_person
                or right.allow_shared_person
            )
            for person_roles in assigned_roles.values()
            for left_index, left in enumerate(person_roles)
            for right in person_roles[left_index + 1 :]
        ):
            continue

        assignment_pairs = tuple(
            (role.id, person.id)
            for role, person in zip(roles, selected_people, strict=True)
        )
        objective = (
            DISTINCT_PERSON_WEIGHT * len({person_id for _, person_id in assignment_pairs})
            + ASSIGNMENT_WEIGHT * len(assignment_pairs)
        )

        for start in starts:
            occupied = _occupied(start, initiative.duration_slots)

            if any(
                not _is_subset(occupied, people[person.id].available_slots)
                for person in selected_people
            ):
                continue

            contribution_ok = True
            for person_id, person_roles in assigned_roles.items():
                shareable_pair = any(
                    left.allow_shared_person or right.allow_shared_person
                    for left_index, left in enumerate(person_roles)
                    for right in person_roles[left_index + 1 :]
                )
                contribution = (
                    len(occupied)
                    if shareable_pair
                    else initiative.duration_slots * len(person_roles)
                )
                if contribution > people[person_id].max_contribution_slots:
                    contribution_ok = False
                    break
            if not contribution_ok:
                continue

            for venue in spaces:
                if venue.capacity < initiative.venue.minimum_capacity:
                    continue
                if not _is_subset(initiative.venue.required_features, venue.features):
                    continue
                if not _is_subset(occupied, venue.available_slots):
                    continue

                resource_ok = True
                for requirement in initiative.resources:
                    resource = resources.get(requirement.resource_id)
                    if resource is None:
                        resource_ok = False
                        break
                    if resource.quantity < requirement.quantity:
                        resource_ok = False
                        break
                    if not _is_subset(occupied, resource.available_slots):
                        resource_ok = False
                        break
                if resource_ok:
                    witnesses.append(
                        OracleWitness(
                            assignments=assignment_pairs,
                            venue_id=venue.id,
                            start_slot=start,
                            objective=objective,
                        )
                    )
    return witnesses


def _expected_status(witnesses: Sequence[OracleWitness]) -> str:
    """Return an oracle-owned status label, never the product status."""

    return "OPTIMAL" if witnesses else "INFEASIBLE"


def _result_witness(result: InitiativeAnalysisResult) -> OracleWitness:
    """Decode only public result fields; do not invoke the product validator."""

    assignments = tuple(
        (assignment.role_instance_id, assignment.person_id)
        for assignment in result.assignments
    )
    venue_entries = [
        entry for entry in result.assembly_trace if entry.requirement_kind == "venue"
    ]
    time_entries = [
        entry for entry in result.assembly_trace if entry.requirement_kind == "time"
    ]
    assert len(venue_entries) == 1
    assert len(time_entries) == 1
    assert len(venue_entries[0].selected_ids) == 1
    assert len(time_entries[0].selected_ids) == 1
    return OracleWitness(
        assignments=assignments,
        venue_id=venue_entries[0].selected_ids[0],
        start_slot=TimeSlot(time_entries[0].selected_ids[0]),
        objective=int(result.objective_value),
    )


def _assert_result_matches_oracle(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    result: InitiativeAnalysisResult,
    witnesses: Sequence[OracleWitness],
) -> None:
    """Check status, contract shape, objective, and the complete optimum tie set."""

    expected_status = _expected_status(witnesses)
    assert result.initiative_id == initiative.id
    assert result.status.value == expected_status
    # Re-validate the public payload through the frozen response model only;
    # no production witness/replay function participates in expected logic.
    assert InitiativeAnalysisResult.model_validate(result.model_dump(mode="json")) == result

    if expected_status == "INFEASIBLE":
        assert result.objective_value is None
        assert result.assignments == []
        assert result.assembly_trace == []
        return

    assert result.status is SolverStatus.OPTIMAL
    minimum = min(witness.objective for witness in witnesses)
    assert result.objective_value == minimum
    actual = _result_witness(result)
    optimum_ties = {
        witness.tie_key
        for witness in witnesses
        if witness.objective == minimum
    }
    assert actual.tie_key in optimum_ties
    assert actual.assignments == tuple(
        (assignment.role_instance_id, assignment.person_id)
        for assignment in result.assignments
    )


ORACLE_SEEDS: tuple[int, ...] = tuple(0xB100 + index * 41 for index in range(256))


@pytest.mark.parametrize("seed", ORACLE_SEEDS, ids=lambda seed: f"seed_{seed:04X}")
def test_256_seeded_instances_match_independent_exhaustive_oracle(seed: int) -> None:
    """Cover hundreds of deterministic bounded instances and both statuses."""

    community, initiative = _tiny_case(seed)
    expected = _enumerate_legal_witnesses(community, initiative)
    result = solve_initiative(
        community,
        initiative,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    _assert_result_matches_oracle(community, initiative, result, expected)


def _batch_initiatives(seed: int, count: int) -> tuple[CommunityState, list[InitiativeBlueprint]]:
    community, _ = _tiny_case(
        seed,
        people_count=5,
        role_count=3,
        space_count=2,
        resource_count=2,
        slot_count=4,
    )
    initiatives = [
        _tiny_case(
            seed + index * 17 + 1,
            people_count=5,
            role_count=1 + index % 3,
            space_count=2,
            resource_count=2,
            slot_count=4,
        )[1]
        for index in range(count)
    ]
    return community, initiatives


@pytest.mark.parametrize("count", (1, 2, 3, 4, 5), ids=lambda count: f"initiatives_{count}")
def test_analyse_initiatives_covers_each_declared_batch_count(count: int) -> None:
    """Exercise the product's multi-initiative API at every 1--5 count."""

    community, initiatives = _batch_initiatives(0xC400 + count * 13, count)
    expected = [
        _enumerate_legal_witnesses(community, initiative)
        for initiative in initiatives
    ]
    results = analyse_initiatives(
        community,
        initiatives,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    assert len(results) == count
    for initiative, result, oracle in zip(initiatives, results, expected, strict=True):
        _assert_result_matches_oracle(community, initiative, result, oracle)


def _tie_case() -> tuple[CommunityState, InitiativeBlueprint]:
    slots = set(SLOT_ORDER)
    community = CommunityState(
        state_id="S_TIE",
        organisations=[OrganisationBlock(id="ORG", name="Organisation")],
        people=[
            PersonBlock(
                id=f"P{index}",
                name=f"Person {index}",
                organisation_id="ORG",
                capabilities={"cap_a"},
                languages={"en"},
                available_slots=slots,
                max_contribution_slots=4,
            )
            for index in range(5)
        ],
        spaces=[
            SpaceBlock(
                id=f"V{index}",
                name=f"Venue {index}",
                organisation_id="ORG",
                available_slots=slots,
                capacity=10,
                features={"feature_a"},
            )
            for index in range(2)
        ],
        resources=[],
    )
    initiative = InitiativeBlueprint(
        id="I_TIE",
        name="Tie initiative",
        roles=[
            RoleRequirement(
                id=f"R{index}",
                label=f"Role {index}",
                required_capabilities={"cap_a"},
                required_languages={"en"},
            )
            for index in range(3)
        ],
        venue=VenueRequirement(minimum_capacity=1, required_features={"feature_a"}),
        candidate_start_slots=list(SLOT_ORDER),
        duration_slots=1,
    )
    return community, initiative


def test_repeat_determinism_has_100_independent_executions_and_tie_membership() -> None:
    """Prove status/objective/witness determinism over the required 100 runs."""

    community, initiative = _tie_case()
    expected = _enumerate_legal_witnesses(community, initiative)
    assert len(expected) > 1, "fixture must contain a genuine optimum tie"
    first: tuple[object, ...] | None = None
    for _ in range(REPEAT_EXECUTIONS):
        result = solve_initiative(
            community,
            initiative,
            time_limit_seconds=2.0,
            num_search_workers=1,
            random_seed=DETERMINISTIC_SEED,
        )
        _assert_result_matches_oracle(community, initiative, result, expected)
        current = (
            result.status,
            result.objective_value,
            tuple(result.assignments),
            tuple(result.assembly_trace),
        )
        if first is None:
            first = current
        else:
            assert current == first
    assert first is not None


@pytest.mark.parametrize(
    "seed",
    ORACLE_SEEDS[:32],
    ids=lambda seed: f"order_seed_{seed:04X}",
)
def test_declaration_order_permutations_preserve_semantic_and_tie_results(seed: int) -> None:
    """Reordering entity declarations must not alter the solved meaning."""

    community, initiative = _tiny_case(seed)
    expected = _enumerate_legal_witnesses(community, initiative)
    first = solve_initiative(
        community,
        initiative,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    reordered = community.model_copy(deep=True)
    reordered.people.reverse()
    reordered.spaces.reverse()
    reordered.resources.reverse()
    second = solve_initiative(
        reordered,
        initiative,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    assert first.status is second.status
    assert first.objective_value == second.objective_value
    assert first.assignments == second.assignments
    assert first.assembly_trace == second.assembly_trace
    _assert_result_matches_oracle(reordered, initiative, second, expected)


class _ModelInvalidSolver:
    """Minimal public solver seam that returns CP-SAT MODEL_INVALID."""

    def __init__(self) -> None:
        self.parameters = SimpleNamespace()
        self.solve_calls = 0

    def Solve(self, _model: object) -> int:
        self.solve_calls += 1
        return cp_model.MODEL_INVALID

    def NumBranches(self) -> int:
        return 0

    def NumConflicts(self) -> int:
        return 0

    def WallTime(self) -> float:
        return 0.0


def test_model_invalid_is_unknown_and_carries_no_witness() -> None:
    """MODEL_INVALID must fail closed to the public UNKNOWN contract."""

    community, initiative = _tiny_case(
        0xD500,
        people_count=5,
        role_count=3,
        space_count=2,
        resource_count=2,
        slot_count=4,
    )
    fake_solver = _ModelInvalidSolver()
    result = solve_initiative(
        community,
        initiative,
        solver=fake_solver,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    assert fake_solver.solve_calls == 1
    assert result.status is SolverStatus.UNKNOWN
    assert result.objective_value is None
    assert result.assignments == []
    assert result.assembly_trace == []
    assert InitiativeAnalysisResult.model_validate(result.model_dump(mode="json")) == result


def _unknown_result(initiative_id: str) -> InitiativeAnalysisResult:
    return InitiativeAnalysisResult(
        initiative_id=initiative_id,
        status=SolverStatus.UNKNOWN,
        solver_stats=SolverStats(branches=0, conflicts=0, wall_time_seconds=0.0),
    )


def test_unknown_stress_outcomes_are_non_decisive_and_excluded_from_ratio() -> None:
    """Stress must preserve UNKNOWN instead of classifying it as survival/failure."""

    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    baseline = solve_initiative(
        fixture.community,
        initiative,
        time_limit_seconds=2.0,
        num_search_workers=1,
        random_seed=DETERMINISTIC_SEED,
    )
    assert baseline.status is SolverStatus.OPTIMAL
    source_state_id = fixture.community.state_id

    def baseline_then_unknown(
        state: CommunityState,
        _initiative: InitiativeBlueprint,
        **_kwargs: object,
    ) -> InitiativeAnalysisResult:
        if state.state_id == source_state_id:
            return baseline
        return _unknown_result(initiative.id)

    response = run_stress_test(
        StressTestRequest(
            base_community=fixture.community.model_copy(deep=True),
            initiative_id=initiative.id,
            catalyst_path=[],
        ),
        initiative,
        fixture.community,
        fixture.actions,
        analyser=baseline_then_unknown,
    )
    assert response.catalogue_size == len(response.outcomes) > 0
    assert response.unknown_count == response.catalogue_size
    assert response.decisive_count == 0
    assert response.survived_count == 0
    assert response.failed_count == 0
    assert response.resilience_ratio is None
    for outcome in response.outcomes:
        assert outcome.status is SolverStatus.UNKNOWN
        assert outcome.survived is None
        assert outcome.criticality is StressCriticality.UNKNOWN
        assert outcome.objective_value is None
        assert outcome.assignment_changes is None
        assert outcome.after_venue_id is None
        assert outcome.after_start_slot is None


def test_unknown_frontier_coverage_cannot_claim_gain_loss_or_winner() -> None:
    """UNKNOWN baseline/after statuses stay unresolved in frontier analysis."""

    fixture = fresh_demo_fixture()
    initiatives = fixture.initiatives[:3]
    action = next(item for item in fixture.actions if item.id == "RECRUIT_HELPER_A")

    def always_unknown(
        _community: CommunityState,
        initiative: InitiativeBlueprint,
        **_kwargs: object,
    ) -> dict[str, str]:
        return {"initiative_id": initiative.id, "status": "UNKNOWN"}

    response = evaluate_capability_frontier(
        CapabilityFrontierRequest(
            base_community=fixture.community.model_copy(deep=True),
            catalyst_path=[],
        ),
        initiatives,
        fixture.community,
        [action],
        analyser=always_unknown,
    )
    assert response.baseline_unknown_ids == sorted(item.id for item in initiatives)
    assert response.baseline_buildable_ids == []
    assert response.baseline_blocked_ids == []
    candidate = response.action_results[0]
    assert candidate.applicable is True
    assert candidate.decisive_coverage_complete is False
    assert candidate.unknown_initiatives == sorted(item.id for item in initiatives)
    assert candidate.newly_feasible_initiatives == []
    assert candidate.lost_feasible_initiatives == []
    assert response.highest_leverage_action_id is None
    assert response.pareto_action_ids == []
    assert response.uncertainty_could_change_winner is True


def test_unknown_verification_never_allows_project_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A downstream UNKNOWN proof must fail closed before Project derivation."""

    fixture = fresh_demo_fixture()
    initiative = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    request = CreateProjectRequest(
        base_community=fixture.community.model_copy(deep=True),
        initiative_id=initiative.id,
        catalyst_path=[],
        title="Unknown proof project",
        short_description="A project request that must remain blocked without proof.",
        objective="Do not create an operational Project from unresolved solver evidence.",
    )

    monkeypatch.setattr(
        "app.projects.solve_initiative",
        lambda *_args, **_kwargs: _unknown_result(initiative.id),
    )
    with pytest.raises(ValueError, match="UNKNOWN"):
        create_project_from_plan(
            request,
            initiative,
            fixture.actions,
            fixture.community,
        )
