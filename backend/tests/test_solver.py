from __future__ import annotations

from itertools import combinations

import pytest

from app.compiler import REQUIREMENT_GROUPS, ROLE_CAPABILITY, compile_initiative
from app.fixture import fresh_demo_fixture
from app.errors import AnalyserContractError
from app.solver import (
    build_compile_summary,
    replay_assignment,
    solve_initiative,
    validate_analysis_witness,
)
from app.api_models import SolverStatus
from app.models import TimeSlot


def _initiative(fixture, initiative_id: str):
    return next(item for item in fixture.initiatives if item.id == initiative_id)


def _training_state():
    fixture = fresh_demo_fixture()
    for person in fixture.community.people:
        if person.id in {"PRIYA", "SAM"}:
            person.capabilities.add("digital_support")
    return fixture


def test_basic_workshop_is_genuinely_optimal_and_replays() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")

    compiled = compile_initiative(fixture.community, initiative)
    result = solve_initiative(compiled)

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == 24
    assert [(item.role_instance_id, item.person_id) for item in result.assignments] == [
        ("DIGITAL_HELPER", "LEO"),
        ("FACILITATOR", "SAM"),
    ]
    assert {entry.requirement_kind for entry in result.assembly_trace} == {
        "role", "venue", "resource", "time"
    }
    assert compiled.decision_variables == len(compiled.model.Proto().variables)
    assert compiled.hard_constraints == len(compiled.model.Proto().constraints)
    assert replay_assignment(fixture.community, initiative, result)
    assert validate_analysis_witness(fixture.community, initiative, result)


@pytest.mark.parametrize(
    "mutation",
    [
        "invalid_start",
        "fabricated_facts",
        "objective",
        "duplicate_assignment",
        "missing_assignment",
        "duplicate_trace",
        "missing_trace",
        "extra_trace",
    ],
)
def test_canonical_witness_rejects_adversarial_decoded_results(mutation: str) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    result = solve_initiative(fixture.community, initiative).model_copy(deep=True)

    if mutation == "invalid_start":
        time_entry = next(entry for entry in result.assembly_trace if entry.requirement_kind == "time")
        time_entry.selected_ids = ["SAT_10"]
        time_entry.facts = {
            "start_slot": "SAT_10",
            "occupied_slots": ["SAT_10", "SAT_11"],
            "duration_slots": 2,
        }
    elif mutation == "fabricated_facts":
        result.assembly_trace[0].facts["label"] = "Fabricated role label"
    elif mutation == "objective":
        result.objective_value = 999
    elif mutation == "duplicate_assignment":
        result.assignments.append(result.assignments[0].model_copy(deep=True))
    elif mutation == "missing_assignment":
        result.assignments.pop()
    elif mutation == "duplicate_trace":
        result.assembly_trace.append(result.assembly_trace[0].model_copy(deep=True))
    elif mutation == "missing_trace":
        result.assembly_trace.pop()
    else:
        extra = result.assembly_trace[0].model_copy(deep=True)
        extra.requirement_id = "EXTRA_ROLE"
        result.assembly_trace.append(extra)

    assert not replay_assignment(fixture.community, initiative, result)
    assert not validate_analysis_witness(fixture.community, initiative, result)


def test_solve_compiled_raises_contract_error_when_decoded_witness_is_invalid(monkeypatch) -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    monkeypatch.setattr("app.solver._objective_value", lambda _: 999)

    with pytest.raises(AnalyserContractError, match="canonical replay"):
        solve_initiative(fixture.community, initiative)


def test_initial_clinic_and_repair_share_are_infeasible() -> None:
    fixture = fresh_demo_fixture()

    clinic = solve_initiative(fixture.community, _initiative(fixture, "MULTILINGUAL_CLINIC"))
    repair = solve_initiative(fixture.community, _initiative(fixture, "REPAIR_SHARE"))

    assert clinic.status is SolverStatus.INFEASIBLE
    assert clinic.assignments == []
    assert repair.status is SolverStatus.INFEASIBLE
    assert repair.assignments == []


def test_training_state_makes_clinic_buildable() -> None:
    fixture = _training_state()
    result = solve_initiative(
        fixture.community,
        _initiative(fixture, "MULTILINGUAL_CLINIC"),
    )

    assert result.status is SolverStatus.OPTIMAL
    assert result.objective_value == 48
    assert {item.person_id for item in result.assignments} == {
        "LEO", "PRIYA", "SAM", "AMIRA"
    }
    assert replay_assignment(
        fixture.community,
        _initiative(fixture, "MULTILINGUAL_CLINIC"),
        result,
    )


def test_capability_mutation_is_caught_by_cp_sat() -> None:
    fixture = fresh_demo_fixture()
    leo = next(person for person in fixture.community.people if person.id == "LEO")
    leo.capabilities.remove("digital_support")

    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))

    assert result.status is SolverStatus.INFEASIBLE


