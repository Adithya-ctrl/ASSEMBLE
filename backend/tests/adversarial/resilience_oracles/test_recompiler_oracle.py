from __future__ import annotations

from copy import deepcopy

import pytest

from app import recompiler
from app.api_models import (
    PersonUnavailablePerturbation,
    PerturbationType,
    RecompileRequest,
    ResourceAvailabilityPerturbation,
    SolverStatus,
    VenueUnavailablePerturbation,
)
from app.errors import AnalyserContractError
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

from .oracle_support import (
    apply_perturbation_locally,
    assignment_tuple,
    canonical_content,
    content_hash,
    legal_assemblies,
    perturbation_receipt_id,
    recompile_oracle,
)


def _tiny_recompile_world() -> tuple[CommunityState, InitiativeBlueprint]:
    """A tiny world with a unique burden-optimal baseline and replacement."""

    source = CommunityState(
        state_id="S0",
        organisations=[OrganisationBlock(id="ORG", name="Tiny organisation")],
        people=[
            PersonBlock(
                id="BASE",
                name="Baseline all-rounder",
                organisation_id="ORG",
                capabilities={"skill", "fac"},
                languages={"en"},
                available_slots={TimeSlot.SAT_11, TimeSlot.SAT_12},
                max_contribution_slots=2,
            ),
            PersonBlock(
                id="ALT",
                name="Replacement specialist",
                organisation_id="ORG",
                capabilities={"skill"},
                languages={"en"},
                available_slots={TimeSlot.SAT_11, TimeSlot.SAT_12},
                max_contribution_slots=2,
            ),
            PersonBlock(
                id="FAC",
                name="Fallback facilitator",
                organisation_id="ORG",
                capabilities={"fac"},
                languages={"en"},
                available_slots={TimeSlot.SAT_11, TimeSlot.SAT_12},
                max_contribution_slots=2,
            ),
        ],
        spaces=[
            SpaceBlock(
                id="ROOM",
                name="Tiny room",
                organisation_id="ORG",
                available_slots={TimeSlot.SAT_11, TimeSlot.SAT_12},
                capacity=4,
                features={"wifi"},
            )
        ],
        resources=[
            ResourceBlock(
                id="KIT",
                name="Tiny kit",
                organisation_id="ORG",
                quantity=1,
                available_slots={TimeSlot.SAT_11, TimeSlot.SAT_12},
                shareable=True,
            )
        ],
    )
    initiative = InitiativeBlueprint(
        id="TINY_RECOMPILE",
        name="Tiny recompile",
        roles=[
            RoleRequirement(
                id="HELPER",
                label="Skill helper",
                required_capabilities={"skill"},
            ),
            RoleRequirement(
                id="FACILITATOR",
                label="Facilitator",
                required_capabilities={"fac"},
                # This makes BASE/BASE the unique lower-burden baseline,
                # while the replacement must use ALT/FAC after BASE is lost.
                allow_shared_person=True,
            ),
        ],
        venue=VenueRequirement(
            minimum_capacity=4,
            required_features={"wifi"},
        ),
        resources=[ResourceRequirement(resource_id="KIT", quantity=1)],
        candidate_start_slots=[TimeSlot.SAT_11],
        duration_slots=2,
    )
    return source, initiative


def _person_spec(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    person_id: str = "BASE",
) -> PersonUnavailablePerturbation:
    person = next(item for item in source.people if item.id == person_id)
    source_digest = content_hash(source)
    return PersonUnavailablePerturbation(
        id=(
            f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_digest.upper()}_"
            f"{PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE.value}_{person_id}"
        ),
        type=PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE,
        initiative_id=initiative.id,
        target_id=person_id,
        label=f"{person.name} becomes unavailable",
        source_content_hash=source_digest,
        before_available_slots=sorted(person.available_slots, key=lambda slot: slot.value),
        after_available_slots=[],
    )


def _venue_spec(
    source: CommunityState,
    initiative: InitiativeBlueprint,
) -> VenueUnavailablePerturbation:
    venue = source.spaces[0]
    source_digest = content_hash(source)
    return VenueUnavailablePerturbation(
        id=(
            f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_digest.upper()}_"
            f"{PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE.value}_{venue.id}"
        ),
        type=PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE,
        initiative_id=initiative.id,
        target_id=venue.id,
        label=f"{venue.name} becomes unavailable",
        source_content_hash=source_digest,
        before_available_slots=sorted(venue.available_slots, key=lambda slot: slot.value),
        after_available_slots=[],
    )


