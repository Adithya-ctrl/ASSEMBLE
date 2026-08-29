"""Set D: independent explanation group/pair/time/resource matrices."""

from __future__ import annotations

from collections.abc import Collection, Callable
import pytest

from app.api_models import RequirementGroup, SolverStatus
from app.errors import AnalyserContractError
from app.explain import explain_infeasibility
from app.models import TimeSlot
from app.solver import solve_initiative

from .support import (
    _role_status,
    explanation_fixtures,
    status_for,
    witness_fixture,
)


def _recording_independent_analyser(calls: list[frozenset[RequirementGroup]]) -> Callable[..., object]:
    def analyser(community, initiative, *, relaxed_groups: Collection[RequirementGroup] = ()):
        relaxed = frozenset(relaxed_groups)
        calls.append(relaxed)
        return status_for(community, initiative, relaxed)

    return analyser


@pytest.mark.parametrize(
    "group",
    tuple(explanation_fixtures()),
    ids=lambda group: group.value,
)
def test_each_requirement_group_has_truthful_independent_singleton_blocker(
    group: RequirementGroup,
) -> None:
    community, initiative, expected_fact = explanation_fixtures()[group]
    assert not _role_status(community, initiative)
    assert _role_status(community, initiative, {group})
    assert all(
        not _role_status(community, initiative, {other})
        for other in RequirementGroup
        if other is not group
    )

    calls: list[frozenset[RequirementGroup]] = []
    response = explain_infeasibility(
        community,
        initiative,
        _recording_independent_analyser(calls),
    )
    assert response.initiative_id == initiative.id
    assert response.status is SolverStatus.INFEASIBLE
    assert response.method == "bounded_relax_and_resolve"
    assert response.blocking_requirement_sets
    assert [list(item.groups) for item in response.blocking_requirement_sets] == [[group]]
    blocking = response.blocking_requirement_sets[0]
    assert blocking.restored_feasibility_when_relaxed is True
    fact = next(
        fact for fact in blocking.facts
        if (
            expected_fact.get("capability") is not None
            and fact.capability == expected_fact["capability"]
        )
        or (
            expected_fact.get("language") is not None
            and fact.language == expected_fact["language"]
        )
        or (
            expected_fact.get("requirement_id") is not None
            and fact.requirement_id == expected_fact["requirement_id"]
        )
        or (
            expected_fact.get("capability") is None
            and expected_fact.get("language") is None
            and expected_fact.get("requirement_id") is None
        )
    )
    for key, value in expected_fact.items():
        assert getattr(fact, key) == value, (group, key, fact)

    expected_group_count = 7
    # The engine makes one baseline call and one bounded singleton call for
    # every group that has inventory facts, then stops before pair search once
    # a singleton restores feasibility.
    assert response.solver_runs == expected_group_count + 1
    assert len(calls) == response.solver_runs
    assert calls[0] == frozenset()
    assert frozenset({group}) in calls
    assert response == explain_infeasibility(
        community,
        initiative,
        _recording_independent_analyser([]),
    )


def test_pair_interaction_surfaces_both_facts_without_false_singleton() -> None:
    community, initiative = witness_fixture()
    community.people[0].capabilities.remove("host")
    community.resources[0].quantity = 1
    expected_pair = (RequirementGroup.ROLE_CAPABILITY, RequirementGroup.RESOURCE_QUANTITY)
    assert not _role_status(community, initiative)
    assert not _role_status(community, initiative, {RequirementGroup.ROLE_CAPABILITY})
    assert not _role_status(community, initiative, {RequirementGroup.RESOURCE_QUANTITY})
    assert _role_status(community, initiative, set(expected_pair))

    calls: list[frozenset[RequirementGroup]] = []
    response = explain_infeasibility(
        community,
        initiative,
        _recording_independent_analyser(calls),
    )
    assert response.status is SolverStatus.INFEASIBLE
    assert [tuple(item.groups) for item in response.blocking_requirement_sets] == [expected_pair]
    assert all(len(item.groups) == 2 for item in response.blocking_requirement_sets)
    facts = response.blocking_requirement_sets[0].facts
    assert {(fact.capability, fact.requirement_id, fact.required, fact.available) for fact in facts} >= {
        ("host", None, 1, 0),
        (None, "KIT", 2, 1),
    }
    assert all(
        not (len(item.groups) == 1 and item.restored_feasibility_when_relaxed)
        for item in response.blocking_requirement_sets
    )
    # Seven groups have facts in this fixture: baseline + seven singleton + all
    # 21 pairs.  This exact count documents the bounded interaction search.
    assert response.solver_runs == 29
    assert len(calls) == 29


