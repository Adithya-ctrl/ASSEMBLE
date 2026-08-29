from __future__ import annotations

from copy import deepcopy

import pytest

from app import resilience
from app.api_models import SolverStatus, StressTestRequest
from app.errors import AnalyserContractError
from app.fixture import fresh_demo_fixture

from .oracle_support import (
    apply_perturbation_locally,
    assignment_tuple,
    canonical_content,
    changed_fields,
    content_hash,
    is_feasible,
    legal_assemblies,
    minimum_burden,
    oracle_spec_dicts,
    perturbation_receipt_id,
    reconstruct_path_locally,
)


def _initiative(fixture, initiative_id: str):
    return next(item for item in fixture.initiatives if item.id == initiative_id)


def _stress_request(fixture, initiative_id: str, path: list[str] | None = None):
    return StressTestRequest(
        base_community=fixture.community.model_copy(deep=True),
        initiative_id=initiative_id,
        catalyst_path=path or [],
    )


def _outcome_by_id(response):
    return {outcome.perturbation_id: outcome for outcome in response.outcomes}


def test_catalogue_is_complete_and_each_entry_has_one_independent_fact_delta() -> None:
    """G1-G5: derive the expected catalogue without production helpers."""

    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    legal = legal_assemblies(fixture.community, initiative)
    assert legal, "the independent oracle must find the documented baseline"
    best_burden = min(item[3] for item in legal)
    best = [item for item in legal if item[3] == best_burden]
    # BASIC_WORKSHOP has a unique legal optimum at S0, so catalogue identity
    # can be derived entirely from domain facts rather than a CP-SAT witness.
    assert len(best) == 1
    baseline_assignments, baseline_venue, baseline_start, _ = best[0]
    assert baseline_start.value == "SAT_11"

    expected_specs = oracle_spec_dicts(
        fixture.community,
        initiative,
        baseline_assignments,
        baseline_venue,
    )
    source_before = fixture.community.model_dump(mode="json")
    initiative_before = initiative.model_dump(mode="json")

    response = resilience.run_stress_test(
        _stress_request(fixture, initiative.id),
        initiative,
        fixture.community,
        fixture.actions,
    )

    assert response.source_state_id == fixture.community.state_id
    assert response.source_content_hash == content_hash(fixture.community)
    assert response.baseline_result.status in {
        SolverStatus.OPTIMAL,
        SolverStatus.FEASIBLE,
    }
    assert assignment_tuple(response.baseline_result) == baseline_assignments
    assert response.baseline_result.objective_value == best_burden

    actual_specs = [item.perturbation.model_dump(mode="json") for item in response.outcomes]
    assert actual_specs == expected_specs
    assert response.catalogue_size == len(expected_specs) == 4
    assert response.unknown_count == 0
    assert response.failed_count == len(expected_specs)
    assert response.survived_count == 0
    assert response.decisive_count == len(expected_specs)
    assert response.resilience_ratio == 0
    assert response.critical_perturbation_ids == [item["id"] for item in expected_specs]
    assert all(item.status is SolverStatus.INFEASIBLE for item in response.outcomes)
    assert all(item.survived is False for item in response.outcomes)
    assert all(item.criticality.value == "CRITICAL" for item in response.outcomes)
    assert all(item.scenario_state_id.startswith("CF_STRESS_V1_") for item in response.outcomes)
    assert all(not item.scenario_state_id.startswith("S") for item in response.outcomes)

    # Apply each returned spec through the SUT, then independently verify that
    # the only changed domain fact is the declared target field.  This is a
    # separate assertion from the SUT's own structural-delta checker.
    for outcome in response.outcomes:
        spec = outcome.perturbation
        local_scenario = apply_perturbation_locally(fixture.community, spec)
        sut_scenario = resilience.apply_canonical_perturbation(
            fixture.community,
            initiative,
            spec,
        )
        expected_field = (
            ("people", spec.target_id, "available_slots")
            if spec.type.value == "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
            else ("spaces", spec.target_id, "available_slots")
            if spec.type.value == "MAKE_SELECTED_VENUE_UNAVAILABLE"
            else ("resources", spec.target_id, "quantity")
        )
        assert changed_fields(fixture.community, local_scenario) == [expected_field]
        assert changed_fields(fixture.community, sut_scenario.state) == [expected_field]
        assert canonical_content(sut_scenario.state) == canonical_content(local_scenario)
        assert sut_scenario.scenario_content_hash == content_hash(local_scenario)
        assert sut_scenario.scenario_state_id == perturbation_receipt_id(
            fixture.community,
            initiative,
            spec,
            local_scenario,
        )
        assert sut_scenario.state.parent_state_id == fixture.community.parent_state_id
        assert sut_scenario.state.state_id == sut_scenario.scenario_state_id

    assert fixture.community.model_dump(mode="json") == source_before
    assert initiative.model_dump(mode="json") == initiative_before