def _resource_spec(
    source: CommunityState,
    initiative: InitiativeBlueprint,
) -> ResourceAvailabilityPerturbation:
    resource = source.resources[0]
    requirement = initiative.resources[0]
    source_digest = content_hash(source)
    return ResourceAvailabilityPerturbation(
        id=(
            f"ASSEMBLE_STRESS_PERTURBATION_V1_{source_digest.upper()}_"
            f"{PerturbationType.REDUCE_AVAILABLE_RESOURCE.value}_{resource.id}"
        ),
        type=PerturbationType.REDUCE_AVAILABLE_RESOURCE,
        initiative_id=initiative.id,
        target_id=resource.id,
        label=f"{resource.name} availability reduced",
        source_content_hash=source_digest,
        requirement_id=requirement.resource_id,
        required_quantity=requirement.quantity,
        before_quantity=resource.quantity,
        after_quantity=requirement.quantity - 1,
    )


def _request(source: CommunityState, initiative: InitiativeBlueprint, spec) -> RecompileRequest:
    return RecompileRequest(
        base_community=source.model_copy(deep=True),
        initiative_id=initiative.id,
        catalyst_path=[],
        perturbation_id=spec.id,
    )


def _run(source, initiative, spec):
    return recompiler.recompile_minimum_disruption(
        _request(source, initiative, spec),
        initiative,
        source,
        [],
        random_seed=0,
    )


def _semantic_response(response):
    result = response.new_result
    return {
        "initiative_id": response.initiative_id,
        "source_state_id": response.source_state_id,
        "perturbation_id": response.perturbation_id,
        "scenario_state_id": response.scenario_state_id,
        "perturbation": response.perturbation.model_dump(mode="json"),
        "status": response.status,
        "minimum_assignment_changes": response.minimum_assignment_changes,
        "preserved_assignments": response.preserved_assignments,
        "changed_assignments": response.changed_assignments,
        "role_diffs": [item.model_dump(mode="json") for item in response.role_diffs],
        "stage1_status": response.stage1_status,
        "stage2_status": response.stage2_status,
        "minimum_proven": response.minimum_proven,
        "secondary_burden_optimal": response.secondary_burden_optimal,
        "new_assignment": assignment_tuple(result) if result is not None else None,
        "new_objective": result.objective_value if result is not None else None,
    }


def test_two_stage_result_matches_independent_min_change_then_burden_oracle() -> None:
    """H1-H2/H7-H8: both objective stages and exact role identities are checked."""

    source, initiative = _tiny_recompile_world()
    baseline_assemblies = legal_assemblies(source, initiative)
    assert len(baseline_assemblies) == 4
    baseline = min(baseline_assemblies, key=lambda item: item[3])
    baseline_assignment = dict(baseline[0])
    assert baseline_assignment == {"HELPER": "BASE", "FACILITATOR": "BASE"}
    assert baseline[3] == 14

    spec = _person_spec(source, initiative)
    scenario = apply_perturbation_locally(source, spec)
    expected = recompile_oracle(source, initiative, scenario, baseline_assignment)
    assert expected is not None
    assert expected["minimum_changes"] == 2
    assert expected["burden"] == 24
    assert expected["assignment"] == (("HELPER", "ALT"), ("FACILITATOR", "FAC"))

    source_before = deepcopy(source.model_dump(mode="json"))
    initiative_before = deepcopy(initiative.model_dump(mode="json"))
    response = _run(source, initiative, spec)

    assert response.status is SolverStatus.OPTIMAL
    assert response.stage1_status is SolverStatus.OPTIMAL
    assert response.stage2_status is SolverStatus.OPTIMAL
    assert response.minimum_proven is True
    assert response.secondary_burden_optimal is True
    assert response.minimum_assignment_changes == expected["minimum_changes"]
    assert response.changed_assignments == expected["minimum_changes"]
    assert response.preserved_assignments == 0
    assert response.new_result is not None
    assert response.new_result.objective_value == expected["burden"]
    assert assignment_tuple(response.new_result) == expected["assignment"]
    assert [
        (item.role_id, item.before_person_id, item.after_person_id, item.changed)
        for item in response.role_diffs
    ] == [
        ("HELPER", "BASE", "ALT", True),
        ("FACILITATOR", "BASE", "FAC", True),
    ]
    assert response.source_state_id == source.state_id
    assert response.perturbation_id == spec.id
    assert response.perturbation.model_dump(mode="json") == spec.model_dump(mode="json")
    assert response.scenario_state_id == perturbation_receipt_id(
        source,
        initiative,
        spec,
        scenario,
    )
    assert canonical_content(scenario) == canonical_content(
        apply_perturbation_locally(source, response.perturbation)
    )
    assert source.model_dump(mode="json") == source_before
    assert initiative.model_dump(mode="json") == initiative_before


