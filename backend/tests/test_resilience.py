from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app import resilience
from app.api_models import (
    InitiativeAnalysisResult,
    SolverStats,
    SolverStatus,
    StressTestRequest,
)
from app.errors import AnalyserContractError
from app.fixture import fresh_demo_fixture
from app.interventions import apply_action, canonical_state_hash, canonical_state_payload
from app.models import (
    InitiativeBlueprint,
    OrganisationBlock,
    PersonBlock,
    RoleRequirement,
)
from app.resilience import (
    BaselineNotFeasible,
    InvalidPerturbation,
    PerturbationCatalogueTooLarge,
    apply_canonical_perturbation,
    generate_canonical_perturbations,
    run_stress_test,
)
from app.solver import solve_initiative


def _initiative(fixture, initiative_id: str) -> InitiativeBlueprint:
    return next(item for item in fixture.initiatives if item.id == initiative_id)


def _request(community, initiative_id: str, path: list[str] | None = None) -> StressTestRequest:
    return StressTestRequest(
        base_community=community.model_copy(deep=True),
        initiative_id=initiative_id,
        catalyst_path=path or [],
    )


def _trained_clinic():
    fixture = fresh_demo_fixture()
    training = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")
    source, _ = apply_action(fixture.community, training)
    return fixture, source, _initiative(fixture, "MULTILINGUAL_CLINIC")


def _unknown_result(initiative_id: str) -> InitiativeAnalysisResult:
    return InitiativeAnalysisResult(
        initiative_id=initiative_id,
        status=SolverStatus.UNKNOWN,
        solver_stats=SolverStats(branches=0, conflicts=0, wall_time_seconds=0),
    )


def test_basic_catalogue_exact_values_and_round_trip() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)

    catalogue = generate_canonical_perturbations(fixture.community, initiative, baseline)
    assert [item.type.value for item in catalogue] == [
        "MAKE_ASSIGNED_PERSON_UNAVAILABLE",
        "MAKE_ASSIGNED_PERSON_UNAVAILABLE",
        "MAKE_SELECTED_VENUE_UNAVAILABLE",
        "REDUCE_AVAILABLE_RESOURCE",
    ]
    assert [item.target_id for item in catalogue] == [
        "LEO", "SAM", "LIBRARY_ROOM", "LIBRARY_LAPTOPS"
    ]
    assert catalogue[-1].required_quantity == 4
    assert (catalogue[-1].before_quantity, catalogue[-1].after_quantity) == (6, 3)
    assert all(item.initiative_id == initiative.id for item in catalogue)
    assert all("becomes unavailable" in item.label for item in catalogue[:3])
    assert all(item.id.startswith("ASSEMBLE_STRESS_PERTURBATION_V1_") for item in catalogue)
    assert all(canonical_state_hash(fixture.community) == item.source_content_hash for item in catalogue)

    response = run_stress_test(
        _request(fixture.community, initiative.id),
        initiative,
        fixture.community,
        fixture.actions,
    )
    assert (response.source_state_id, response.source_content_hash) == (
        "S0", canonical_state_hash(fixture.community)
    )
    assert (response.catalogue_size, response.decisive_count) == (4, 4)
    assert (response.survived_count, response.failed_count, response.unknown_count) == (0, 4, 0)
    assert response.resilience_ratio == 0
    assert len(response.critical_perturbation_ids) == 4
    assert all(item.status is SolverStatus.INFEASIBLE for item in response.outcomes)
    assert all(item.criticality.value == "CRITICAL" for item in response.outcomes)
    assert all(item.scenario_state_id.startswith("CF_STRESS_V1_") for item in response.outcomes)

    parsed = type(response).model_validate(response.model_dump(mode="json"))
    assert parsed == response


def test_trained_clinic_catalogue_and_precise_helper_blocker() -> None:
    fixture, source, clinic = _trained_clinic()
    baseline = solve_initiative(source, clinic)
    assert (baseline.status, baseline.objective_value) == (SolverStatus.OPTIMAL, 48)
    assert {item.person_id for item in baseline.assignments} == {"PRIYA", "LEO", "SAM", "AMIRA"}

    catalogue = generate_canonical_perturbations(source, clinic, baseline)
    assert len(catalogue) == 6
    assert [item.target_id for item in catalogue] == [
        "AMIRA", "LEO", "PRIYA", "SAM", "LIBRARY_ROOM", "LIBRARY_LAPTOPS"
    ]
    resource = catalogue[-1]
    assert (resource.required_quantity, resource.before_quantity, resource.after_quantity) == (5, 6, 4)

    response = run_stress_test(
        _request(fixture.community, clinic.id, ["TRAIN_DIGITAL_HELPERS"]),
        clinic,
        fixture.community,
        fixture.actions,
    )
    assert response.source_state_id == source.state_id
    assert (response.catalogue_size, response.decisive_count) == (6, 6)
    assert (response.survived_count, response.failed_count, response.unknown_count) == (0, 6, 0)
    assert response.resilience_ratio == 0

    leo = next(
        item
        for item in response.outcomes
        if item.perturbation.target_id == "LEO"
    )
    helper_facts = [
        fact
        for requirement_set in leo.blockers
        for fact in requirement_set.facts
        if fact.capability == "digital_support"
    ]
    assert any(
        (fact.required, fact.available, fact.relevant_ids)
        == (3, 2, ["PRIYA", "SAM"])
        for fact in helper_facts
    )


