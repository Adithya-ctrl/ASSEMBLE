from __future__ import annotations

from collections.abc import Collection

from app.api_models import RequirementGroup
from app.explain import explain_infeasibility, inventory_facts
from app.fixture import fresh_demo_fixture
from app.models import CommunityState, InitiativeBlueprint
from app.models import TimeSlot


def _clinic_analyser(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Collection[RequirementGroup] = (),
) -> dict[str, str]:
    """Faithful bounded stub: only named relaxed constraints are omitted."""

    relaxed = set(relaxed_groups)
    people = community.people
    has_helpers = sum("digital_support" in person.capabilities for person in people) >= 3
    has_arabic = any("ar" in person.languages for person in people)
    has_venue = any(
        {"wheelchair_accessible", "wifi", "power"}.issubset(space.features)
        for space in community.spaces
    )
    laptops = any(resource.id == "LIBRARY_LAPTOPS" and resource.quantity >= 5 for resource in community.resources)
    feasible = (
        RequirementGroup.ROLE_CAPABILITY in relaxed
        or has_helpers
    ) and (RequirementGroup.LANGUAGE in relaxed or has_arabic) and (
        RequirementGroup.VENUE_FEATURE in relaxed or has_venue
    ) and (RequirementGroup.RESOURCE_QUANTITY in relaxed or laptops)
    return {"status": "OPTIMAL" if feasible else "INFEASIBLE"}


def test_inventory_reports_clinic_helper_shortage_with_ids() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")

    facts = inventory_facts(fixture.community, clinic)
    helper = next(
        fact
        for fact in facts[RequirementGroup.ROLE_CAPABILITY]
        if fact.capability == "digital_support"
    )
    assert (helper.required, helper.available) == (3, 1)
    assert helper.relevant_ids == ["LEO"]


def test_explain_uses_solver_confirmed_singleton_and_not_laptop_relaxation() -> None:
    fixture = fresh_demo_fixture()
    clinic = next(item for item in fixture.initiatives if item.id == "MULTILINGUAL_CLINIC")

    response = explain_infeasibility(fixture.community, clinic, _clinic_analyser)

    assert response.status == "INFEASIBLE"
    assert response.method == "bounded_relax_and_resolve"
    assert response.solver_runs >= 2
    assert [group.value for group in response.blocking_requirement_sets[0].groups] == [
        "role_capability"
    ]
    assert all(
        "resource_quantity" not in {group.value for group in requirement_set.groups}
        for requirement_set in response.blocking_requirement_sets
    )


def test_availability_explanation_names_resource_and_missing_slot() -> None:
    fixture = fresh_demo_fixture()
    workshop = next(item for item in fixture.initiatives if item.id == "BASIC_WORKSHOP")
    laptops = next(
        resource
        for resource in fixture.community.resources
        if resource.id == "LIBRARY_LAPTOPS"
    )
    laptops.quantity = 6
    laptops.available_slots.remove(TimeSlot.SAT_12)

    response = explain_infeasibility(fixture.community, workshop)

    assert response.status == "INFEASIBLE"
    assert [group.value for group in response.blocking_requirement_sets[0].groups] == [
        "availability"
    ]
    resource_fact = next(
        fact
        for fact in response.blocking_requirement_sets[0].facts
        if fact.requirement_id == "LIBRARY_LAPTOPS"
    )
    assert (resource_fact.required, resource_fact.available) == (1, 0)
    assert resource_fact.relevant_ids == ["LIBRARY_LAPTOPS"]
    assert resource_fact.note is not None
    assert "SAT_12" in resource_fact.note