def test_recompile_semantics_are_deterministic_and_scenario_bound() -> None:
    source, initiative = _tiny_recompile_world()
    spec = _person_spec(source, initiative)
    first = _run(source, initiative, spec)
    second = _run(source, initiative, spec)
    assert _semantic_response(first) == _semantic_response(second)
    assert first.scenario_state_id.startswith("CF_STRESS_V1_")
    assert first.scenario_state_id != source.state_id
    assert first.source_state_id == "S0"
    assert first.perturbation.source_content_hash == content_hash(source)
    assert first.perturbation.initiative_id == initiative.id


def test_infeasible_stage_one_stops_without_minimum_or_replacement_witness() -> None:
    """H5: a venue/resource integrity loss cannot claim a change bound."""

    source, initiative = _tiny_recompile_world()
    spec = _venue_spec(source, initiative)
    scenario = apply_perturbation_locally(source, spec)
    assert legal_assemblies(scenario, initiative) == []

    response = _run(source, initiative, spec)
    assert response.status is SolverStatus.INFEASIBLE
    assert response.stage1_status is SolverStatus.INFEASIBLE
    assert response.stage2_status is None
    assert response.stage2_solver_stats is None
    assert response.minimum_proven is False
    assert response.minimum_assignment_changes is None
    assert response.new_result is None
    assert response.role_diffs == []
    assert response.preserved_assignments is None
    assert response.changed_assignments is None


def test_unknown_stage_one_withholds_minimum_and_never_enters_stage_two(monkeypatch) -> None:
    """H4: Stage 1 UNKNOWN is unresolved, not a zero-change or infeasible claim."""

    source, initiative = _tiny_recompile_world()
    spec = _person_spec(source, initiative)

    monkeypatch.setattr(
        recompiler,
        "solver_status_from_cp_sat",
        lambda status_code: SolverStatus.UNKNOWN,
    )
    monkeypatch.setattr(
        recompiler,
        "solve_compiled",
        lambda *args, **kwargs: pytest.fail("Stage 2 must not run after Stage 1 UNKNOWN"),
    )
    response = _run(source, initiative, spec)

    assert response.status is SolverStatus.UNKNOWN
    assert response.stage1_status is SolverStatus.UNKNOWN
    assert response.stage2_status is None
    assert response.stage2_solver_stats is None
    assert response.minimum_proven is False
    assert response.minimum_assignment_changes is None
    assert response.new_result is None
    assert response.role_diffs == []
    assert response.preserved_assignments is None
    assert response.changed_assignments is None


def test_feasible_but_nonoptimal_stage_two_returns_witness_without_optimality_claim(
    monkeypatch,
) -> None:
    """H6: a Stage 2 incumbent may be useful, but burden optimality stays false."""

    source, initiative = _tiny_recompile_world()
    spec = _person_spec(source, initiative)
    proven = _run(source, initiative, spec)
    assert proven.new_result is not None

    def feasible_stage_two(*args, **kwargs):
        del args, kwargs
        return proven.new_result.model_copy(update={"status": SolverStatus.FEASIBLE})

    monkeypatch.setattr(recompiler, "solve_compiled", feasible_stage_two)
    response = _run(source, initiative, spec)

    assert response.status is SolverStatus.FEASIBLE
    assert response.stage1_status is SolverStatus.OPTIMAL
    assert response.stage2_status is SolverStatus.FEASIBLE
    assert response.minimum_proven is True
    assert response.secondary_burden_optimal is False
    assert response.minimum_assignment_changes == 2
    assert response.changed_assignments == 2
    assert response.new_result is not None
    assert response.new_result.status is SolverStatus.FEASIBLE
    assert assignment_tuple(response.new_result) == (("HELPER", "ALT"), ("FACILITATOR", "FAC"))


def test_wrong_catalogue_target_is_rejected_before_any_stage_metrics() -> None:
    source, initiative = _tiny_recompile_world()
    person_spec = _person_spec(source, initiative)
    non_catalogue_spec = _person_spec(source, initiative, "ALT")
    request = _request(source, initiative, person_spec).model_copy(
        update={"perturbation_id": non_catalogue_spec.id}
    )
    with pytest.raises(recompiler.InvalidPerturbation, match="not in the canonical catalogue"):
        recompiler.recompile_minimum_disruption(
            request,
            initiative,
            source,
            [],
        )
