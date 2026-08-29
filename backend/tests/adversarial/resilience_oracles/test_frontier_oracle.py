from __future__ import annotations

from copy import deepcopy

from app import frontier
from app.api_models import CapabilityFrontierRequest, SolverStatus
from app.fixture import fresh_demo_fixture
from app.models import AddResourceQuantityEffect, CatalystAction

from .oracle_support import (
    action_is_applicable,
    apply_action_locally,
    canonical_content,
    content_hash,
    frontier_receipt_id,
    is_feasible,
    reconstruct_path_locally,
)


def _by_action(response):
    return {item.action_id: item for item in response.action_results}


def _frontier_request(fixture, path: list[str] | None = None):
    return CapabilityFrontierRequest(
        base_community=fixture.community.model_copy(deep=True),
        catalyst_path=path or [],
    )


def _dominates(left, right) -> bool:
    left_count, left_cost = left[1], left[2]
    right_count, right_cost = right[1], right[2]
    return (
        left_count >= right_count
        and left_cost <= right_cost
        and (left_count > right_count or left_cost < right_cost)
    )


def test_one_action_frontier_matches_independent_enumeration_and_pareto_oracle() -> None:
    """I1/I4/I6: enumerate each action from one source and rank locally."""

    fixture = fresh_demo_fixture()
    request = _frontier_request(fixture)
    local_source = reconstruct_path_locally(
        fixture.community,
        [],
        fixture.actions,
    )
    initiatives = fixture.initiatives
    baseline_feasible = {
        initiative.id: is_feasible(local_source, initiative)
        for initiative in initiatives
    }
    expected_buildable = sorted(
        initiative_id
        for initiative_id, feasible in baseline_feasible.items()
        if feasible
    )
    expected_blocked = sorted(
        initiative_id
        for initiative_id, feasible in baseline_feasible.items()
        if not feasible
    )

    response = frontier.evaluate_capability_frontier(
        request,
        initiatives,
        fixture.community,
        fixture.actions,
    )
    assert response.source_state_id == local_source.state_id == "S0"
    assert response.baseline_buildable_ids == expected_buildable == ["BASIC_WORKSHOP"]
    assert response.baseline_blocked_ids == expected_blocked == [
        "MULTILINGUAL_CLINIC",
        "REPAIR_SHARE",
    ]
    assert response.baseline_unknown_ids == []

    candidates: list[tuple[str, int, int]] = []
    actual_results = response.action_results
    assert [item.action_id for item in actual_results] == [
        action.id for action in fixture.actions
    ]
    for action in fixture.actions:
        actual = _by_action(response)[action.id]
        applicable = action_is_applicable(local_source, action)
        assert actual.applicable is applicable
        if not applicable:
            assert actual.scenario_state_id is None
            assert actual.scenario_content_hash is None
            assert actual.produced_diff is None
            assert actual.statuses_after == {}
            assert actual.newly_feasible_initiatives == []
            assert actual.lost_feasible_initiatives == []
            assert actual.unknown_initiatives == []
            assert actual.total_feasible_after is None
            assert actual.decisive_coverage_complete is False
            continue

        local_successor, local_diff = apply_action_locally(local_source, action)
        local_after = {
            initiative.id: is_feasible(local_successor, initiative)
            for initiative in initiatives
        }
        expected_new = sorted(
            initiative_id
            for initiative_id in baseline_feasible
            if not baseline_feasible[initiative_id] and local_after[initiative_id]
        )
        expected_lost = sorted(
            initiative_id
            for initiative_id in baseline_feasible
            if baseline_feasible[initiative_id] and not local_after[initiative_id]
        )
        assert actual.statuses_after.keys() == local_after.keys()
        assert {
            initiative_id
            for initiative_id, status in actual.statuses_after.items()
            if status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        } == {
            initiative_id
            for initiative_id, feasible in local_after.items()
            if feasible
        }
        assert actual.newly_feasible_initiatives == expected_new
        assert actual.lost_feasible_initiatives == expected_lost
        assert actual.unknown_initiatives == []
        assert actual.total_feasible_after == sum(local_after.values())
        assert actual.decisive_coverage_complete is True
        assert actual.produced_diff is not None
        assert actual.produced_diff.model_dump(mode="json") == local_diff.model_dump(mode="json")
        assert actual.scenario_content_hash == content_hash(local_successor)
        assert actual.scenario_state_id == frontier_receipt_id(
            local_source,
            action,
            local_successor,
        )
        assert actual.scenario_state_id != local_successor.state_id
        assert canonical_content(local_successor) == canonical_content(
            local_successor.model_copy(deep=True)
        )
        candidates.append((action.id, len(expected_new), action.cost))

    expected_rank = sorted(candidates, key=lambda item: (-item[1], item[2], item[0]))
    expected_winner = next(
        (action_id for action_id, count, _ in expected_rank if count > 0),
        None,
    )
    expected_pareto = [
        item
        for item in expected_rank
        if not any(
            _dominates(other, item)
            for other in candidates
            if other != item
        )
    ]
    assert response.highest_leverage_action_id == expected_winner == "TRAIN_DIGITAL_HELPERS"
    assert response.pareto_action_ids == [item[0] for item in expected_pareto]
    assert response.uncertainty_could_change_winner is False
    assert "newly feasible initiatives descending" in response.ranking_explanation


