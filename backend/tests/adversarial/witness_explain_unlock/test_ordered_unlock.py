"""Set E: independent ordered unlock/planner catalogue and state tests."""

from __future__ import annotations

from collections.abc import Collection

import pytest

from app.api_models import RequirementGroup
from app.interventions import (
    ActionAlreadyApplied,
    AlreadyFeasible,
    NoUnlockPath,
    apply_action,
    ordered_action_paths,
    find_minimum_unlock,
)
from app.models import AddCapabilityEffect, CatalystAction
from app.planner import NoPlanFound, plan_catalyst

from .support import (
    action,
    direct_target_action,
    independent_action_paths,
    independent_apply,
    independent_state_id,
    independent_target_status,
    irrelevant_action,
    planner_fixture,
    resource_action,
    training_action,
)


def _target_analyser(community, initiative, *, relaxed_groups: Collection[RequirementGroup] = ()):
    """Independent status oracle supplied to the product search routines."""

    return independent_target_status(community, initiative, relaxed=relaxed_groups)


def _ids(paths):
    return [tuple(action.id for action in path) for path in paths]


def test_dependency_order_is_executable_and_expected_by_independent_paths() -> None:
    community, initiative = planner_fixture()
    training = training_action()
    resource = resource_action()
    catalogue = [resource, training]

    expected = []
    for candidate in independent_action_paths(catalogue):
        current = community
        try:
            for item in candidate.actions:
                current = independent_apply(current, item)
        except ValueError:
            continue
        if independent_target_status(current, initiative)["status"] in {"OPTIMAL", "FEASIBLE"}:
            expected.append(candidate)
    assert [tuple(item.actions[i].id for i in range(len(item.actions))) for item in expected] == [
        ("Z_TRAIN", "A_RESOURCE")
    ]
    assert _ids(ordered_action_paths(catalogue)) == _ids(
        [item.actions for item in independent_action_paths(catalogue)]
    )

    unlocked = find_minimum_unlock(community, initiative, catalogue, _target_analyser)
    planned = plan_catalyst(community, initiative, catalogue, _target_analyser)
    assert unlocked.interventions == planned.path == ["Z_TRAIN", "A_RESOURCE"]
    assert unlocked.total_cost == planned.total_cost == 2
    assert unlocked.candidate_paths_evaluated == 4
    assert planned.target_status_before.value == "INFEASIBLE"
    assert planned.target_status_after.value == "OPTIMAL"


def test_cost_then_length_then_id_tuple_ranking_is_explicit() -> None:
    community, initiative = planner_fixture()
    initiative.resources = []
    prep = action(
        "B_PREP",
        cost=1,
        effects=[
            AddCapabilityEffect(type="add_capability", person_id="LEARNER", capability_id="prep")
        ],
    )
    finish = action(
        "C_FINISH",
        cost=1,
        person_capabilities=[("LEARNER", "prep")],
        effects=[
            AddCapabilityEffect(type="add_capability", person_id="LEARNER", capability_id="target")
        ],
    )
    direct = direct_target_action("A_DIRECT", cost=2)
    feasible = []
    for candidate in independent_action_paths([direct, prep, finish]):
        current = community
        try:
            for item in candidate.actions:
                current = independent_apply(current, item)
        except ValueError:
            continue
        if independent_target_status(current, initiative)["status"] in {"OPTIMAL", "FEASIBLE"}:
            feasible.append(candidate)
    expected = min(feasible, key=lambda candidate: candidate.key)
    assert expected.actions == (direct,)
    planned = plan_catalyst(
        community,
        initiative,
        [direct, prep, finish],
        _target_analyser,
    )
    assert planned.path == ["A_DIRECT"]

    alpha = direct_target_action("A_ALPHA", cost=2)
    beta = direct_target_action("B_BETA", cost=2)
    tied = plan_catalyst(community, initiative, [beta, alpha], _target_analyser)
    assert tied.path == ["A_ALPHA"]
    unlocked = find_minimum_unlock(community, initiative, [beta, alpha], _target_analyser)
    assert unlocked.interventions == ["A_ALPHA"]


def test_irrelevant_cheapest_action_does_not_count_as_unlock() -> None:
    community, initiative = planner_fixture()
    initiative.resources = []
    cheap = irrelevant_action()
    direct = direct_target_action("EXPENSIVE_TARGET", cost=2)
    catalogue = [cheap, direct]
    unlocked = find_minimum_unlock(community, initiative, catalogue, _target_analyser)
    planned = plan_catalyst(community, initiative, catalogue, _target_analyser)
    assert unlocked.interventions == planned.path == ["EXPENSIVE_TARGET"]
    assert unlocked.total_cost == planned.total_cost == 2


