from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis_state import reconstruct_authoritative_state
from app.api_models import (
    CapabilityFrontierRequest,
    CapabilityFrontierResponse,
    FrontierActionResult,
    SolverStatus,
    StateDiff,
)
from app.errors import AnalyserContractError
from app.fixture import fresh_demo_fixture
from app.frontier import _scenario_receipt, evaluate_capability_frontier
from app.interventions import apply_action, canonical_state_hash, state_id_for
from app.models import CatalystAction, CommunityState, InitiativeBlueprint
from app.solver import solve_initiative


def _frontier(
    *,
    path: list[str] | None = None,
    actions=None,
    analyser=None,
):
    fixture = fresh_demo_fixture()
    request = CapabilityFrontierRequest(
        base_community=fixture.community.model_copy(deep=True),
        catalyst_path=path or [],
    )
    return fixture, evaluate_capability_frontier(
        request,
        fixture.initiatives,
        fixture.community,
        fixture.actions if actions is None else actions,
        analyser=solve_initiative if analyser is None else analyser,
    )


def _by_id(response):
    return {item.action_id: item for item in response.action_results}


def test_s0_fixture_frontier_reports_all_four_actions_and_real_before_after_sets() -> None:
    fixture, response = _frontier()
    assert response.source_state_id == "S0"
    assert response.baseline_statuses == {
        "BASIC_WORKSHOP": SolverStatus.OPTIMAL,
        "MULTILINGUAL_CLINIC": SolverStatus.INFEASIBLE,
        "REPAIR_SHARE": SolverStatus.INFEASIBLE,
    }
    assert response.baseline_buildable_ids == ["BASIC_WORKSHOP"]
    assert response.baseline_blocked_ids == ["MULTILINGUAL_CLINIC", "REPAIR_SHARE"]
    assert response.baseline_unknown_ids == []
    assert [item.action_id for item in response.action_results] == [
        "TRAIN_DIGITAL_HELPERS",
        "RECRUIT_HELPER_A",
        "RECRUIT_HELPER_B",
        "BORROW_TWO_LAPTOPS",
    ]

    actions = _by_id(response)
    assert all(item.applicable for item in actions.values())
    assert actions["TRAIN_DIGITAL_HELPERS"].newly_feasible_initiatives == [
        "MULTILINGUAL_CLINIC"
    ]
    assert actions["TRAIN_DIGITAL_HELPERS"].total_feasible_after == 2
    assert actions["TRAIN_DIGITAL_HELPERS"].statuses_after == {
        "BASIC_WORKSHOP": SolverStatus.OPTIMAL,
        "MULTILINGUAL_CLINIC": SolverStatus.OPTIMAL,
        "REPAIR_SHARE": SolverStatus.INFEASIBLE,
    }
    for action_id in (
        "RECRUIT_HELPER_A",
        "RECRUIT_HELPER_B",
        "BORROW_TWO_LAPTOPS",
    ):
        assert actions[action_id].newly_feasible_initiatives == []
        assert actions[action_id].lost_feasible_initiatives == []
        assert actions[action_id].total_feasible_after == 1
        assert actions[action_id].statuses_after == {
            "BASIC_WORKSHOP": SolverStatus.OPTIMAL,
            "MULTILINGUAL_CLINIC": SolverStatus.INFEASIBLE,
            "REPAIR_SHARE": SolverStatus.INFEASIBLE,
        }

    train = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")
    successor, expected_diff = apply_action(fixture.community, train)
    train_result = actions["TRAIN_DIGITAL_HELPERS"]
    assert train_result.produced_diff == expected_diff
    assert train_result.source_state_id == "S0"
    assert train_result.scenario_state_id is not None
    assert train_result.scenario_state_id.startswith("CF_FRONTIER_V1_")
    assert train_result.scenario_state_id != state_id_for(successor)
    assert train_result.scenario_content_hash == canonical_state_hash(successor)
    assert response.highest_leverage_action_id == "TRAIN_DIGITAL_HELPERS"
    assert response.pareto_action_ids == [
        "TRAIN_DIGITAL_HELPERS",
        "BORROW_TWO_LAPTOPS",
    ]

    round_trip = CapabilityFrontierResponse.model_validate(
        response.model_dump(mode="json")
    )
    assert round_trip == response


