"""Set C: complete canonical-witness mutation catalogue.

Every case changes one named semantic fact in an otherwise genuine feasible
receipt.  The expected rejection is calculated by a small local oracle rather
than by calling the product validator and the product validator is exercised
only as the system under test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.api_models import AssemblyTraceEntry
from app.solver import replay_assignment, solve_initiative, validate_analysis_witness
from app.models import CommunityState, InitiativeBlueprint, TimeSlot

from .support import independent_witness_legal, witness_fixture


@dataclass(frozen=True)
class WitnessMutation:
    name: str
    semantic_fact: str
    mutate: Callable[[CommunityState, InitiativeBlueprint, Any], None]


def _trace(result: Any, kind: str) -> Any:
    return next(entry for entry in result.assembly_trace if entry.requirement_kind == kind)


def _wrong_initiative(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.initiative_id = "OTHER_INITIATIVE"


def _missing_role(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assignments.pop()


def _duplicate_role(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assignments.append(result.assignments[0].model_copy(deep=True))


def _wrong_person(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assignments[0].person_id = "BOB"


def _person_lacks_capability(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.people[0].capabilities.remove("host")


def _person_lacks_language(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.people[0].languages.remove("ar")


def _person_unavailable(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.people[0].available_slots.remove(TimeSlot.SAT_10)


def _contribution_exceeded(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.people[0].max_contribution_slots = 1


def _wrong_venue(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "venue").selected_ids = ["ROOM_BAD"]


def _venue_too_small(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.spaces[0].capacity = 7


def _venue_missing_feature(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.spaces[0].features.remove("power")


def _venue_unavailable(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.spaces[0].available_slots.remove(TimeSlot.SAT_10)


def _wrong_start(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    # Only the selected start identifier changes; the stale presentation facts
    # are intentionally left untouched so this remains one fact mutation.
    _trace(result, "time").selected_ids = ["SAT_11"]


def _wrong_occupied_slots(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "time").facts["occupied_slots"] = ["SAT_10"]


def _wrong_duration(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "time").facts["duration_slots"] = 1


def _resource_missing(community: CommunityState, __: InitiativeBlueprint, _: Any) -> None:
    community.resources.clear()


def _wrong_quantity_evidence(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "resource").facts["quantity_available"] = 3


def _wrong_shareable_fact(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "resource").facts["shareable"] = False


def _fake_objective(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.objective_value = int(result.objective_value) + 1


def _wrong_trace_selected_id(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    _trace(result, "role").selected_ids = ["BOB"]


def _duplicated_trace_entry(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assembly_trace.append(_trace(result, "role").model_copy(deep=True))


def _missing_time_trace(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assembly_trace = [
        entry for entry in result.assembly_trace if entry.requirement_kind != "time"
    ]


def _extra_unexpected_trace(_: CommunityState, __: InitiativeBlueprint, result: Any) -> None:
    result.assembly_trace.append(
        AssemblyTraceEntry(
            requirement_kind="role",
            requirement_id="EXTRA_ROLE",
            selected_ids=["ALICE"],
            facts={},
        )
    )


MUTATIONS = (
    WitnessMutation("wrong_initiative_id", "result.initiative_id", _wrong_initiative),
    WitnessMutation("missing_role", "result.assignments", _missing_role),
    WitnessMutation("duplicate_role", "result.assignments", _duplicate_role),
    WitnessMutation("wrong_person", "result.assignments", _wrong_person),
    WitnessMutation("person_lacks_capability", "community.person[ALICE].capabilities", _person_lacks_capability),
    WitnessMutation("person_lacks_language", "community.person[ALICE].languages", _person_lacks_language),
    WitnessMutation("person_unavailable", "community.person[ALICE].available_slots", _person_unavailable),
    WitnessMutation("contribution_exceeded", "community.person[ALICE].max_contribution_slots", _contribution_exceeded),
    WitnessMutation("wrong_venue", "result.venue.selected_ids", _wrong_venue),
    WitnessMutation("venue_too_small", "community.space[ROOM_GOOD].capacity", _venue_too_small),
    WitnessMutation("venue_missing_feature", "community.space[ROOM_GOOD].features", _venue_missing_feature),
    WitnessMutation("venue_unavailable", "community.space[ROOM_GOOD].available_slots", _venue_unavailable),
    WitnessMutation("wrong_start", "result.time.selected_ids", _wrong_start),
    WitnessMutation("wrong_occupied_slots", "result.time.facts.occupied_slots", _wrong_occupied_slots),
    WitnessMutation("wrong_duration", "result.time.facts.duration_slots", _wrong_duration),
    WitnessMutation("resource_missing", "community.resource_catalogue", _resource_missing),
    WitnessMutation("wrong_quantity_evidence", "result.resource.facts.quantity_available", _wrong_quantity_evidence),
    WitnessMutation("wrong_shareable_fact", "result.resource.facts.shareable", _wrong_shareable_fact),
    WitnessMutation("fake_objective", "result.objective_value", _fake_objective),
    WitnessMutation("wrong_trace_selected_id", "result.role.selected_ids", _wrong_trace_selected_id),
    WitnessMutation("duplicated_trace_entry", "result.assembly_trace.structure", _duplicated_trace_entry),
    WitnessMutation("missing_time_trace", "result.assembly_trace.structure", _missing_time_trace),
    WitnessMutation("extra_unexpected_trace", "result.assembly_trace.structure", _extra_unexpected_trace),
)


def _fact_projection(community: CommunityState, initiative: InitiativeBlueprint, result: Any) -> dict[str, Any]:
    """Project all canonical facts into independently named semantic fields."""

    projection: dict[str, Any] = {
        "result.initiative_id": result.initiative_id,
        "result.objective_value": result.objective_value,
        "result.assignments": tuple(
            (item.role_instance_id, item.person_id) for item in result.assignments
        ),
        "result.assembly_trace.structure": tuple(
            (entry.requirement_kind, entry.requirement_id)
            for entry in result.assembly_trace
        ),
    }
    for person in community.people:
        projection[f"community.person[{person.id}].capabilities"] = tuple(sorted(person.capabilities))
        projection[f"community.person[{person.id}].languages"] = tuple(sorted(person.languages))
        projection[f"community.person[{person.id}].available_slots"] = tuple(
            sorted(slot.value for slot in person.available_slots)
        )
        projection[f"community.person[{person.id}].max_contribution_slots"] = person.max_contribution_slots
    for space in community.spaces:
        projection[f"community.space[{space.id}].capacity"] = space.capacity
        projection[f"community.space[{space.id}].features"] = tuple(sorted(space.features))
        projection[f"community.space[{space.id}].available_slots"] = tuple(
            sorted(slot.value for slot in space.available_slots)
        )
    projection["community.resource_catalogue"] = tuple(
        (
            resource.id,
            resource.quantity,
            tuple(sorted(slot.value for slot in resource.available_slots)),
            resource.shareable,
        )
        for resource in community.resources
    )
    for entry in result.assembly_trace:
        prefix = f"result.{entry.requirement_kind}"
        projection[f"{prefix}.selected_ids"] = tuple(entry.selected_ids)
        for key, value in sorted(entry.facts.items()):
            if isinstance(value, list):
                value = tuple(value)
            projection[f"{prefix}.facts.{key}"] = value
    # ``initiative`` is included in the signature so callers cannot accidentally
    # project a receipt against a different blueprint without an obvious API.
    projection["initiative.id"] = initiative.id
    return projection


def test_catalogue_is_complete_and_independently_described() -> None:
    expected_names = {
        "wrong_initiative_id",
        "missing_role",
        "duplicate_role",
        "wrong_person",
        "person_lacks_capability",
        "person_lacks_language",
        "person_unavailable",
        "contribution_exceeded",
        "wrong_venue",
        "venue_too_small",
        "venue_missing_feature",
        "venue_unavailable",
        "wrong_start",
        "wrong_occupied_slots",
        "wrong_duration",
        "resource_missing",
        "wrong_quantity_evidence",
        "wrong_shareable_fact",
        "fake_objective",
        "wrong_trace_selected_id",
        "duplicated_trace_entry",
        "missing_time_trace",
        "extra_unexpected_trace",
    }
    assert len(MUTATIONS) == 23
    assert {item.name for item in MUTATIONS} == expected_names
    assert {item.semantic_fact for item in MUTATIONS}


def test_every_single_fact_mutation_is_independently_expected_to_fail_replay() -> None:
    community, initiative = witness_fixture()
    baseline = solve_initiative(community, initiative)
    assert baseline.status.value in {"OPTIMAL", "FEASIBLE"}
    assert independent_witness_legal(community, initiative, baseline)
    assert validate_analysis_witness(community, initiative, baseline)

    baseline_facts = _fact_projection(community, initiative, baseline)
    for mutation in MUTATIONS:
        mutated_community = community.model_copy(deep=True)
        mutated_initiative = initiative.model_copy(deep=True)
        mutated_result = baseline.model_copy(deep=True)
        mutation.mutate(mutated_community, mutated_initiative, mutated_result)

        changed = {
            key
            for key, before in baseline_facts.items()
            if _fact_projection(mutated_community, mutated_initiative, mutated_result).get(key) != before
        }
        # Removed catalogue entries have no corresponding post-mutation key;
        # include those missing keys in the same independent diff calculation.
        mutated_facts = _fact_projection(mutated_community, mutated_initiative, mutated_result)
        changed.update(set(baseline_facts) - set(mutated_facts))
        changed.update(set(mutated_facts) - set(baseline_facts))
        if "result.assembly_trace.structure" in changed:
            # Adding/removing one trace entry necessarily removes/adds that
            # entry's projected child fields.  Treat the collection structure
            # as the single semantic fact being mutated.
            changed = {"result.assembly_trace.structure"}
        assert changed == {mutation.semantic_fact}, (mutation.name, changed)

        # This expected answer is the local plain-Python oracle; it does not
        # call validate_analysis_witness, replay_assignment, or any compiler.
        assert not independent_witness_legal(
            mutated_community,
            mutated_initiative,
            mutated_result,
        ), mutation.name
        assert not validate_analysis_witness(
            mutated_community,
            mutated_initiative,
            mutated_result,
        ), mutation.name
        assert not replay_assignment(
            mutated_community,
            mutated_initiative,
            mutated_result,
        ), mutation.name


def test_solver_stats_are_presentation_only_and_cannot_mask_a_canonical_receipt() -> None:
    community, initiative = witness_fixture()
    baseline = solve_initiative(community, initiative)
    altered = baseline.model_copy(deep=True)
    altered.solver_stats.wall_time_seconds = altered.solver_stats.wall_time_seconds + 123.0
    assert _fact_projection(community, initiative, altered) == _fact_projection(
        community,
        initiative,
        baseline,
    )
    assert independent_witness_legal(community, initiative, altered)
    assert validate_analysis_witness(community, initiative, altered)
