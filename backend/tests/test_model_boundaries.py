from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.api_models import PlanRequest
from app.models import (
    ActionPreconditions,
    AddResourceQuantityEffect,
    CatalystAction,
    CommunityState,
    InitiativeBlueprint,
    MAX_STABLE_ID_LENGTH,
    OrganisationBlock,
    PersonBlock,
    ResourceBlock,
    ResourceRequirement,
    RoleRequirement,
    SpaceBlock,
    TimeSlot,
    VenueRequirement,
)


def _person(value: object) -> PersonBlock:
    return PersonBlock(
        id="PERSON",
        name="Person",
        organisation_id="ORG",
        available_slots={TimeSlot.SAT_10},
        max_contribution_slots=value,
    )


def _space(value: object) -> SpaceBlock:
    return SpaceBlock(
        id="SPACE",
        name="Space",
        organisation_id="ORG",
        capacity=value,
    )


def _resource_quantity(value: object) -> ResourceBlock:
    return ResourceBlock(
        id="RESOURCE",
        name="Resource",
        organisation_id="ORG",
        quantity=value,
        shareable=True,
    )


def _venue(value: object) -> VenueRequirement:
    return VenueRequirement(minimum_capacity=value)


def _resource_requirement(value: object) -> ResourceRequirement:
    return ResourceRequirement(resource_id="RESOURCE", quantity=value)


def _resource_effect(value: object) -> AddResourceQuantityEffect:
    return AddResourceQuantityEffect(
        type="add_resource_quantity",
        resource_id="RESOURCE",
        quantity=value,
    )


def _action(value: object) -> CatalystAction:
    return CatalystAction(
        id="ACTION",
        name="Action",
        cost=value,
        preconditions=ActionPreconditions(),
        effects=[_resource_effect(1)],
    )


def _initiative(value: object) -> InitiativeBlueprint:
    return InitiativeBlueprint(
        id="INITIATIVE",
        name="Initiative",
        venue=_venue(0),
        candidate_start_slots=[TimeSlot.SAT_10],
        duration_slots=value,
    )


def _resource_shareable(value: object) -> ResourceBlock:
    return ResourceBlock(
        id="RESOURCE",
        name="Resource",
        organisation_id="ORG",
        quantity=0,
        shareable=value,
    )


def _role_allow_shared(value: object) -> RoleRequirement:
    return RoleRequirement(id="ROLE", label="Role", allow_shared_person=value)


def _plan(value: object) -> PlanRequest:
    return PlanRequest(
        community=CommunityState(state_id="STATE"),
        initiative_id="INITIATIVE",
        actions=[_action(0)],
        max_depth=value,
    )


def test_stable_id_accepts_documented_maximum_length() -> None:
    identifier = "A" * MAX_STABLE_ID_LENGTH
    assert OrganisationBlock(id=identifier, name="Organisation").id == identifier


def test_stable_id_rejects_more_than_documented_maximum_length() -> None:
    with pytest.raises(ValidationError):
        OrganisationBlock(id="A" * (MAX_STABLE_ID_LENGTH + 1), name="Organisation")


@pytest.mark.parametrize(
    ("factory", "boundary"),
    [
        pytest.param(_person, 1, id="person-max-contribution-lower-bound"),
        pytest.param(_space, 0, id="space-capacity-lower-bound"),
        pytest.param(_resource_quantity, 0, id="resource-quantity-lower-bound"),
        pytest.param(_venue, 0, id="venue-capacity-lower-bound"),
        pytest.param(_resource_requirement, 1, id="resource-requirement-lower-bound"),
        pytest.param(_resource_effect, 1, id="resource-effect-lower-bound"),
        pytest.param(_action, 0, id="action-cost-lower-bound"),
        pytest.param(_initiative, 1, id="initiative-duration-lower-bound"),
        pytest.param(_initiative, len(TimeSlot), id="initiative-duration-upper-bound"),
    ],
)
def test_strict_integer_fields_preserve_valid_boundaries(
    factory: Callable[[object], Any], boundary: int
) -> None:
    factory(boundary)


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(_person, id="person-max-contribution"),
        pytest.param(_space, id="space-capacity"),
        pytest.param(_resource_quantity, id="resource-quantity"),
        pytest.param(_venue, id="venue-capacity"),
        pytest.param(_resource_requirement, id="resource-requirement"),
        pytest.param(_resource_effect, id="resource-effect"),
        pytest.param(_action, id="action-cost"),
        pytest.param(_initiative, id="initiative-duration"),
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(1.0, id="float"),
        pytest.param("1", id="string"),
        pytest.param(True, id="boolean"),
    ],
)
def test_strict_integer_fields_reject_coercible_values(
    factory: Callable[[object], Any], invalid_value: object
) -> None:
    with pytest.raises(ValidationError):
        factory(invalid_value)


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(_resource_shareable, id="resource-shareable"),
        pytest.param(_role_allow_shared, id="role-allow-shared-person"),
    ],
)
@pytest.mark.parametrize("boundary", [False, True])
def test_strict_boolean_fields_preserve_boolean_values(
    factory: Callable[[object], Any], boundary: bool
) -> None:
    assert factory(boundary)


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(_resource_shareable, id="resource-shareable"),
        pytest.param(_role_allow_shared, id="role-allow-shared-person"),
    ],
)
@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(0, id="zero"),
        pytest.param(1, id="one"),
        pytest.param("true", id="true-string"),
        pytest.param("false", id="false-string"),
    ],
)
def test_strict_boolean_fields_reject_coercible_values(
    factory: Callable[[object], Any], invalid_value: object
) -> None:
    with pytest.raises(ValidationError):
        factory(invalid_value)


def test_plan_depth_preserves_exact_literal() -> None:
    assert _plan(2).max_depth == 2


def test_plan_depth_preserves_default() -> None:
    request = PlanRequest(
        community=CommunityState(state_id="STATE"),
        initiative_id="INITIATIVE",
        actions=[_action(0)],
    )
    assert request.max_depth == 2


@pytest.mark.parametrize(
    "invalid_value",
    [
        pytest.param(2.0, id="float"),
        pytest.param("2", id="string"),
        pytest.param(True, id="boolean"),
    ],
)
def test_plan_depth_rejects_coercible_literal_values(invalid_value: object) -> None:
    with pytest.raises(ValidationError):
        _plan(invalid_value)