def test_frontier_reconstructs_path_and_marks_repeated_action_inapplicable() -> None:
    """I1/I2/I6: a candidate is evaluated only from the reconstructed source."""

    fixture = fresh_demo_fixture()
    local_source = reconstruct_path_locally(
        fixture.community,
        ["TRAIN_DIGITAL_HELPERS"],
        fixture.actions,
    )
    response = frontier.evaluate_capability_frontier(
        _frontier_request(fixture, ["TRAIN_DIGITAL_HELPERS"]),
        fixture.initiatives,
        fixture.community,
        fixture.actions,
    )
    assert response.source_state_id == local_source.state_id
    assert response.baseline_buildable_ids == [
        initiative.id
        for initiative in fixture.initiatives
        if is_feasible(local_source, initiative)
    ]
    repeated = _by_action(response)["TRAIN_DIGITAL_HELPERS"]
    assert repeated.applicable is False
    assert repeated.scenario_state_id is None
    assert repeated.statuses_after == {}
    assert repeated.newly_feasible_initiatives == []
    assert repeated.lost_feasible_initiatives == []
    assert repeated.unknown_initiatives == []
    assert repeated.total_feasible_after is None
    assert repeated.decisive_coverage_complete is False
    assert response.highest_leverage_action_id is None
    assert response.pareto_action_ids == ["BORROW_TWO_LAPTOPS"]


def test_frontier_detects_a_decisive_feasibility_loss_without_monotonicity_assumption() -> None:
    """I5: a controlled analyser can expose a newly lost baseline initiative."""

    fixture = fresh_demo_fixture()
    recruit = next(
        action for action in fixture.actions if action.id == "RECRUIT_HELPER_A"
    )
    source_digest = content_hash(fixture.community)
    from app.solver import solve_initiative

    def loss_analyser(community, initiative, **kwargs):
        del kwargs
        if (
            content_hash(community) != source_digest
            and initiative.id == "BASIC_WORKSHOP"
            and any(person.id == "EXTERNAL_HELPER_A" for person in community.people)
        ):
            return {"status": "INFEASIBLE"}
        return solve_initiative(community, initiative)

    response = frontier.evaluate_capability_frontier(
        _frontier_request(fixture),
        fixture.initiatives,
        fixture.community,
        [recruit],
        analyser=loss_analyser,
    )
    result = response.action_results[0]
    assert result.applicable is True
    assert result.lost_feasible_initiatives == ["BASIC_WORKSHOP"]
    assert result.newly_feasible_initiatives == []
    assert result.unknown_initiatives == []
    assert result.decisive_coverage_complete is True
    assert result.total_feasible_after == 0
    assert response.highest_leverage_action_id is None
    assert response.uncertainty_could_change_winner is False