def test_resource_quantity_and_availability_mutations_are_caught() -> None:
    fixture = fresh_demo_fixture()
    laptops = next(resource for resource in fixture.community.resources if resource.id == "LIBRARY_LAPTOPS")
    laptops.quantity = 3
    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    assert result.status is SolverStatus.INFEASIBLE

    fixture = fresh_demo_fixture()
    laptops = next(resource for resource in fixture.community.resources if resource.id == "LIBRARY_LAPTOPS")
    laptops.available_slots.remove(TimeSlot.SAT_12)
    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    assert result.status is SolverStatus.INFEASIBLE


@pytest.mark.parametrize(
    ("relaxed_groups", "expected_status"),
    [
        (frozenset(), SolverStatus.INFEASIBLE),
        ({"resource_quantity"}, SolverStatus.INFEASIBLE),
        ({"availability"}, SolverStatus.OPTIMAL),
        ({"resource_quantity", "availability"}, SolverStatus.OPTIMAL),
    ],
)
def test_resource_quantity_relaxation_does_not_leak_into_availability(
    relaxed_groups: set[str] | frozenset[str],
    expected_status: SolverStatus,
) -> None:
    fixture = fresh_demo_fixture()
    laptops = next(
        resource
        for resource in fixture.community.resources
        if resource.id == "LIBRARY_LAPTOPS"
    )
    assert laptops.quantity >= 4
    laptops.available_slots.remove(TimeSlot.SAT_12)

    result = solve_initiative(
        fixture.community,
        _initiative(fixture, "BASIC_WORKSHOP"),
        relax_groups=relaxed_groups,
    )

    assert result.status is expected_status


MISSING_RESOURCE_RELAXATIONS = [
    frozenset(),
    *(frozenset({group}) for group in sorted(REQUIREMENT_GROUPS)),
    *(frozenset(pair) for pair in combinations(sorted(REQUIREMENT_GROUPS), 2)),
]


@pytest.mark.parametrize(
    "relaxed_groups",
    MISSING_RESOURCE_RELAXATIONS,
    ids=lambda groups: "+".join(sorted(groups)) or "strict",
)
def test_missing_resource_reference_is_never_relaxable(
    relaxed_groups: frozenset[str],
) -> None:
    fixture = fresh_demo_fixture()
    fixture.community.resources = [
        resource
        for resource in fixture.community.resources
        if resource.id != "LIBRARY_LAPTOPS"
    ]

    result = solve_initiative(
        fixture.community,
        _initiative(fixture, "BASIC_WORKSHOP"),
        relax_groups=relaxed_groups,
    )

    assert result.status is SolverStatus.INFEASIBLE


def test_venue_accessibility_availability_and_contribution_mutations_are_caught() -> None:
    fixture = fresh_demo_fixture()
    room = fixture.community.spaces[0]
    room.features.remove("wheelchair_accessible")
    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    assert result.status is SolverStatus.INFEASIBLE

    fixture = fresh_demo_fixture()
    sam = next(person for person in fixture.community.people if person.id == "SAM")
    sam.available_slots.remove(TimeSlot.SAT_12)
    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    assert result.status is SolverStatus.INFEASIBLE

    fixture = fresh_demo_fixture()
    leo = next(person for person in fixture.community.people if person.id == "LEO")
    leo.max_contribution_slots = 1
    result = solve_initiative(fixture.community, _initiative(fixture, "BASIC_WORKSHOP"))
    assert result.status is SolverStatus.INFEASIBLE


def test_relaxation_is_explicit_and_unknown_is_preserved() -> None:
    fixture = fresh_demo_fixture()
    initiative = _initiative(fixture, "BASIC_WORKSHOP")
    leo = next(person for person in fixture.community.people if person.id == "LEO")
    leo.capabilities.remove("digital_support")

    strict = solve_initiative(fixture.community, initiative)
    relaxed = solve_initiative(
        fixture.community,
        initiative,
        relax_groups={ROLE_CAPABILITY},
    )
    assert strict.status is SolverStatus.INFEASIBLE
    assert relaxed.status is SolverStatus.OPTIMAL

    unknown = solve_initiative(
        fresh_demo_fixture().community,
        initiative,
        time_limit_seconds=0,
    )
    assert unknown.status is SolverStatus.UNKNOWN
    assert unknown.assignments == []
    assert unknown.objective_value is None


def test_compile_summary_contains_real_generated_counts() -> None:
    fixture = fresh_demo_fixture()
    summary = build_compile_summary(
        fixture.community,
        [
            _initiative(fixture, "BASIC_WORKSHOP"),
            _initiative(fixture, "MULTILINGUAL_CLINIC"),
        ],
    )
    assert summary.people == 5
    assert summary.organisations == 4
    assert summary.spaces == 1
    assert summary.resources == 2
    assert summary.decision_variables > 0
    assert summary.hard_constraints > 0
