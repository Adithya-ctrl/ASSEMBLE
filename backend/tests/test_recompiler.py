from __future__ import annotations

from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import pytest

from app import resilience
from app.api_models import (
    InitiativeAnalysisResult,
    PersonUnavailablePerturbation,
    PerturbationType,
    RecompileRequest,
    RecompileResponse,
    ResourceAvailabilityPerturbation,
    SolverStatus,
    SolverStats,
    VenueUnavailablePerturbation,
)
from app.errors import AnalyserContractError
from app.fixture import fresh_demo_fixture
from app.interventions import apply_action, canonical_state_hash
from app.recompiler import (
    InvalidPerturbation,
    PerturbationCatalogueTooLarge,
    recompile_minimum_disruption,
)
from app.solver import replay_assignment, solve_initiative, validate_analysis_witness


def _initiative(fixture, initiative_id: str):
    return next(item for item in fixture.initiatives if item.id == initiative_id)


def _trained_source(fixture):
    action = next(item for item in fixture.actions if item.id == "TRAIN_DIGITAL_HELPERS")
    source, _ = apply_action(fixture.community, action)
    return source


def _person_spec(source, initiative, person_id: str):
    person = next(item for item in source.people if item.id == person_id)
    source_hash = canonical_state_hash(source)
    return PersonUnavailablePerturbation(
        id=resilience._perturbation_id(
            source_hash,
            PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE,
            person_id,
        ),
        type=PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE,
        initiative_id=initiative.id,
        target_id=person_id,
        label=f"{person.name} becomes unavailable",
        source_content_hash=source_hash,
        before_available_slots=sorted(person.available_slots, key=lambda slot: slot.value),
        after_available_slots=[],
    )


def _venue_spec(source, initiative):
    venue = source.spaces[0]
    source_hash = canonical_state_hash(source)
    return VenueUnavailablePerturbation(
        id=resilience._perturbation_id(
            source_hash,
            PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE,
            venue.id,
        ),
        type=PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE,
        initiative_id=initiative.id,
        target_id=venue.id,
        label=f"{venue.name} becomes unavailable",
        source_content_hash=source_hash,
        before_available_slots=sorted(venue.available_slots, key=lambda slot: slot.value),
        after_available_slots=[],
    )


def _resource_spec(source, initiative):
    requirement = initiative.resources[0]
    resource = next(item for item in source.resources if item.id == requirement.resource_id)
    source_hash = canonical_state_hash(source)
    return ResourceAvailabilityPerturbation(
        id=resilience._perturbation_id(
            source_hash,
            PerturbationType.REDUCE_AVAILABLE_RESOURCE,
            resource.id,
        ),
        type=PerturbationType.REDUCE_AVAILABLE_RESOURCE,
        initiative_id=initiative.id,
        target_id=resource.id,
        label=f"{resource.name} availability reduced",
        source_content_hash=source_hash,
        requirement_id=requirement.resource_id,
        required_quantity=requirement.quantity,
        before_quantity=resource.quantity,
        after_quantity=max(0, requirement.quantity - 1),
    )


def _request(fixture, initiative, source, perturbation):
    return RecompileRequest(
        base_community=fixture.community,
        initiative_id=initiative.id,
        catalyst_path=["TRAIN_DIGITAL_HELPERS"],
        perturbation_id=perturbation.id,
    )


def _resilience_stub(generator, applier=resilience.apply_canonical_perturbation):
    return SimpleNamespace(
        CounterfactualScenario=resilience.CounterfactualScenario,
        validate_counterfactual_scenario=resilience.validate_counterfactual_scenario,
        generate_canonical_perturbations=generator,
        apply_canonical_perturbation=applier,
    )


def _run_with_spec(monkeypatch, fixture, initiative, source, perturbation):
    stub = _resilience_stub(
        lambda source_state, initiative, baseline_result: [perturbation]
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: stub)
    return recompile_minimum_disruption(
        _request(fixture, initiative, source, perturbation),
        initiative,
        fixture.community,
        fixture.actions,
    )


def test_trained_successor_replaces_priya_with_leo_at_one_change() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    baseline = solve_initiative(source, initiative)
    assert baseline.status is SolverStatus.OPTIMAL
    assert [(item.role_instance_id, item.person_id) for item in baseline.assignments] == [
        ("DIGITAL_HELPER", "PRIYA"),
        ("FACILITATOR", "SAM"),
    ]

    perturbation = next(
        item
        for item in resilience.generate_canonical_perturbations(source, initiative, baseline)
        if item.target_id == "PRIYA"
    )
    response = recompile_minimum_disruption(
        _request(fixture, initiative, source, perturbation),
        initiative,
        fixture.community,
        fixture.actions,
    )

    assert response.status is SolverStatus.OPTIMAL
    assert response.stage1_status is SolverStatus.OPTIMAL
    assert response.stage2_status is SolverStatus.OPTIMAL
    assert response.minimum_proven is True
    assert response.minimum_assignment_changes == 1
    assert response.secondary_burden_optimal is True
    assert response.new_result is not None
    assert response.new_result.objective_value == 24
    assert [(item.role_instance_id, item.person_id) for item in response.new_result.assignments] == [
        ("DIGITAL_HELPER", "LEO"),
        ("FACILITATOR", "SAM"),
    ]
    assert [(item.role_id, item.before_person_id, item.after_person_id, item.changed) for item in response.role_diffs] == [
        ("DIGITAL_HELPER", "PRIYA", "LEO", True),
        ("FACILITATOR", "SAM", "SAM", False),
    ]
    assert response.preserved_assignments == 1
    assert response.changed_assignments == 1
    # The scenario is the only community accepted by the final witness.
    scenario = resilience.apply_canonical_perturbation(source, initiative, perturbation).state
    assert validate_analysis_witness(scenario, initiative, response.new_result)
    assert replay_assignment(scenario, initiative, response.new_result)