def test_trained_catalogue_outcomes_match_independent_feasibility_and_ratio() -> None:
    """G2-G6: classify every trained-Basic scenario from local enumeration."""

    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    local_source = reconstruct_path_locally(
        fixture.community,
        ["TRAIN_DIGITAL_HELPERS"],
        fixture.actions,
    )
    assert is_feasible(local_source, initiative)

    response = resilience.run_stress_test(
        _stress_request(fixture, initiative.id, ["TRAIN_DIGITAL_HELPERS"]),
        initiative,
        fixture.community,
        fixture.actions,
    )
    assert response.source_state_id == local_source.state_id
    assert response.source_content_hash == content_hash(local_source)

    expected_decisive: list[bool] = []
    for outcome in response.outcomes:
        local_scenario = apply_perturbation_locally(local_source, outcome.perturbation)
        expected = is_feasible(local_scenario, initiative)
        expected_decisive.append(expected)
        actual_feasible = outcome.status in {
            SolverStatus.OPTIMAL,
            SolverStatus.FEASIBLE,
        }
        assert actual_feasible is expected
        if expected:
            assert outcome.survived is True
            assert outcome.objective_value == minimum_burden(local_scenario, initiative)
            assert outcome.objective_value is not None
            assert outcome.objective_delta == (
                outcome.objective_value - response.baseline_result.objective_value
            )
            assert outcome.assignment_changes == len(outcome.changed_roles)
        else:
            assert outcome.survived is False
            assert outcome.objective_value is None
            assert outcome.assignment_changes is None
            assert outcome.after_venue_id is None
            assert outcome.after_start_slot is None

    expected_survived = sum(expected_decisive)
    expected_failed = len(expected_decisive) - expected_survived
    assert response.catalogue_size == len(expected_decisive)
    assert response.survived_count == expected_survived
    assert response.failed_count == expected_failed
    assert response.unknown_count == 0
    assert response.decisive_count == len(expected_decisive)
    assert response.resilience_ratio == expected_survived / len(expected_decisive)
    assert response.critical_perturbation_ids == [
        outcome.perturbation_id
        for outcome in response.outcomes
        if outcome.status is SolverStatus.INFEASIBLE
    ]


def test_unknown_scenarios_are_unresolved_and_model_invalid_is_not_infeasible() -> None:
    """G7: UNKNOWN is honest, and an unsupported MODEL_INVALID cannot be hidden."""

    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    source_hash = content_hash(fixture.community)

    # This is only a controlled analyser seam.  The expectation is the local
    # status policy below, not a call to the production solver.
    from app.solver import solve_initiative

    baseline = solve_initiative(fixture.community, initiative)

    def unknown_scenarios(community, declared, **kwargs):
        del kwargs
        if content_hash(community) == source_hash:
            return baseline
        return {"status": "UNKNOWN"}

    response = resilience.run_stress_test(
        _stress_request(fixture, initiative.id),
        initiative,
        fixture.community,
        fixture.actions,
        analyser=unknown_scenarios,
    )
    assert response.catalogue_size == 4
    assert response.unknown_count == 4
    assert response.decisive_count == 0
    assert response.survived_count == 0
    assert response.failed_count == 0
    assert response.resilience_ratio is None
    assert response.critical_perturbation_ids == []
    assert all(item.status is SolverStatus.UNKNOWN for item in response.outcomes)
    assert all(item.survived is None for item in response.outcomes)
    assert all(item.criticality.value == "UNKNOWN" for item in response.outcomes)
    assert all(item.objective_value is None for item in response.outcomes)
    assert all(item.blockers == [] for item in response.outcomes)

    def model_invalid_scenarios(community, declared, **kwargs):
        del kwargs
        if content_hash(community) == source_hash:
            return baseline
        return {"status": "MODEL_INVALID"}

    with pytest.raises(AnalyserContractError, match=r"unknown.*status"):
        resilience.run_stress_test(
            _stress_request(fixture, initiative.id),
            initiative,
            fixture.community,
            fixture.actions,
            analyser=model_invalid_scenarios,
        )


def test_scenario_application_is_source_pure_even_when_spec_payload_is_copied() -> None:
    """G10: counterfactual mutation never leaks into operational source data."""

    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    response = resilience.run_stress_test(
        _stress_request(fixture, initiative.id),
        initiative,
        fixture.community,
        fixture.actions,
    )
    source_before = deepcopy(fixture.community.model_dump(mode="json"))
    initiative_before = deepcopy(initiative.model_dump(mode="json"))
    for outcome in response.outcomes:
        # Reparse a fresh typed spec to make sure no object alias is relied on.
        spec = type(outcome.perturbation).model_validate(
            outcome.perturbation.model_dump(mode="json")
        )
        envelope = resilience.apply_canonical_perturbation(
            fixture.community,
            initiative,
            spec,
        )
        envelope.state.people[:] = list(reversed(envelope.state.people))
        assert fixture.community.model_dump(mode="json") == source_before
        assert initiative.model_dump(mode="json") == initiative_before