def test_path_reconstructs_source_and_repeated_action_is_inapplicable() -> None:
    fixture, response = _frontier(path=["TRAIN_DIGITAL_HELPERS"])
    assert response.source_state_id != "S0"
    assert response.baseline_buildable_ids == [
        "BASIC_WORKSHOP",
        "MULTILINGUAL_CLINIC",
    ]
    assert response.baseline_blocked_ids == ["REPAIR_SHARE"]
    repeated = _by_id(response)["TRAIN_DIGITAL_HELPERS"]
    assert not repeated.applicable
    assert repeated.scenario_state_id is None
    assert repeated.scenario_content_hash is None
    assert repeated.produced_diff is None
    assert repeated.statuses_after == {}
    assert repeated.newly_feasible_initiatives == []
    assert repeated.lost_feasible_initiatives == []
    assert repeated.unknown_initiatives == []
    assert repeated.total_feasible_after is None
    assert repeated.decisive_coverage_complete is False
    assert response.highest_leverage_action_id is None
    assert response.uncertainty_could_change_winner is False


def test_zero_unlock_and_no_applicable_actions_are_normal_domain_responses() -> None:
    fixture = fresh_demo_fixture()
    borrow = [action for action in fixture.actions if action.id == "BORROW_TWO_LAPTOPS"]
    _, zero_unlock = _frontier(actions=borrow)
    assert zero_unlock.highest_leverage_action_id is None
    assert zero_unlock.uncertainty_could_change_winner is False
    assert zero_unlock.pareto_action_ids == ["BORROW_TWO_LAPTOPS"]
    assert zero_unlock.action_results[0].newly_feasible_initiatives == []

    train = [action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS"]
    request = CapabilityFrontierRequest(
        base_community=fixture.community.model_copy(deep=True),
        catalyst_path=["TRAIN_DIGITAL_HELPERS"],
    )
    no_applicable = evaluate_capability_frontier(
        request,
        fixture.initiatives,
        fixture.community,
        train,
    )
    assert no_applicable.action_results[0].applicable is False
    assert no_applicable.pareto_action_ids == []
    assert no_applicable.highest_leverage_action_id is None
    assert no_applicable.uncertainty_could_change_winner is False


def test_actions_are_evaluated_only_from_source_and_in_catalogue_order() -> None:
    fixture = fresh_demo_fixture()
    train = CatalystAction.model_validate(
        {
            "id": "Z_TRAIN",
            "name": "Train resource coordinator",
            "cost": 1,
            "effects": [
                {
                    "type": "add_capability",
                    "person_id": "PRIYA",
                    "capability_id": "resource_access",
                }
            ],
        }
    )
    dependent = CatalystAction.model_validate(
        {
            "id": "A_RESOURCE",
            "name": "Release reserved laptop",
            "cost": 1,
            "preconditions": {
                "person_capabilities": [
                    {"person_id": "PRIYA", "capability_id": "resource_access"}
                ]
            },
            "effects": [
                {
                    "type": "add_resource_quantity",
                    "resource_id": "LIBRARY_LAPTOPS",
                    "quantity": 1,
                }
            ],
        }
    )
    calls: list[tuple[str, str]] = []

    def status_only_analyser(community: CommunityState, initiative: InitiativeBlueprint):
        calls.append((community.state_id, initiative.id))
        return {"status": "INFEASIBLE"}

    response = evaluate_capability_frontier(
        CapabilityFrontierRequest(base_community=fixture.community.model_copy(deep=True)),
        fixture.initiatives,
        fixture.community,
        [dependent, train],
        analyser=status_only_analyser,
    )
    assert [item.action_id for item in response.action_results] == [
        "A_RESOURCE",
        "Z_TRAIN",
    ]
    assert response.action_results[0].applicable is False
    assert response.action_results[1].applicable is True
    assert len(calls) == len(fixture.initiatives) * 2
    # The dependent action must not observe Z_TRAIN's separate candidate state.
    assert all(state_id == "S0" for state_id, _ in calls[: len(fixture.initiatives)])


def test_mutating_analyser_is_rejected_and_caller_inputs_survive() -> None:
    fixture = fresh_demo_fixture()
    before_base = fixture.community.model_dump(mode="json")
    before_actions = [action.model_dump(mode="json") for action in fixture.actions]
    before_initiatives = [initiative.model_dump(mode="json") for initiative in fixture.initiatives]

    def mutating_analyser(community: CommunityState, initiative: InitiativeBlueprint):
        community.people[0].name = "MUTATED COPY"
        initiative.name = "MUTATED INITIATIVE COPY"
        return solve_initiative(community, initiative)

    with pytest.raises(AnalyserContractError, match="mutated its input"):
        evaluate_capability_frontier(
            CapabilityFrontierRequest(base_community=fixture.community.model_copy(deep=True)),
            fixture.initiatives,
            fixture.community,
            fixture.actions,
            analyser=mutating_analyser,
        )
    assert fixture.community.model_dump(mode="json") == before_base
    assert [action.model_dump(mode="json") for action in fixture.actions] == before_actions
    assert [
        initiative.model_dump(mode="json") for initiative in fixture.initiatives
    ] == before_initiatives


def test_after_action_mutating_analyser_is_rejected_without_leaking_source_or_actions() -> None:
    fixture = fresh_demo_fixture()
    before_base = fixture.community.model_dump(mode="json")
    before_actions = [action.model_dump(mode="json") for action in fixture.actions]
    before_initiatives = [
        initiative.model_dump(mode="json") for initiative in fixture.initiatives
    ]

    def mutating_after_analyser(community: CommunityState, initiative: InitiativeBlueprint):
        if community.state_id.startswith("CF_FRONTIER_V1_"):
            community.resources[0].quantity += 99
            initiative.roles[0].label = "MUTATED AFTER COPY"
        return solve_initiative(community, initiative)

    with pytest.raises(AnalyserContractError, match="mutated its input"):
        evaluate_capability_frontier(
            CapabilityFrontierRequest(base_community=fixture.community.model_copy(deep=True)),
            fixture.initiatives,
            fixture.community,
            fixture.actions,
            analyser=mutating_after_analyser,
        )
    assert fixture.community.model_dump(mode="json") == before_base
    assert [action.model_dump(mode="json") for action in fixture.actions] == before_actions
    assert [
        initiative.model_dump(mode="json") for initiative in fixture.initiatives
    ] == before_initiatives


def test_feasible_witness_is_replayed_and_invalid_witness_fails_closed() -> None:
    fixture = fresh_demo_fixture()

    def invalid_analyser(community: CommunityState, initiative: InitiativeBlueprint):
        result = solve_initiative(community, initiative).model_copy(deep=True)
        if result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            result.objective_value = (result.objective_value or 0) + 1
        return result

    with pytest.raises(AnalyserContractError, match="canonical replay"):
        evaluate_capability_frontier(
            CapabilityFrontierRequest(base_community=fixture.community.model_copy(deep=True)),
            fixture.initiatives,
            fixture.community,
            fixture.actions,
            analyser=invalid_analyser,
        )


def test_unknown_after_status_is_never_counted_and_withholds_winner() -> None:
    fixture = fresh_demo_fixture()

    def unknown_training_clinic(
        community: CommunityState,
        initiative: InitiativeBlueprint,
    ):
        if (
            initiative.id == "MULTILINGUAL_CLINIC"
            and community.state_id.startswith("CF_FRONTIER_V1_")
        ):
            return {"status": "UNKNOWN"}
        return solve_initiative(community, initiative)

    _, response = _frontier(analyser=unknown_training_clinic)
    assert response.highest_leverage_action_id is None
    assert response.uncertainty_could_change_winner is True
    assert "incomplete" in response.ranking_explanation.lower()
    training = _by_id(response)["TRAIN_DIGITAL_HELPERS"]
    assert training.decisive_coverage_complete is False
    assert training.unknown_initiatives == ["MULTILINGUAL_CLINIC"]
    assert training.newly_feasible_initiatives == []
    assert training.lost_feasible_initiatives == []
    assert training.total_feasible_after == 1


def test_unknown_baseline_is_unresolved_even_when_a_candidate_returns_feasible() -> None:
    fixture = fresh_demo_fixture()

    def unknown_baseline_clinic(
        community: CommunityState,
        initiative: InitiativeBlueprint,
    ):
        if initiative.id == "MULTILINGUAL_CLINIC" and not community.state_id.startswith(
            "CF_FRONTIER_V1_"
        ):
            return {"status": "UNKNOWN"}
        return solve_initiative(community, initiative)

    _, response = _frontier(analyser=unknown_baseline_clinic)
    assert response.baseline_unknown_ids == ["MULTILINGUAL_CLINIC"]
    assert response.highest_leverage_action_id is None
    assert response.uncertainty_could_change_winner is True
    training = _by_id(response)["TRAIN_DIGITAL_HELPERS"]
    assert training.unknown_initiatives == ["MULTILINGUAL_CLINIC"]
    assert training.newly_feasible_initiatives == []
    assert training.decisive_coverage_complete is False


def test_pareto_keeps_equal_count_equal_cost_ties_and_uses_id_for_winner() -> None:
    fixture = fresh_demo_fixture()
    training = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")
    tie = training.model_copy(deep=True)
    tie.id = "A_TRAIN_TIE"
    actions = [*fixture.actions, tie]
    _, response = _frontier(actions=actions)
    assert response.highest_leverage_action_id == "A_TRAIN_TIE"
    assert response.pareto_action_ids == [
        "A_TRAIN_TIE",
        "TRAIN_DIGITAL_HELPERS",
        "BORROW_TWO_LAPTOPS",
    ]


def test_frontier_receipt_is_not_an_operational_successor_and_reconstruction_is_exact() -> None:
    fixture, response = _frontier()
    train = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")
    source = reconstruct_authoritative_state(
        fixture.community,
        [],
        fixture.community,
        fixture.actions,
    )
    operational_successor, _ = apply_action(source, train)
    receipt = _by_id(response)["TRAIN_DIGITAL_HELPERS"]
    assert receipt.source_state_id == source.state_id
    assert receipt.scenario_state_id != operational_successor.state_id
    assert receipt.scenario_state_id.startswith("CF_FRONTIER_V1_")
    assert receipt.scenario_content_hash == canonical_state_hash(operational_successor)
    recomputed_id, recomputed_hash = _scenario_receipt(source, train, operational_successor)
    assert receipt.scenario_state_id == recomputed_id
    assert receipt.scenario_content_hash == recomputed_hash
    assert operational_successor.parent_state_id == source.state_id


def test_frontier_models_reject_operational_receipts_and_inapplicable_payloads() -> None:
    with pytest.raises(ValidationError, match="CF_FRONTIER_V1"):
        FrontierActionResult(
            source_state_id="S0",
            action_id="ACTION",
            action_name="Action",
            cost=1,
            applicable=True,
            scenario_state_id="S_OPERATIONAL_SUCCESSOR",
            scenario_content_hash="0" * 64,
            produced_diff=StateDiff(),
            total_feasible_after=0,
            decisive_coverage_complete=True,
            explanation="bad namespace",
        )

    with pytest.raises(ValidationError, match="must not carry a scenario receipt"):
        FrontierActionResult(
            source_state_id="S0",
            action_id="ACTION",
            action_name="Action",
            cost=1,
            applicable=False,
            scenario_state_id="CF_FRONTIER_V1_" + "A" * 64,
            scenario_content_hash="0" * 64,
            produced_diff=StateDiff(),
            decisive_coverage_complete=False,
            explanation="bad inapplicable receipt",
        )


def test_serialized_frontier_response_rejects_a_tampered_operational_scenario_id() -> None:
    _, response = _frontier()
    payload = response.model_dump(mode="json")
    payload["action_results"][0]["scenario_state_id"] = "S_OPERATIONAL_SUCCESSOR"
    with pytest.raises(ValidationError, match="CF_FRONTIER_V1"):
        CapabilityFrontierResponse.model_validate(payload)


@pytest.mark.parametrize(
    "status",
    [SolverStatus.INFEASIBLE, SolverStatus.UNKNOWN],
)
def test_status_only_nonfeasible_analyser_results_are_supported(status: SolverStatus) -> None:
    fixture = fresh_demo_fixture()

    def analyser(community: CommunityState, initiative: InitiativeBlueprint):
        del community, initiative
        return {"status": status.value}

    _, response = _frontier(analyser=analyser)
    assert all(value is status for value in response.baseline_statuses.values())
    assert all(
        not item.newly_feasible_initiatives
        for item in response.action_results
        if item.applicable
    )