def test_recompile_receipt_round_trips_typed_cf_stress_spec_and_rejects_operational_id(
    monkeypatch,
) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    response = _run_with_spec(monkeypatch, fixture, initiative, source, perturbation)

    payload = response.model_dump(mode="json")
    assert payload["perturbation"]["type"] == "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
    assert payload["perturbation"]["initiative_id"] == initiative.id
    assert payload["scenario_state_id"].startswith("CF_STRESS_V1_")
    round_tripped = RecompileResponse.model_validate(payload)
    assert round_tripped.perturbation.id == perturbation.id

    bad_stub = SimpleNamespace(
        CounterfactualScenario=resilience.CounterfactualScenario,
        validate_counterfactual_scenario=resilience.validate_counterfactual_scenario,
        generate_canonical_perturbations=lambda source_state, initiative, baseline_result: [
            perturbation
        ],
        apply_canonical_perturbation=lambda source_state, initiative, spec: (
            lambda envelope: replace(
                envelope,
                state=envelope.state.model_copy(update={"state_id": "S_FORGED"}),
                scenario_state_id="S_FORGED",
            )
        )(resilience.apply_canonical_perturbation(source_state, initiative, spec)),
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: bad_stub)
    with pytest.raises(resilience.InvalidPerturbation, match="CF_STRESS"):
        recompile_minimum_disruption(
            _request(fixture, initiative, source, perturbation),
            initiative,
            fixture.community,
            fixture.actions,
        )