def test_apply_proves_one_field_delta_and_preserves_source_and_initiative() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)
    catalogue = generate_canonical_perturbations(fixture.community, initiative, baseline)
    source_state_dump = canonical_state_payload(fixture.community)
    initiative_dump = initiative.model_dump(mode="json")

    for perturbation in catalogue:
        scenario = apply_canonical_perturbation(fixture.community, initiative, perturbation)
        assert canonical_state_payload(fixture.community) == source_state_dump
        assert initiative.model_dump(mode="json") == initiative_dump
        assert scenario.state.state_id == scenario.scenario_state_id
        assert scenario.scenario_state_id.startswith("CF_STRESS_V1_")
        assert not scenario.scenario_state_id.startswith("S")
        assert scenario.state.parent_state_id == fixture.community.parent_state_id
        assert scenario.state.parent_state_id != fixture.community.state_id
        before = canonical_state_payload(fixture.community)
        after = canonical_state_payload(scenario.state)
        before_entities = {
            group: {item["id"]: item for item in before[group]}
            for group in ("people", "spaces", "resources")
        }
        after_entities = {
            group: {item["id"]: item for item in after[group]}
            for group in ("people", "spaces", "resources")
        }
        changed = [
            (group, entity_id, key)
            for group in before_entities
            for entity_id in before_entities[group]
            for key in before_entities[group][entity_id]
            if before_entities[group][entity_id][key] != after_entities[group][entity_id][key]
        ]
        expected_field = (
            "people", perturbation.target_id, "available_slots"
        ) if perturbation.type.value == "MAKE_ASSIGNED_PERSON_UNAVAILABLE" else (
            "spaces", perturbation.target_id, "available_slots"
        ) if perturbation.type.value == "MAKE_SELECTED_VENUE_UNAVAILABLE" else (
            "resources", perturbation.target_id, "quantity"
        )
        assert changed == [expected_field]
        assert scenario.scenario_content_hash == canonical_state_hash(scenario.state)
        assert scenario.scenario_state_id == resilience._scenario_id(
            canonical_state_hash(fixture.community),
            initiative.id,
            perturbation,
            canonical_state_payload(scenario.state),
        )


def test_duplicate_selected_people_collapse_to_one_entry() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP").model_copy(deep=True)
    initiative.id = "DUPLICATE_STRESS"
    initiative.roles[0].allow_shared_person = True
    initiative.roles[1].allow_shared_person = True
    initiative.roles[1].required_capabilities = {"digital_support"}
    baseline = solve_initiative(fixture.community, initiative)
    assert [item.person_id for item in baseline.assignments] == ["LEO", "LEO"]
    catalogue = generate_canonical_perturbations(fixture.community, initiative, baseline)
    assert [item.target_id for item in catalogue] == ["LEO", "LIBRARY_ROOM", "LIBRARY_LAPTOPS"]


def test_duplicate_resource_requirement_fails_closed() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP").model_copy(deep=True)
    initiative.resources.append(initiative.resources[0].model_copy(deep=True))
    baseline = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    with pytest.raises(InvalidPerturbation, match="duplicate resource"):
        generate_canonical_perturbations(fixture.community, initiative, baseline)


def test_catalogue_overflow_is_complete_and_prevents_scenario_calls() -> None:
    fixture = fresh_demo_fixture()
    basic = _initiative(fixture, "BASIC_WORKSHOP")
    for index in range(21):
        fixture.community.people.append(
            PersonBlock(
                id=f"P{index:02d}",
                name=f"Person {index}",
                organisation_id="TECH_SOCIETY",
                capabilities={"digital_support"},
                languages={"en"},
                available_slots={"SAT_11", "SAT_12"},
                max_contribution_slots=2,
            )
        )
    initiative = basic.model_copy(deep=True)
    initiative.id = "OVERFLOW_STRESS"
    initiative.roles = [
        RoleRequirement(
            id=f"ROLE_{index:02d}",
            label=f"Role {index}",
            required_capabilities={"digital_support"},
            allow_shared_person=False,
        )
        for index in range(21)
    ]
    baseline = solve_initiative(fixture.community, initiative)
    calls = 0

    def analyser(community, declared):
        nonlocal calls
        calls += 1
        return solve_initiative(community, declared)

    request = _request(fixture.community, initiative.id)
    with pytest.raises(PerturbationCatalogueTooLarge) as exc_info:
        run_stress_test(request, initiative, fixture.community, fixture.actions, analyser)
    assert exc_info.value.catalogue_size == 23
    assert calls == 1


