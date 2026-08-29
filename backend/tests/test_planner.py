from __future__ import annotations

from collections.abc import Collection

import pytest

from app.api_models import RequirementGroup
from app.fixture import fresh_demo_fixture
from app.interventions import apply_action, find_minimum_unlock
from app.models import CatalystAction, CommunityState, InitiativeBlueprint
from app.planner import NoPlanFound, plan_catalyst


def _clinic_analyser(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Collection[RequirementGroup] = (),
) -> dict[str, str]:
    del initiative, relaxed_groups
    helpers = sum("digital_support" in person.capabilities for person in community.people)
    laptops = next(resource.quantity for resource in community.resources if resource.id == "LIBRARY_LAPTOPS")
    return {"status": "OPTIMAL" if helpers >= 3 and laptops >= 5 else "INFEASIBLE"}


def test_depth_two_planner_prefers_training_and_records_hash_states() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")

    response = plan_catalyst(fixture.community, clinic, fixture.actions, _clinic_analyser)

    assert response.path == ["TRAIN_DIGITAL_HELPERS"]
    assert response.total_cost == 2
    assert response.states[0] == "S0"
    assert len(response.states) == 2
    assert response.target_status_before == "INFEASIBLE"
    assert response.target_status_after == "OPTIMAL"
    assert 1 <= len(response.nodes) <= 20


def test_expansion_cap_is_hard() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")

    with pytest.raises(NoPlanFound):
        plan_catalyst(
            fixture.community,
            clinic,
            fixture.actions,
            _clinic_analyser,
            max_expanded_states=1,
        )


def test_state_successor_can_be_replayed_without_changing_predecessor() -> None:
    fixture = fresh_demo_fixture()
    training = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")

    first, _ = apply_action(fixture.community, training)
    second, _ = apply_action(fixture.community, training)
    assert first.state_id == second.state_id
    assert fixture.community.state_id == "S0"


def test_unlock_and_planner_agree_on_executable_dependent_action_order() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")
    train_dependency = CatalystAction.model_validate(
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
    add_resource = CatalystAction.model_validate(
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
    fillers = [
        action
        for action in fixture.actions
        if action.id in {"RECRUIT_HELPER_A", "RECRUIT_HELPER_B"}
    ]
    catalogue = [add_resource, train_dependency, *fillers]

    def dependent_analyser(
        community: CommunityState,
        initiative: InitiativeBlueprint,
        *,
        relaxed_groups: Collection[RequirementGroup] = (),
    ) -> dict[str, str]:
        del initiative, relaxed_groups
        priya = next(person for person in community.people if person.id == "PRIYA")
        laptops = next(
            resource.quantity
            for resource in community.resources
            if resource.id == "LIBRARY_LAPTOPS"
        )
        ready = "resource_access" in priya.capabilities and laptops >= 7
        return {"status": "OPTIMAL" if ready else "INFEASIBLE"}

    unlock = find_minimum_unlock(fixture.community, clinic, catalogue, dependent_analyser)
    plan = plan_catalyst(fixture.community, clinic, catalogue, dependent_analyser)

    assert unlock.candidate_paths_evaluated == 16
    assert unlock.interventions == ["Z_TRAIN", "A_RESOURCE"]
    assert plan.path == unlock.interventions
    assert len(plan.states) == 3