def test_already_feasible_target_has_no_fake_unlock_or_plan() -> None:
    community, initiative = planner_fixture()
    initiative.resources = []
    next(person for person in community.people if person.id == "LEARNER").capabilities.add("target")
    actions = [irrelevant_action(), direct_target_action()]
    with pytest.raises(AlreadyFeasible, match="already feasible"):
        find_minimum_unlock(community, initiative, actions, _target_analyser)
    with pytest.raises(NoPlanFound, match="already feasible"):
        plan_catalyst(community, initiative, actions, _target_analyser)


def test_no_path_is_bounded_and_returns_stable_errors() -> None:
    community, initiative = planner_fixture()
    initiative.resources = []
    actions = [irrelevant_action()]
    before = community.model_dump(mode="json")
    with pytest.raises(NoUnlockPath, match="no ordered intervention path"):
        find_minimum_unlock(community, initiative, actions, _target_analyser)
    with pytest.raises(NoPlanFound, match="no catalyst path"):
        plan_catalyst(community, initiative, actions, _target_analyser)
    assert community.model_dump(mode="json") == before


def test_noop_transition_is_rejected_and_never_becomes_a_second_successor() -> None:
    community, initiative = planner_fixture()
    training = training_action()
    successor, _ = apply_action(community, training)
    predecessor_snapshot = community.model_dump(mode="json")
    successor_snapshot = successor.model_dump(mode="json")
    with pytest.raises(ActionAlreadyApplied, match="no unapplied effects"):
        apply_action(successor, training)
    assert successor.model_dump(mode="json") == successor_snapshot
    assert community.model_dump(mode="json") == predecessor_snapshot
    with pytest.raises(NoUnlockPath):
        find_minimum_unlock(successor, initiative, [training], _target_analyser)
    with pytest.raises(NoPlanFound):
        plan_catalyst(successor, initiative, [training], _target_analyser)


def test_predecessor_is_byte_stable_across_every_executable_action_path() -> None:
    community, initiative = planner_fixture()
    del initiative
    actions = [training_action(), resource_action(), irrelevant_action()]
    before_community = community.model_dump(mode="json")
    for candidate in independent_action_paths(actions):
        current = community
        try:
            for item in candidate.actions:
                current, _ = apply_action(current, item)
        except (ActionAlreadyApplied, ValueError):
            continue
        assert current.state_id == independent_state_id(current)
        assert community.model_dump(mode="json") == before_community
    assert community.model_dump(mode="json") == before_community


def test_state_identity_is_content_deterministic_and_collision_resistant_for_changes() -> None:
    community, _ = planner_fixture()
    training = training_action()
    noise = irrelevant_action()
    first, _ = apply_action(community, training)
    repeated, _ = apply_action(community, training)
    assert first.state_id == repeated.state_id == independent_state_id(first)

    training_then_noise, _ = apply_action(first, noise)
    noise_then_training, _ = apply_action(community, noise)
    noise_then_training, _ = apply_action(noise_then_training, training)
    assert training_then_noise.state_id == noise_then_training.state_id
    assert training_then_noise.state_id == independent_state_id(training_then_noise)
    resource, _ = apply_action(first, resource_action())
    assert resource.state_id != first.state_id
    assert resource.state_id == independent_state_id(resource)


def test_maximum_action_catalogue_and_search_bounds_are_exhaustive_but_capped() -> None:
    community, initiative = planner_fixture()
    initiative.resources = []
    actions: list[CatalystAction] = []
    for index in range(32):
        identifier = f"A{index:02d}"
        capability = "target" if index == 0 else f"cap_{index:02d}"
        actions.append(
            action(
                identifier,
                cost=1,
                effects=[
                    AddCapabilityEffect(
                        type="add_capability",
                        person_id="LEARNER",
                        capability_id=capability,
                    )
                ],
            )
        )

    independent_candidates = independent_action_paths(actions)
    assert len(independent_candidates) == 32 + (32 * 31) == 1024
    assert len(ordered_action_paths(actions, max_depth=2)) == 1024
    unlocked = find_minimum_unlock(community, initiative, actions, _target_analyser)
    assert unlocked.catalogue_size == 32
    assert unlocked.candidate_paths_evaluated == 1024
    assert unlocked.interventions == ["A00"]

    planned = plan_catalyst(
        community,
        initiative,
        actions,
        _target_analyser,
        max_depth=2,
        max_expanded_states=20,
    )
    assert planned.path == ["A00"]
    assert len(planned.nodes) == 20
    assert len(planned.nodes) <= 20
    with pytest.raises(ValueError, match="max_depth"):
        ordered_action_paths(actions, max_depth=3)
    with pytest.raises(ValueError, match="max_depth"):
        ordered_action_paths(actions, max_depth=-1)
    with pytest.raises(ValueError, match="max_expanded_states"):
        plan_catalyst(community, initiative, actions, _target_analyser, max_expanded_states=0)
    with pytest.raises(ValueError, match="max_expanded_states"):
        plan_catalyst(community, initiative, actions, _target_analyser, max_expanded_states=21)