def test_forged_cf_receipt_digest_is_rejected_by_public_verifier(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")

    def forged_applier(source_state, initiative, spec):
        envelope = resilience.apply_canonical_perturbation(source_state, initiative, spec)
        return replace(envelope, scenario_content_hash="0" * 64)

    stub = _resilience_stub(
        lambda source_state, initiative, baseline_result: [perturbation],
        forged_applier,
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: stub)

    with pytest.raises(resilience.InvalidPerturbation, match="content hash"):
        recompile_minimum_disruption(
            _request(fixture, initiative, source, perturbation),
            initiative,
            fixture.community,
            fixture.actions,
        )


def test_unknown_perturbation_id_is_rejected_after_full_catalogue_generation(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    stub = _resilience_stub(
        lambda source_state, initiative, baseline_result: [perturbation]
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: stub)
    request = _request(fixture, initiative, source, perturbation).model_copy(
        update={"perturbation_id": "P_UNKNOWN"}
    )

    with pytest.raises(InvalidPerturbation, match="not in the canonical catalogue"):
        recompile_minimum_disruption(
            request,
            initiative,
            fixture.community,
            fixture.actions,
        )


def test_catalogue_overflow_fails_before_perturbation_resolution(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    stub = _resilience_stub(
        lambda source_state, initiative, baseline_result: [perturbation] * 21,
        lambda *args: pytest.fail("overflow must stop before apply"),
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: stub)

    with pytest.raises(PerturbationCatalogueTooLarge) as raised:
        recompile_minimum_disruption(
            _request(fixture, initiative, source, perturbation),
            initiative,
            fixture.community,
            fixture.actions,
        )
    assert raised.value.catalogue_size == 21


def test_minimum_change_matches_bruteforce_assignment_fixture(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    scenario = resilience.apply_canonical_perturbation(source, initiative, perturbation).state
    baseline = solve_initiative(source, initiative)
    baseline_by_role = {
        item.role_instance_id: item.person_id for item in baseline.assignments
    }

    role_candidates = {
        role.id: [person.id for person in scenario.people if role.required_capabilities <= person.capabilities]
        for role in initiative.roles
    }
    feasible_changes: list[int] = []
    for helper, facilitator in product(
        role_candidates["DIGITAL_HELPER"], role_candidates["FACILITATOR"]
    ):
        assignments = {
            "DIGITAL_HELPER": helper,
            "FACILITATOR": facilitator,
        }
        if helper == facilitator:
            continue
        if replay_assignment(
            scenario,
            initiative,
            assignments,
            venue_id="LIBRARY_ROOM",
            start_slot="SAT_11",
        ):
            feasible_changes.append(
                sum(assignments[role.id] != baseline_by_role[role.id] for role in initiative.roles)
            )

    response = _run_with_spec(monkeypatch, fixture, initiative, source, perturbation)
    assert response.minimum_assignment_changes == min(feasible_changes)
    assert response.minimum_assignment_changes == 1


@pytest.mark.parametrize("kind", ["venue", "resource"])
def test_venue_and_resource_loss_are_infeasible_without_replacement(monkeypatch, kind: str) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _venue_spec(source, initiative) if kind == "venue" else _resource_spec(source, initiative)

    response = _run_with_spec(monkeypatch, fixture, initiative, source, perturbation)

    assert response.status is SolverStatus.INFEASIBLE
    assert response.stage1_status is SolverStatus.INFEASIBLE
    assert response.stage2_status is None
    assert response.new_result is None
    assert response.role_diffs == []
    assert response.minimum_proven is False
    assert response.minimum_assignment_changes is None


def test_stage1_feasible_fails_closed_without_stage2(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    _run_with_spec_original = _run_with_spec
    monkeypatch.setattr(
        "app.recompiler.solver_status_from_cp_sat",
        lambda _: SolverStatus.FEASIBLE,
    )
    monkeypatch.setattr(
        "app.recompiler.solve_compiled",
        lambda *args, **kwargs: pytest.fail("Stage 2 must not run after Stage 1 FEASIBLE"),
    )

    response = _run_with_spec_original(monkeypatch, fixture, initiative, source, perturbation)

    assert response.status is SolverStatus.UNKNOWN
    assert response.stage1_status is SolverStatus.FEASIBLE
    assert response.stage2_status is None
    assert response.stage2_solver_stats is None
    assert response.minimum_proven is False
    assert response.minimum_assignment_changes is None
    assert response.new_result is None
    assert "minimum" not in response.explanation.lower()


def test_stage1_objective_mismatch_fails_closed_as_contract_error(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    monkeypatch.setattr("app.recompiler.integral_objective_value", lambda _: 99)

    with pytest.raises(AnalyserContractError, match="does not match selected"):
        _run_with_spec(monkeypatch, fixture, initiative, source, perturbation)


def test_stage2_unknown_retains_only_proven_minimum_and_stage_receipts(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    perturbation = _person_spec(source, initiative, "PRIYA")
    unknown_stats = SolverStats(branches=17, conflicts=3, wall_time_seconds=0.25)

    def unknown_stage2(compiled, **kwargs):
        assert kwargs["num_search_workers"] == 1
        return InitiativeAnalysisResult(
            initiative_id=initiative.id,
            status=SolverStatus.UNKNOWN,
            solver_stats=unknown_stats,
        )

    monkeypatch.setattr("app.recompiler.solve_compiled", unknown_stage2)
    response = _run_with_spec(monkeypatch, fixture, initiative, source, perturbation)

    assert response.status is SolverStatus.UNKNOWN
    assert response.stage1_status is SolverStatus.OPTIMAL
    assert response.stage2_status is SolverStatus.UNKNOWN
    assert response.minimum_proven is True
    assert response.minimum_assignment_changes == 1
    assert response.stage1_solver_stats is not None
    assert response.stage2_solver_stats == unknown_stats
    assert response.new_result is None
    assert response.role_diffs == []
    assert response.preserved_assignments is None
    assert response.changed_assignments is None
    assert response.secondary_burden_optimal is False


def test_mutating_analyser_is_rejected_on_baseline_and_blocker_paths(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source = _trained_source(fixture)
    person_loss = _person_spec(source, initiative, "PRIYA")
    calls = 0
    mutate_after_baseline = False

    def mutating_analyser(community, initiative, *, relaxed_groups=()):
        nonlocal calls
        calls += 1
        result = solve_initiative(
            community,
            initiative,
            relaxed_groups=relaxed_groups,
        )
        if not mutate_after_baseline or calls > 1:
            community.people[0].available_slots.clear()
        return result

    stub = _resilience_stub(
        lambda source_state, initiative, baseline_result: [person_loss]
    )
    monkeypatch.setattr("app.recompiler._resilience_module", lambda: stub)
    request = _request(fixture, initiative, source, person_loss)
    with pytest.raises(AnalyserContractError, match="analysis state was mutated"):
        recompile_minimum_disruption(
            request,
            initiative,
            fixture.community,
            fixture.actions,
            mutating_analyser,
        )
    assert calls == 1

    # The baseline is valid on the first call; the same mutation must still
    # fail closed when an infeasible Stage 1 asks for factual blockers.
    calls = 0
    mutate_after_baseline = True
    venue_loss = _venue_spec(source, initiative)
    stub.generate_canonical_perturbations = (
        lambda source_state, initiative, baseline_result: [venue_loss]
    )
    request = _request(fixture, initiative, source, venue_loss)
    with pytest.raises(AnalyserContractError, match="analysis state was mutated"):
        recompile_minimum_disruption(
            request,
            initiative,
            fixture.community,
            fixture.actions,
            mutating_analyser,
        )
    assert calls > 1