def test_baseline_must_be_decisively_feasible() -> None:
    fixture = fresh_demo_fixture()
    clinic = _initiative(fixture, "MULTILINGUAL_CLINIC")
    with pytest.raises(BaselineNotFeasible):
        run_stress_test(
            _request(fixture.community, clinic.id),
            clinic,
            fixture.community,
            fixture.actions,
        )


def test_unknown_outcomes_are_excluded_from_decisive_denominator() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)

    def unknown_scenarios(community, declared):
        if community.state_id == fixture.community.state_id:
            return baseline
        return _unknown_result(declared.id)

    response = run_stress_test(
        _request(fixture.community, initiative.id),
        initiative,
        fixture.community,
        fixture.actions,
        unknown_scenarios,
    )
    assert (response.catalogue_size, response.unknown_count, response.decisive_count) == (4, 4, 0)
    assert response.resilience_ratio is None
    assert response.critical_perturbation_ids == []
    assert all(item.survived is None and item.criticality.value == "UNKNOWN" for item in response.outcomes)
    type(response).model_validate(response.model_dump(mode="json"))


@pytest.mark.parametrize("mutate", ["community", "initiative"])
def test_analyser_mutation_isolation_fails_at_baseline(mutate: str) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source_before = canonical_state_payload(fixture.community)
    initiative_before = initiative.model_dump(mode="json")

    def malicious(community, declared):
        if mutate == "community":
            community.people[0].available_slots.clear()
        else:
            declared.roles.reverse()
        return solve_initiative(community, declared)

    with pytest.raises(AnalyserContractError, match="mutated"):
        run_stress_test(
            _request(fixture.community, initiative.id),
            initiative,
            fixture.community,
            fixture.actions,
            malicious,
        )
    assert canonical_state_payload(fixture.community) == source_before
    assert initiative.model_dump(mode="json") == initiative_before


def test_analyser_mutation_isolation_fails_at_scenario_seam() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)
    calls = 0

    def malicious(community, declared):
        nonlocal calls
        calls += 1
        if calls > 1:
            community.resources[0].quantity += 1
        return baseline if calls == 1 else solve_initiative(community, declared)

    with pytest.raises(AnalyserContractError, match="mutated"):
        run_stress_test(
            _request(fixture.community, initiative.id),
            initiative,
            fixture.community,
            fixture.actions,
            malicious,
        )


def test_forged_perturbation_and_serialized_response_bindings_fail() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    baseline = solve_initiative(fixture.community, initiative)
    perturbation = generate_canonical_perturbations(fixture.community, initiative, baseline)[0]
    forged = perturbation.model_copy(deep=True)
    forged.id = "FORGED"
    with pytest.raises(InvalidPerturbation):
        apply_canonical_perturbation(fixture.community, initiative, forged)

    response = run_stress_test(
        _request(fixture.community, initiative.id), initiative, fixture.community, fixture.actions
    )
    payload = response.model_dump(mode="json")
    malformed_payloads = []
    for key, value in (
        ("decisive_count", 0),
        ("resilience_ratio", 1),
        ("source_content_hash", "0" * 64),
    ):
        altered = deepcopy(payload)
        altered[key] = value
        malformed_payloads.append(altered)
    altered = deepcopy(payload)
    altered["outcomes"][0]["source_state_id"] = "FORGED_SOURCE"
    malformed_payloads.append(altered)
    altered = deepcopy(payload)
    altered["outcomes"][0]["perturbation"]["initiative_id"] = "OTHER_INITIATIVE"
    malformed_payloads.append(altered)
    altered = deepcopy(payload)
    altered["outcomes"][0]["scenario_state_id"] = "SFORGED"
    malformed_payloads.append(altered)
    altered = deepcopy(payload)
    altered["outcomes"][0]["perturbation_id"] = "FORGED_PERTURBATION"
    malformed_payloads.append(altered)
    for malformed in malformed_payloads:
        with pytest.raises(ValidationError):
            type(response).model_validate(malformed)


def test_stress_rechecks_forged_counterfactual_receipt_before_analysis(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    original_apply = resilience.apply_canonical_perturbation

    def forged_apply(source, declared, perturbation):
        scenario = original_apply(source, declared, perturbation)
        forged_state = scenario.state.model_copy(deep=True)
        forged_state.state_id = "CF_STRESS_V1_" + ("0" * 64)
        return replace(
            scenario,
            state=forged_state,
            scenario_state_id=forged_state.state_id,
        )

    monkeypatch.setattr(resilience, "apply_canonical_perturbation", forged_apply)
    with pytest.raises(InvalidPerturbation, match="receipt"):
        run_stress_test(
            _request(fixture.community, initiative.id),
            initiative,
            fixture.community,
            fixture.actions,
        )