def test_time_intersection_is_availability_not_a_false_skill_or_capacity_blocker() -> None:
    community, initiative = witness_fixture()
    community.people[0].available_slots = {TimeSlot.SAT_10}
    community.spaces[0].available_slots = {TimeSlot.SAT_11}
    community.resources[0].available_slots = {TimeSlot.SAT_10, TimeSlot.SAT_11}
    initiative.candidate_start_slots = [TimeSlot.SAT_10, TimeSlot.SAT_11]
    initiative.duration_slots = 1
    assert not _role_status(community, initiative)
    assert _role_status(community, initiative, {RequirementGroup.AVAILABILITY})
    assert not _role_status(community, initiative, {RequirementGroup.ROLE_CAPABILITY})

    response = explain_infeasibility(
        community,
        initiative,
        _recording_independent_analyser([]),
    )
    assert response.status is SolverStatus.INFEASIBLE
    assert [list(item.groups) for item in response.blocking_requirement_sets] == [
        [RequirementGroup.AVAILABILITY]
    ]
    assert all(
        RequirementGroup.ROLE_CAPABILITY not in item.groups
        and RequirementGroup.VENUE_CAPACITY not in item.groups
        for item in response.blocking_requirement_sets
    )
    # Each inventory item is individually available for some start, so the
    # evidence must retain all three facts rather than inventing a skill gap.
    facts = response.blocking_requirement_sets[0].facts
    assert {fact.requirement_id for fact in facts} >= {"HOST", "venue", "KIT"}
    assert all(fact.required == fact.available == 1 for fact in facts)


def test_missing_resource_reference_remains_integrity_failure_under_quantity_and_availability_relaxations() -> None:
    community, initiative = witness_fixture()
    community.resources.clear()
    calls: list[frozenset[RequirementGroup]] = []
    response = explain_infeasibility(
        community,
        initiative,
        _recording_independent_analyser(calls),
    )
    assert response.status is SolverStatus.INFEASIBLE
    assert response.blocking_requirement_sets == []
    assert not _role_status(
        community,
        initiative,
        {RequirementGroup.RESOURCE_QUANTITY, RequirementGroup.AVAILABILITY},
    )
    assert frozenset({RequirementGroup.RESOURCE_QUANTITY, RequirementGroup.AVAILABILITY}) in calls
    assert all(
        not ({RequirementGroup.RESOURCE_QUANTITY, RequirementGroup.AVAILABILITY}.issubset(call))
        or status_for(community, initiative, call)["status"] == SolverStatus.INFEASIBLE.value
        for call in calls
    )


def _malicious_analyser_cases():
    community, initiative = witness_fixture()
    valid = solve_initiative(community, initiative)

    def mutates_community(c, _i, **_kwargs):
        c.people[0].name = "MUTATED"
        return {"status": "OPTIMAL"}

    def mutates_initiative(_c, i, **_kwargs):
        i.name = "MUTATED"
        return {"status": "OPTIMAL"}

    def feasible_after_corrupting_copy(c, _i, **_kwargs):
        damaged = c.model_copy(deep=True)
        damaged.people.clear()
        return {"status": "OPTIMAL"}

    def mismatched_initiative(_c, i, **_kwargs):
        mismatched = valid.model_copy(deep=True)
        mismatched.initiative_id = "OTHER_INITIATIVE"
        return mismatched

    def duplicate_assignments(_c, _i, **_kwargs):
        malformed = valid.model_copy(deep=True)
        malformed.assignments.append(malformed.assignments[0].model_copy(deep=True))
        return malformed

    def malformed_trace(_c, _i, **_kwargs):
        malformed = valid.model_copy(deep=True)
        malformed.assembly_trace.pop()
        return malformed

    def feasible_without_witness(_c, _i, **_kwargs):
        return {"status": "FEASIBLE"}

    def infeasible_with_witness(_c, _i, **_kwargs):
        return {
            "status": "INFEASIBLE",
            "assignments": [{"role_instance_id": "HOST", "person_id": "ALICE"}],
        }

    def unknown_with_objective(_c, _i, **_kwargs):
        return {"status": "UNKNOWN", "objective_value": 12}

    return community, initiative, (
        ("mutates_community", mutates_community),
        ("mutates_initiative", mutates_initiative),
        ("feasible_after_corrupting_copy", feasible_after_corrupting_copy),
        ("mismatched_initiative", mismatched_initiative),
        ("duplicate_assignments", duplicate_assignments),
        ("malformed_trace", malformed_trace),
        ("feasible_without_witness", feasible_without_witness),
        ("infeasible_with_witness", infeasible_with_witness),
        ("unknown_with_objective", unknown_with_objective),
    )


@pytest.mark.parametrize(
    "name,index",
    [
        (name, index)
        for index, (name, _) in enumerate(_malicious_analyser_cases()[2])
        if name not in {"feasible_after_corrupting_copy", "feasible_without_witness"}
    ],
)
def test_malicious_or_malformed_analyser_fails_closed(name: str, index: int) -> None:
    community, initiative, cases = _malicious_analyser_cases()
    _, analyser = cases[index]
    with pytest.raises(AnalyserContractError):
        explain_infeasibility(community, initiative, analyser)


@pytest.mark.parametrize(
    "name,index,expected_status",
    (
        ("feasible_after_corrupting_copy", 2, SolverStatus.OPTIMAL),
        ("feasible_without_witness", 6, SolverStatus.FEASIBLE),
    ),
)
def test_exact_status_only_analyser_seam_remains_supported(
    name: str,
    index: int,
    expected_status: SolverStatus,
) -> None:
    community, initiative, cases = _malicious_analyser_cases()
    selected_name, analyser = cases[index]
    assert selected_name == name
    community_before = community.model_dump(mode="json")
    initiative_before = initiative.model_dump(mode="json")

    response = explain_infeasibility(community, initiative, analyser)

    assert response.status is expected_status
    assert response.initiative_id == initiative.id
    assert response.blocking_requirement_sets == []
    assert response.solver_runs == 1
    assert community.model_dump(mode="json") == community_before
    assert initiative.model_dump(mode="json") == initiative_before
