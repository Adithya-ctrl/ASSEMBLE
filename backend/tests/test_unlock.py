from __future__ import annotations

from collections.abc import Collection

from app.api_models import RequirementGroup
from app.fixture import fresh_demo_fixture
from app.interventions import apply_action, find_minimum_unlock, transition_state
from app.models import CommunityState, InitiativeBlueprint


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


def test_training_is_cheapest_complete_unlock_and_catalogue_paths_are_exhaustive() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")

    response = find_minimum_unlock(fixture.community, clinic, fixture.actions, _clinic_analyser)

    assert response.interventions == ["TRAIN_DIGITAL_HELPERS"]
    assert response.total_cost == 2
    assert response.catalogue_size == 4
    assert response.candidate_paths_evaluated == 16
    assert response.resulting_status == "OPTIMAL"


def test_borrowing_laptops_alone_does_not_solve_and_transition_is_immutable() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")
    training = next(action for action in fixture.actions if action.id == "TRAIN_DIGITAL_HELPERS")
    borrowing = next(action for action in fixture.actions if action.id == "BORROW_TWO_LAPTOPS")

    borrowed, _ = apply_action(fixture.community, borrowing)
    assert _clinic_analyser(borrowed, clinic)["status"] == "INFEASIBLE"
    assert fixture.community.resources[0].quantity == 6

    transition = transition_state(fixture.community, training)
    assert transition.predecessor_state_id == "S0"
    assert transition.successor_state.parent_state_id == "S0"
    assert transition.diff.added_capabilities == {
        "PRIYA": ["digital_support"],
        "SAM": ["digital_support"],
    }
    assert "digital_support" not in fixture.community.people[1].capabilities
    assert transition.successor_state.state_id.startswith("S")