def test_frontier_unknown_candidate_withholds_winner_and_excludes_it_from_pareto() -> None:
    """I3: incomplete coverage is an honest uncertainty, not a gain/loss."""

    fixture = fresh_demo_fixture()
    unknown_action = CatalystAction(
        id="A_UNKNOWN",
        name="Unresolved inventory probe",
        cost=0,
        effects=[
            AddResourceQuantityEffect(
                type="add_resource_quantity",
                resource_id="LIBRARY_LAPTOPS",
                quantity=1,
            )
        ],
    )
    training = next(
        action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS"
    )
    actions = [unknown_action, training]
    source_digest = content_hash(fixture.community)
    from app.solver import solve_initiative

    def partial_analyser(community, initiative, **kwargs):
        del kwargs
        laptop_quantity = next(
            resource.quantity
            for resource in community.resources
            if resource.id == "LIBRARY_LAPTOPS"
        )
        if laptop_quantity == 7:
            return {"status": "UNKNOWN"}
        return solve_initiative(community, initiative)

    local_source = reconstruct_path_locally(fixture.community, [], actions)
    assert content_hash(local_source) == source_digest
    baseline_feasible = {
        initiative.id: is_feasible(local_source, initiative)
        for initiative in fixture.initiatives
    }
    response = frontier.evaluate_capability_frontier(
        _frontier_request(fixture),
        fixture.initiatives,
        fixture.community,
        actions,
        analyser=partial_analyser,
    )
    by_action = _by_action(response)
    unresolved = by_action["A_UNKNOWN"]
    assert unresolved.applicable is True
    assert unresolved.unknown_initiatives == [
        initiative.id for initiative in fixture.initiatives
    ]
    assert unresolved.newly_feasible_initiatives == []
    assert unresolved.lost_feasible_initiatives == []
    assert unresolved.decisive_coverage_complete is False
    assert unresolved.total_feasible_after == 0

    trained = by_action["TRAIN_DIGITAL_HELPERS"]
    assert trained.decisive_coverage_complete is True
    assert trained.unknown_initiatives == []
    assert trained.newly_feasible_initiatives == ["MULTILINGUAL_CLINIC"]
    assert trained.lost_feasible_initiatives == []
    assert trained.total_feasible_after == sum(baseline_feasible.values()) + 1
    assert response.highest_leverage_action_id is None
    assert response.uncertainty_could_change_winner is True
    assert response.pareto_action_ids == ["TRAIN_DIGITAL_HELPERS"]
    assert "withheld" in response.ranking_explanation


def test_frontier_is_input_pure_and_repeatable() -> None:
    fixture = fresh_demo_fixture()
    base_before = deepcopy(fixture.community.model_dump(mode="json"))
    initiatives_before = [
        deepcopy(initiative.model_dump(mode="json"))
        for initiative in fixture.initiatives
    ]
    actions_before = [
        deepcopy(action.model_dump(mode="json"))
        for action in fixture.actions
    ]
    first = frontier.evaluate_capability_frontier(
        _frontier_request(fixture),
        fixture.initiatives,
        fixture.community,
        fixture.actions,
    )
    second = frontier.evaluate_capability_frontier(
        _frontier_request(fixture),
        fixture.initiatives,
        fixture.community,
        fixture.actions,
    )
    assert first == second
    assert fixture.community.model_dump(mode="json") == base_before
    assert [initiative.model_dump(mode="json") for initiative in fixture.initiatives] == initiatives_before
    assert [action.model_dump(mode="json") for action in fixture.actions] == actions_before
