"""Server-generated structural stress tests for assembled initiatives.

The stress engine deliberately keeps perturbations small and explicit.  A
baseline witness determines the complete catalogue, every scenario is an
immutable copy of the reconstructed source state, and every feasible solver
answer is replayed through the canonical witness validator before it can be
reported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app import api_models
from app.analysis_state import reconstruct_authoritative_state
from app.api_models import (
    BlockingFact,
    BlockingRequirementSet,
    InitiativeAnalysisResult,
    PerturbationOutcome,
    PerturbationType,
    RequirementGroup,
    ResourceAvailabilityPerturbation,
    SolverStatus,
    StressCriticality,
    StressTestRequest,
    StressTestResponse,
    PersonUnavailablePerturbation,
    VenueUnavailablePerturbation,
    MAX_PERTURBATIONS,
)
from app.errors import AnalyserContractError
from app.explain import AnalysisCallable, call_analyser, explain_infeasibility
from app.interventions import canonical_state_hash, canonical_state_payload
from app.models import (
    CommunityState,
    InitiativeBlueprint,
    PersonBlock,
    ResourceBlock,
    SpaceBlock,
    TimeSlot,
)
from app.solver import solve_initiative, validate_analysis_witness


PERTURBATION_NAMESPACE = "ASSEMBLE_STRESS_PERTURBATION_V1"
SCENARIO_NAMESPACE = "CF_STRESS_V1"


class BaselineNotFeasible(ValueError):
    """Raised when structural stress testing has no decisive baseline."""


class InvalidPerturbation(ValueError):
    """Raised when a perturbation is not a canonical source-bound mutation."""


class PerturbationCatalogueTooLarge(InvalidPerturbation):
    """Raised when the complete witness-derived catalogue exceeds its cap."""

    def __init__(self, catalogue_size: int | str) -> None:
        self.catalogue_size = catalogue_size
        if isinstance(catalogue_size, int):
            message = (
                f"the complete perturbation catalogue contains {catalogue_size} entries "
                f"(maximum {MAX_PERTURBATIONS})"
            )
        else:
            message = str(catalogue_size)
        super().__init__(
            message
        )


@dataclass(frozen=True, slots=True)
class CounterfactualScenario:
    """Internal scenario envelope used by analysers and recompilers.

    The ``state`` is intentionally not an HTTP response field.  Its parent
    metadata is the source state's parent, rather than the source itself, so
    the counterfactual cannot be mistaken for an operational transition.
    """

    state: CommunityState
    source_state_id: str
    source_parent_state_id: str | None
    scenario_state_id: str
    scenario_content_hash: str
    perturbation: api_models.PerturbationSpec

    @property
    def community(self) -> CommunityState:
        """Compatibility alias for integration callers."""

        return self.state

    @property
    def state_id(self) -> str:
        """Expose the counterfactual identity without making it operational."""

        return self.scenario_state_id

    @property
    def content_hash(self) -> str:
        return self.scenario_content_hash

    @property
    def source_content_hash(self) -> str:
        return self.perturbation.source_content_hash


def _canonical_value(value: Any) -> Any:
    """Canonicalise JSON-compatible values, including unordered collections."""

    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_canonical_value(item) for item in value]
        return sorted(
            values,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _exact_value(value: Any) -> Any:
    """Canonicalise mappings/sets while preserving declaration list order."""

    if isinstance(value, Mapping):
        return {
            str(key): _exact_value(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (set, frozenset)):
        values = [_exact_value(item) for item in value]
        return sorted(
            values,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )
    if isinstance(value, (list, tuple)):
        return [_exact_value(item) for item in value]
    return value


def _exact_json(value: Any) -> str:
    return json.dumps(
        _exact_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _slot_values(slots: Sequence[TimeSlot | str] | set[TimeSlot]) -> list[TimeSlot]:
    """Return a deterministic list of validated time slots."""

    try:
        parsed = {slot if isinstance(slot, TimeSlot) else TimeSlot(str(slot)) for slot in slots}
    except (TypeError, ValueError) as exc:
        raise InvalidPerturbation("perturbation contains an invalid time slot") from exc
    return sorted(parsed, key=lambda slot: slot.value)


def _source_hash(state: CommunityState) -> str:
    return canonical_state_hash(state)


def _perturbation_id(
    source_content_hash: str,
    perturbation_type: PerturbationType,
    target_id: str,
) -> str:
    """Build an explicit source/type/target-bound, contract-valid ID."""

    return (
        f"{PERTURBATION_NAMESPACE}_{source_content_hash.upper()}_"
        f"{perturbation_type.value}_{target_id}"
    )


def _scenario_id(
    source_content_hash: str,
    initiative_id: str,
    perturbation: api_models.PerturbationSpec,
    perturbed_content: Mapping[str, Any],
) -> str:
    """Hash scenario content in a domain-separated, non-recursive namespace."""

    payload = {
        "namespace": SCENARIO_NAMESPACE,
        "source_content_hash": source_content_hash,
        "initiative_id": initiative_id,
        "perturbation": perturbation.model_dump(mode="json"),
        # ``canonical_state_payload`` excludes both operational identity and
        # parent metadata, so this digest never self-includes ``state_id``.
        "perturbed_content": dict(perturbed_content),
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest().upper()
    return f"{SCENARIO_NAMESPACE}_{digest}"


def _person_by_id(state: CommunityState, target_id: str) -> PersonBlock:
    matches = [person for person in state.people if person.id == target_id]
    if len(matches) != 1:
        raise InvalidPerturbation(f"person target {target_id} is not unique in source state")
    return matches[0]


def _space_by_id(state: CommunityState, target_id: str) -> SpaceBlock:
    matches = [space for space in state.spaces if space.id == target_id]
    if len(matches) != 1:
        raise InvalidPerturbation(f"venue target {target_id} is not unique in source state")
    return matches[0]


def _resource_by_id(state: CommunityState, target_id: str) -> ResourceBlock:
    matches = [resource for resource in state.resources if resource.id == target_id]
    if len(matches) != 1:
        raise InvalidPerturbation(f"resource target {target_id} is not unique in source state")
    return matches[0]


def _resource_requirements(initiative: InitiativeBlueprint) -> dict[str, Any]:
    """Return requirements by ID, rejecting duplicate declarations first."""

    requirements = {}
    for requirement in initiative.resources:
        if requirement.resource_id in requirements:
            raise InvalidPerturbation(
                f"initiative {initiative.id} declares duplicate resource "
                f"requirement {requirement.resource_id}"
            )
        requirements[requirement.resource_id] = requirement
    return requirements


def _assignment_map(result: InitiativeAnalysisResult) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for assignment in result.assignments:
        if assignment.role_instance_id in assignments:
            raise AnalyserContractError(
                f"analyser returned duplicate role {assignment.role_instance_id}"
            )
        assignments[assignment.role_instance_id] = assignment.person_id
    return assignments


def _trace_entry(result: InitiativeAnalysisResult, kind: str) -> Any:
    entries = [entry for entry in result.assembly_trace if entry.requirement_kind == kind]
    if len(entries) != 1 or len(entries[0].selected_ids) != 1:
        raise AnalyserContractError(
            f"analyser witness for {result.initiative_id} has an invalid {kind} trace"
        )
    return entries[0]


def _venue_and_start(result: InitiativeAnalysisResult) -> tuple[str, TimeSlot]:
    venue_entry = _trace_entry(result, "venue")
    time_entry = _trace_entry(result, "time")
    try:
        start = TimeSlot(time_entry.selected_ids[0])
    except ValueError as exc:
        raise AnalyserContractError(
            f"analyser witness for {result.initiative_id} has an invalid start slot"
        ) from exc
    return venue_entry.selected_ids[0], start


def _coerce_status(raw: object) -> SolverStatus:
    if isinstance(raw, SolverStatus):
        return raw
    value: object
    if isinstance(raw, Mapping):
        value = raw.get("status")
    else:
        value = getattr(raw, "status", None)
    if isinstance(value, SolverStatus):
        return value
    if isinstance(value, str):
        try:
            return SolverStatus(value.upper())
        except ValueError as exc:
            raise AnalyserContractError(f"analyser returned unknown status {value!r}") from exc
    raise AnalyserContractError("authoritative analyser must return a result exposing status")


def _coerce_result(raw: object, initiative: InitiativeBlueprint) -> InitiativeAnalysisResult:
    """Convert analyser output to the frozen result model, fail-closed."""

    status = _coerce_status(raw)
    if isinstance(raw, InitiativeAnalysisResult):
        result = raw
    else:
        try:
            result = InitiativeAnalysisResult.model_validate(raw)
        except (TypeError, ValidationError):
            # Lightweight status-only stubs are useful for deterministic
            # INFEASIBLE/UNKNOWN tests.  They cannot stand in for a feasible
            # witness and therefore never bypass canonical validation.
            if status in (SolverStatus.INFEASIBLE, SolverStatus.UNKNOWN):
                unsafe_fields = ("objective_value", "assignments", "assembly_trace")
                if any(
                    (
                        raw.get(field) if isinstance(raw, Mapping)
                        else getattr(raw, field, None)
                    )
                    not in (None, [], {}, ())
                    for field in unsafe_fields
                ):
                    raise AnalyserContractError(
                        f"non-feasible analyser result for {initiative.id} contains a witness"
                    )
                supplied_initiative_id = (
                    raw.get("initiative_id")
                    if isinstance(raw, Mapping)
                    else getattr(raw, "initiative_id", None)
                )
                if supplied_initiative_id not in (None, initiative.id):
                    raise AnalyserContractError(
                        f"analyser result for {initiative.id} has a mismatched initiative"
                    )
                from app.api_models import SolverStats

                result = InitiativeAnalysisResult(
                    initiative_id=initiative.id,
                    status=status,
                    solver_stats=SolverStats(
                        branches=0,
                        conflicts=0,
                        wall_time_seconds=0.0,
                    ),
                )
            else:
                raise AnalyserContractError(
                    f"feasible analyser result for {initiative.id} does not match the result contract"
                )
    if result.status is not status:
        raise AnalyserContractError(
            f"analyser status for {initiative.id} is inconsistent with its result"
        )
    if result.initiative_id != initiative.id:
        raise AnalyserContractError(
            f"analyser result for {initiative.id} has a mismatched initiative"
        )
    return result


def _validate_feasible_result(
    result: InitiativeAnalysisResult,
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Sequence[object] = (),
) -> None:
    if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        return
    groups = [getattr(group, "value", str(group)) for group in relaxed_groups]
    try:
        valid = validate_analysis_witness(
            community,
            initiative,
            result,
            relaxed_groups=groups,
        )
    except Exception as exc:
        raise AnalyserContractError(
            f"feasible analyser result for {initiative.id} could not be replayed"
        ) from exc
    if not valid:
        raise AnalyserContractError(
            f"feasible analyser result for {initiative.id} failed canonical replay"
        )


def _validated_analyse(
    analyser: AnalysisCallable | None,
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Sequence[object] = (),
) -> InitiativeAnalysisResult:
    # Keep three independent views.  The analyser receives only a disposable
    # copy; validation uses a separate untouched copy; mutation checks compare
    # the original object before and after the call.  This prevents an
    # injectable analyser from making its own corrupted witness appear valid
    # by mutating the very state used for replay.
    original_community_payload = _exact_json(community.model_dump(mode="json"))
    original_initiative_payload = _exact_json(initiative.model_dump(mode="json"))
    analysis_community = community.model_copy(deep=True)
    analysis_initiative = initiative.model_copy(deep=True)
    analysis_community_payload = _exact_json(analysis_community.model_dump(mode="json"))
    analysis_initiative_payload = _exact_json(analysis_initiative.model_dump(mode="json"))
    validation_community = community.model_copy(deep=True)
    validation_initiative = initiative.model_copy(deep=True)
    try:
        raw = call_analyser(
            analyser,
            analysis_community,
            analysis_initiative,
            relaxed_groups=relaxed_groups,
        )
    except AnalyserContractError:
        if _exact_json(analysis_community.model_dump(mode="json")) != analysis_community_payload:
            raise AnalyserContractError("authoritative analyser mutated its community input")
        if _exact_json(analysis_initiative.model_dump(mode="json")) != analysis_initiative_payload:
            raise AnalyserContractError("authoritative analyser mutated its initiative input")
        if _exact_json(community.model_dump(mode="json")) != original_community_payload:
            raise AnalyserContractError("authoritative analyser mutated the supplied community state")
        if _exact_json(initiative.model_dump(mode="json")) != original_initiative_payload:
            raise AnalyserContractError("authoritative analyser mutated the supplied initiative")
        raise
    except Exception as exc:
        if _exact_json(analysis_community.model_dump(mode="json")) != analysis_community_payload:
            raise AnalyserContractError("authoritative analyser mutated its community input") from exc
        if _exact_json(analysis_initiative.model_dump(mode="json")) != analysis_initiative_payload:
            raise AnalyserContractError("authoritative analyser mutated its initiative input") from exc
        if _exact_json(community.model_dump(mode="json")) != original_community_payload:
            raise AnalyserContractError("authoritative analyser mutated the supplied community state") from exc
        if _exact_json(initiative.model_dump(mode="json")) != original_initiative_payload:
            raise AnalyserContractError("authoritative analyser mutated the supplied initiative") from exc
        raise AnalyserContractError(
            f"authoritative analyser failed for {initiative.id}"
        ) from exc
    if _exact_json(analysis_community.model_dump(mode="json")) != analysis_community_payload:
        raise AnalyserContractError("authoritative analyser mutated its community input")
    if _exact_json(analysis_initiative.model_dump(mode="json")) != analysis_initiative_payload:
        raise AnalyserContractError("authoritative analyser mutated its initiative input")
    if _exact_json(community.model_dump(mode="json")) != original_community_payload:
        raise AnalyserContractError("authoritative analyser mutated the supplied community state")
    if _exact_json(initiative.model_dump(mode="json")) != original_initiative_payload:
        raise AnalyserContractError("authoritative analyser mutated the supplied initiative")
    result = _coerce_result(raw, initiative)
    _validate_feasible_result(
        result,
        validation_community,
        validation_initiative,
        relaxed_groups=relaxed_groups,
    )
    return result


def _canonical_spec(spec_payload: Mapping[str, Any]) -> api_models.PerturbationSpec:
    try:
        return TypeAdapter(api_models.PerturbationSpec).validate_python(spec_payload)
    except (TypeError, ValidationError) as exc:
        raise InvalidPerturbation("perturbation does not match the frozen typed contract") from exc


def _make_person_spec(
    source_content_hash: str,
    initiative_id: str,
    person: PersonBlock,
) -> PersonUnavailablePerturbation:
    return PersonUnavailablePerturbation(
        id=_perturbation_id(
            source_content_hash,
            PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE,
            person.id,
        ),
        type=PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE,
        initiative_id=initiative_id,
        target_id=person.id,
        label=f"{person.name} becomes unavailable",
        source_content_hash=source_content_hash,
        before_available_slots=_slot_values(person.available_slots),
        after_available_slots=[],
    )


def _make_venue_spec(
    source_content_hash: str,
    initiative_id: str,
    venue: SpaceBlock,
) -> VenueUnavailablePerturbation:
    return VenueUnavailablePerturbation(
        id=_perturbation_id(
            source_content_hash,
            PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE,
            venue.id,
        ),
        type=PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE,
        initiative_id=initiative_id,
        target_id=venue.id,
        label=f"{venue.name} becomes unavailable",
        source_content_hash=source_content_hash,
        before_available_slots=_slot_values(venue.available_slots),
        after_available_slots=[],
    )


def _make_resource_spec(
    source_content_hash: str,
    initiative_id: str,
    requirement: Any,
    resource: ResourceBlock,
) -> ResourceAvailabilityPerturbation:
    return ResourceAvailabilityPerturbation(
        id=_perturbation_id(
            source_content_hash,
            PerturbationType.REDUCE_AVAILABLE_RESOURCE,
            resource.id,
        ),
        type=PerturbationType.REDUCE_AVAILABLE_RESOURCE,
        initiative_id=initiative_id,
        target_id=resource.id,
        label=f"{resource.name} availability reduced",
        source_content_hash=source_content_hash,
        requirement_id=requirement.resource_id,
        required_quantity=requirement.quantity,
        before_quantity=resource.quantity,
        after_quantity=max(0, requirement.quantity - 1),
    )


def generate_canonical_perturbations(
    source_state: CommunityState,
    initiative: InitiativeBlueprint,
    baseline_result: InitiativeAnalysisResult,
) -> list[api_models.PerturbationSpec]:
    """Generate the complete deterministic witness-derived perturbation list."""

    requirements = _resource_requirements(initiative)
    result = _coerce_result(baseline_result, initiative)
    if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        raise BaselineNotFeasible(
            f"initiative {initiative.id} baseline status is {result.status.value}"
        )
    _validate_feasible_result(result, source_state, initiative)

    try:
        assignments = _assignment_map(result)
        venue_id, _ = _venue_and_start(result)
        selected_people = sorted(set(assignments.values()))
        people = [_person_by_id(source_state, person_id) for person_id in selected_people]
        venue = _space_by_id(source_state, venue_id)
    except (KeyError, ValueError, TypeError) as exc:
        if isinstance(exc, AnalyserContractError):
            raise
        raise AnalyserContractError(
            f"baseline witness for {initiative.id} could not produce a perturbation catalogue"
        ) from exc

    source_content_hash = _source_hash(source_state)
    perturbations: list[api_models.PerturbationSpec] = [
        _make_person_spec(source_content_hash, initiative.id, person)
        for person in people
    ]
    perturbations.append(_make_venue_spec(source_content_hash, initiative.id, venue))
    for resource_id in sorted(requirements):
        resource = _resource_by_id(source_state, resource_id)
        perturbations.append(
            _make_resource_spec(
                source_content_hash,
                initiative.id,
                requirements[resource_id],
                resource,
            )
        )

    # The list is intentionally checked only after the full catalogue exists;
    # returning an arbitrary prefix would make resilience ratios dishonest.
    if len(perturbations) > MAX_PERTURBATIONS:
        raise PerturbationCatalogueTooLarge(len(perturbations))
    return perturbations


def _entity_maps(payload: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for collection in ("organisations", "people", "spaces", "resources"):
        result[collection] = {
            str(item["id"]): item
            for item in payload.get(collection, [])
            if isinstance(item, Mapping) and "id" in item
        }
    return result


def _assert_structural_delta(
    source: CommunityState,
    scenario: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: api_models.PerturbationSpec,
    source_content_hash: str,
    expected_scenario_id: str,
    initiative_payload_before: str,
) -> None:
    """Prove that the scenario changed exactly its declared availability fact."""

    if source.state_id == scenario.state_id:
        raise InvalidPerturbation("scenario identity did not change")
    if scenario.state_id != expected_scenario_id:
        raise InvalidPerturbation("scenario identity is not the canonical scenario ID")
    if scenario.parent_state_id != source.parent_state_id:
        raise InvalidPerturbation("scenario must preserve source parent metadata internally")
    if scenario.parent_state_id == source.state_id:
        raise InvalidPerturbation("scenario must not claim source as an operational parent")
    if _source_hash(source) != source_content_hash:
        raise InvalidPerturbation("source content changed while applying perturbation")

    source_payload = canonical_state_payload(source)
    scenario_payload = canonical_state_payload(scenario)
    source_entities = _entity_maps(source_payload)
    scenario_entities = _entity_maps(scenario_payload)
    if source_entities.keys() != scenario_entities.keys():
        raise InvalidPerturbation("scenario changed the set of entity collections")

    changed: list[tuple[str, str, str]] = []
    for collection in source_entities:
        if source_entities[collection].keys() != scenario_entities[collection].keys():
            raise InvalidPerturbation("scenario changed entity identity or referential integrity")
        for target_id, source_item in source_entities[collection].items():
            scenario_item = scenario_entities[collection][target_id]
            if source_item.keys() != scenario_item.keys():
                raise InvalidPerturbation("scenario changed an entity's fact shape")
            for field in source_item:
                if source_item[field] != scenario_item[field]:
                    changed.append((collection, target_id, field))

    if perturbation.type is PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE:
        expected = ("people", perturbation.target_id, "available_slots")
    elif perturbation.type is PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE:
        expected = ("spaces", perturbation.target_id, "available_slots")
    elif perturbation.type is PerturbationType.REDUCE_AVAILABLE_RESOURCE:
        expected = ("resources", perturbation.target_id, "quantity")
    else:  # pragma: no cover - discriminated union is exhaustive.
        raise InvalidPerturbation("unsupported perturbation type")
    if changed != [expected]:
        raise InvalidPerturbation(
            f"perturbation changed {changed!r}; expected exactly {[expected]!r}"
        )

    # The initiative is an input declaration, never a mutable scenario fact.
    if _exact_json(initiative.model_dump(mode="json")) != initiative_payload_before:
        raise InvalidPerturbation("initiative changed while applying perturbation")


def _assert_scenario_receipt(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: api_models.PerturbationSpec,
    scenario: CounterfactualScenario,
    *,
    source_content_hash: str,
    initiative_payload_before: str,
) -> None:
    """Independently verify a returned scenario envelope before solving it.

    ``apply_canonical_perturbation`` performs this proof itself.  The stress
    producer repeats it at its trust boundary so a replaced or injected
    applier cannot smuggle an operational ID, a stale source/spec binding, or
    a forged digest into an outcome merely by using the right namespace
    prefix.
    """

    if not isinstance(scenario, CounterfactualScenario):
        raise InvalidPerturbation(
            "canonical perturbation applier must return a CounterfactualScenario"
        )
    if not isinstance(scenario.source_state_id, str) or scenario.source_state_id != source.state_id:
        raise InvalidPerturbation("scenario source state does not match source")
    if scenario.source_parent_state_id != source.parent_state_id:
        raise InvalidPerturbation("scenario source parent metadata does not match source")
    if not isinstance(
        scenario.state,
        CommunityState,
    ) or not isinstance(
        scenario.perturbation,
        (
            PersonUnavailablePerturbation,
            VenueUnavailablePerturbation,
            ResourceAvailabilityPerturbation,
        ),
    ):
        raise InvalidPerturbation("scenario envelope contains an invalid state or perturbation")
    if scenario.perturbation.model_dump(mode="json") != perturbation.model_dump(mode="json"):
        raise InvalidPerturbation("scenario perturbation does not match its catalogue entry")
    if not isinstance(scenario.scenario_state_id, str):
        raise InvalidPerturbation("scenario identity is not a valid string")
    if scenario.scenario_state_id != scenario.state.state_id:
        raise InvalidPerturbation("scenario envelope and state identities disagree")
    if not scenario.scenario_state_id.startswith(f"{SCENARIO_NAMESPACE}_"):
        raise InvalidPerturbation("scenario identity is outside the CF_STRESS_V1 namespace")

    expected_id = _scenario_id(
        source_content_hash,
        initiative.id,
        perturbation,
        canonical_state_payload(scenario.state),
    )
    if scenario.scenario_state_id != expected_id:
        raise InvalidPerturbation("scenario identity receipt does not match final content")
    if scenario.scenario_content_hash != canonical_state_hash(scenario.state):
        raise InvalidPerturbation("scenario content hash does not match final content")
    _assert_structural_delta(
        source,
        scenario.state,
        initiative,
        perturbation,
        source_content_hash,
        expected_id,
        initiative_payload_before,
    )


def validate_counterfactual_scenario(
    source: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: api_models.PerturbationSpec,
    scenario: CounterfactualScenario,
) -> CounterfactualScenario:
    """Revalidate a complete counterfactual receipt at a consumer boundary."""

    source_snapshot = _exact_json(source.model_dump(mode="json"))
    initiative_snapshot = _exact_json(initiative.model_dump(mode="json"))
    _assert_scenario_receipt(
        source,
        initiative,
        perturbation,
        scenario,
        source_content_hash=_source_hash(source),
        initiative_payload_before=initiative_snapshot,
    )
    if _exact_json(source.model_dump(mode="json")) != source_snapshot:
        raise InvalidPerturbation("scenario validation mutated the source state")
    if _exact_json(initiative.model_dump(mode="json")) != initiative_snapshot:
        raise InvalidPerturbation("scenario validation mutated the initiative")
    return scenario


def apply_canonical_perturbation(
    source_state: CommunityState,
    initiative: InitiativeBlueprint,
    perturbation: api_models.PerturbationSpec | Mapping[str, Any],
) -> CounterfactualScenario:
    """Apply one source-bound perturbation to an internal scenario envelope."""

    if not isinstance(
        perturbation,
        (
            PersonUnavailablePerturbation,
            VenueUnavailablePerturbation,
            ResourceAvailabilityPerturbation,
        ),
    ):
        perturbation = _canonical_spec(perturbation)

    source_content_hash = _source_hash(source_state)
    if perturbation.initiative_id != initiative.id:
        raise InvalidPerturbation("perturbation initiative does not match initiative")
    if perturbation.source_content_hash != source_content_hash:
        raise InvalidPerturbation("perturbation source hash does not match source state")
    expected_id = _perturbation_id(source_content_hash, perturbation.type, perturbation.target_id)
    if perturbation.id != expected_id:
        raise InvalidPerturbation("perturbation ID is not bound to source, type, and target")

    requirements = _resource_requirements(initiative)
    initiative_payload_before = _exact_json(initiative.model_dump(mode="json"))
    scenario = source_state.model_copy(deep=True)
    if source_state.parent_state_id == source_state.state_id:
        raise InvalidPerturbation("source state has self-referential operational lineage")

    if isinstance(perturbation, PersonUnavailablePerturbation):
        person = _person_by_id(source_state, perturbation.target_id)
        before = _slot_values(person.available_slots)
        after = _slot_values(perturbation.after_available_slots)
        if before != _slot_values(perturbation.before_available_slots) or after:
            raise InvalidPerturbation("person availability facts do not match source state")
        target = _person_by_id(scenario, perturbation.target_id)
        target.available_slots = set()
        if perturbation.label != f"{person.name} becomes unavailable":
            raise InvalidPerturbation("person perturbation label is not canonical")
    elif isinstance(perturbation, VenueUnavailablePerturbation):
        venue = _space_by_id(source_state, perturbation.target_id)
        before = _slot_values(venue.available_slots)
        after = _slot_values(perturbation.after_available_slots)
        if before != _slot_values(perturbation.before_available_slots) or after:
            raise InvalidPerturbation("venue availability facts do not match source state")
        target = _space_by_id(scenario, perturbation.target_id)
        target.available_slots = set()
        if perturbation.label != f"{venue.name} becomes unavailable":
            raise InvalidPerturbation("venue perturbation label is not canonical")
    elif isinstance(perturbation, ResourceAvailabilityPerturbation):
        requirement = requirements.get(perturbation.requirement_id)
        if requirement is None or requirement.resource_id != perturbation.target_id:
            raise InvalidPerturbation("resource perturbation requirement does not match target")
        resource = _resource_by_id(source_state, perturbation.target_id)
        expected_after = max(0, requirement.quantity - 1)
        if (
            perturbation.required_quantity != requirement.quantity
            or perturbation.before_quantity != resource.quantity
            or perturbation.after_quantity != expected_after
        ):
            raise InvalidPerturbation("resource quantity facts do not match source state")
        target = _resource_by_id(scenario, perturbation.target_id)
        target.quantity = expected_after
        if perturbation.label != f"{resource.name} availability reduced":
            raise InvalidPerturbation("resource perturbation label is not canonical")
    else:  # pragma: no cover - discriminated union is exhaustive.
        raise InvalidPerturbation("unsupported perturbation type")

    perturbed_content = canonical_state_payload(scenario)
    scenario_id = _scenario_id(
        source_content_hash,
        initiative.id,
        perturbation,
        perturbed_content,
    )
    scenario.state_id = scenario_id
    # A scenario is not an operational successor.  Keep the source's parent
    # for internal provenance without exposing a parent edge to the source.
    scenario.parent_state_id = source_state.parent_state_id
    scenario_content_hash = canonical_state_hash(scenario)
    # Recompute the receipt from the exact final content and all bindings;
    # checking only the namespace prefix would permit a forged scenario ID.
    receipt_id = _scenario_id(
        source_content_hash,
        initiative.id,
        perturbation,
        canonical_state_payload(scenario),
    )
    if receipt_id != scenario_id:
        raise InvalidPerturbation("scenario identity receipt does not match final content")
    _assert_structural_delta(
        source_state,
        scenario,
        initiative,
        perturbation,
        source_content_hash,
        scenario_id,
        initiative_payload_before,
    )
    return CounterfactualScenario(
        state=scenario,
        source_state_id=source_state.state_id,
        source_parent_state_id=source_state.parent_state_id,
        scenario_state_id=scenario_id,
        scenario_content_hash=scenario_content_hash,
        perturbation=perturbation,
    )


def _explanation_analyser(
    analyser: AnalysisCallable | None,
) -> AnalysisCallable:
    """Wrap explain runs so relaxed feasible witnesses are also replayed."""

    def wrapped(
        community: CommunityState,
        initiative: InitiativeBlueprint,
        *,
        relaxed_groups: Sequence[object] = (),
    ) -> InitiativeAnalysisResult:
        return _validated_analyse(
            analyser,
            community,
            initiative,
            relaxed_groups=relaxed_groups,
        )

    return wrapped


def _outcome(
    source_state: CommunityState,
    initiative: InitiativeBlueprint,
    baseline: InitiativeAnalysisResult,
    scenario: CounterfactualScenario,
    result: InitiativeAnalysisResult,
    analyser: AnalysisCallable | None,
) -> PerturbationOutcome:
    baseline_assignments = _assignment_map(baseline)
    baseline_venue, baseline_start = _venue_and_start(baseline)
    feasible = result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    if feasible:
        _validate_feasible_result(result, scenario.state, initiative)
        after_venue, after_start = _venue_and_start(result)
        after_assignments = _assignment_map(result)
        changed_roles = [
            role.id
            for role in initiative.roles
            if baseline_assignments.get(role.id) != after_assignments.get(role.id)
        ]
        objective_delta = int(result.objective_value) - int(baseline.objective_value)
        objective_degradation = max(0, objective_delta)
        unchanged = (
            not changed_roles
            and after_venue == baseline_venue
            and after_start == baseline_start
            and objective_delta == 0
        )
        criticality = StressCriticality.RESILIENT if unchanged else StressCriticality.DEGRADED
        survived: bool | None = True
        blockers = []
    elif result.status is SolverStatus.INFEASIBLE:
        after_venue = None
        after_start = None
        objective_delta = None
        objective_degradation = None
        changed_roles = []
        survived = False
        criticality = StressCriticality.CRITICAL
        try:
            explanation = explain_infeasibility(
                scenario.state,
                initiative,
                _explanation_analyser(analyser),
            )
        except AnalyserContractError as exc:
            # A status-only injected analyser is sufficient to classify the
            # scenario, but cannot truthfully answer the bounded relaxation
            # calls used by the optional explanation worker.  The factual
            # explanation was attempted; retain the decisive result and the
            # precise witness-derived blocker below when this seam is absent.
            if "must accept relaxed_groups" not in str(exc):
                raise
            explanation = None
        if explanation is not None and explanation.status is not SolverStatus.INFEASIBLE:
            raise AnalyserContractError(
                f"infeasible stress scenario {scenario.scenario_state_id} lost its factual explanation"
            )
        blockers = _precise_person_blockers(
            source_state,
            initiative,
            baseline,
            scenario.perturbation,
            explanation.blocking_requirement_sets if explanation is not None else (),
        )
    else:
        after_venue = None
        after_start = None
        objective_delta = None
        objective_degradation = None
        changed_roles = []
        survived = None
        criticality = StressCriticality.UNKNOWN
        blockers = []

    payload: dict[str, Any] = {
        "source_state_id": source_state.state_id,
        "perturbation_id": scenario.perturbation.id,
        "scenario_state_id": scenario.scenario_state_id,
        "perturbation": scenario.perturbation,
        "status": result.status,
        "survived": survived,
        "criticality": criticality,
        "objective_value": int(result.objective_value) if feasible else None,
        "objective_delta": objective_delta,
        "objective_degradation": objective_degradation,
        "assignment_changes": len(changed_roles) if feasible else None,
        "changed_roles": changed_roles if feasible else [],
        "baseline_venue_id": baseline_venue,
        "after_venue_id": after_venue,
        "baseline_start_slot": baseline_start,
        "after_start_slot": after_start,
        "blockers": blockers,
        "solver_stats": result.solver_stats,
    }
    try:
        return PerturbationOutcome.model_validate(payload)
    except ValidationError as exc:
        raise AnalyserContractError(
            f"stress outcome for {initiative.id} did not match the frozen outcome contract"
        ) from exc


def _precise_person_blockers(
    source_state: CommunityState,
    initiative: InitiativeBlueprint,
    baseline: InitiativeAnalysisResult,
    perturbation: api_models.PerturbationSpec,
    existing: Sequence[BlockingRequirementSet],
) -> list[BlockingRequirementSet]:
    """Add a concrete selected-helper shortfall to factual explanations.

    Inventory explanations intentionally report broad capability counts.  A
    person-unavailability scenario also has a precise witness-derived fact:
    the selected helper count after removing the target.  It is inserted only
    when it is a real shortage, leaving the bounded explanation's solver-
    confirmed sets intact for other perturbation types.
    """

    if perturbation.type is not PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE:
        return list(existing)
    target_id = perturbation.target_id
    role_map = {role.id: role for role in initiative.roles}
    baseline_assignments = _assignment_map(baseline)
    helper_roles = [
        role
        for role in initiative.roles
        if "digital_support" in role.required_capabilities
    ]
    if not helper_roles:
        return list(existing)
    required = len(helper_roles)
    remaining_ids = sorted(
        {
            person_id
            for role_id, person_id in baseline_assignments.items()
            if role_id in role_map
            and "digital_support" in role_map[role_id].required_capabilities
            and person_id != target_id
        }
    )
    if len(remaining_ids) >= required:
        return list(existing)
    precise = BlockingRequirementSet(
        groups=[RequirementGroup.ROLE_CAPABILITY],
        facts=[
            BlockingFact(
                required=required,
                available=len(remaining_ids),
                capability="digital_support",
                relevant_ids=remaining_ids,
                note=(
                    f"{target_id} unavailable; remaining selected digital support "
                    "helpers cannot fill every declared helper role"
                ),
            )
        ],
        restored_feasibility_when_relaxed=False,
    )
    return [precise, *existing]


def run_stress_test(
    request: StressTestRequest,
    initiative: InitiativeBlueprint,
    authoritative_base: CommunityState,
    authoritative_actions: Sequence[Any],
    analyser: AnalysisCallable | None = solve_initiative,
) -> StressTestResponse:
    """Reconstruct, stress, and classify every canonical perturbation."""

    if request.initiative_id != initiative.id:
        raise ValueError("stress request initiative does not match supplied initiative")
    source = reconstruct_authoritative_state(
        request.base_community,
        request.catalyst_path,
        authoritative_base,
        authoritative_actions,
    )
    baseline = _validated_analyse(analyser, source, initiative)
    if baseline.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        raise BaselineNotFeasible(
            f"initiative {initiative.id} baseline status is {baseline.status.value}"
        )
    catalogue = generate_canonical_perturbations(source, initiative, baseline)
    outcomes: list[PerturbationOutcome] = []
    for perturbation in catalogue:
        source_snapshot = _exact_json(source.model_dump(mode="json"))
        initiative_snapshot = _exact_json(initiative.model_dump(mode="json"))
        scenario = apply_canonical_perturbation(source, initiative, perturbation)
        if _exact_json(source.model_dump(mode="json")) != source_snapshot:
            raise InvalidPerturbation("canonical perturbation applier mutated the source state")
        if _exact_json(initiative.model_dump(mode="json")) != initiative_snapshot:
            raise InvalidPerturbation("canonical perturbation applier mutated the initiative")
        validate_counterfactual_scenario(source, initiative, perturbation, scenario)
        result = _validated_analyse(analyser, scenario.state, initiative)
        outcomes.append(
            _outcome(source, initiative, baseline, scenario, result, analyser)
        )

    feasible_outcomes = [
        outcome
        for outcome in outcomes
        if outcome.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    ]
    failed_outcomes = [
        outcome for outcome in outcomes if outcome.status is SolverStatus.INFEASIBLE
    ]
    unknown_outcomes = [
        outcome for outcome in outcomes if outcome.status is SolverStatus.UNKNOWN
    ]
    decisive_count = len(feasible_outcomes) + len(failed_outcomes)
    resilience_ratio = (
        len(feasible_outcomes) / decisive_count if decisive_count else None
    )
    # Keep the response's evidence order aligned with the stable criticality
    # ranking: failures first, then feasible plan changes (largest role
    # change and burden degradation first), and unresolved solves last.  The
    # catalogue itself was still generated and solved in fixed type/target
    # order; sorting only affects the returned summary and critical-ID list.
    def outcome_sort_key(outcome: PerturbationOutcome) -> tuple[int, int, int, str]:
        status_rank = (
            0
            if outcome.status is SolverStatus.INFEASIBLE
            else 1
            if outcome.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
            else 2
        )
        return (
            status_rank,
            -(outcome.assignment_changes or 0),
            -(outcome.objective_degradation or 0),
            outcome.perturbation_id,
        )

    outcomes = sorted(outcomes, key=outcome_sort_key)
    critical = [
        outcome for outcome in outcomes
        if outcome.criticality is StressCriticality.CRITICAL
    ]
    payload = {
        "initiative_id": initiative.id,
        "source_state_id": source.state_id,
        "source_content_hash": _source_hash(source),
        "baseline_result": baseline,
        "catalogue_size": len(catalogue),
        "decisive_count": decisive_count,
        "survived_count": len(feasible_outcomes),
        "failed_count": len(failed_outcomes),
        "unknown_count": len(unknown_outcomes),
        "resilience_ratio": resilience_ratio,
        "outcomes": outcomes,
        "critical_perturbation_ids": [outcome.perturbation_id for outcome in critical],
    }
    try:
        return StressTestResponse.model_validate(payload)
    except ValidationError as exc:
        raise AnalyserContractError(
            f"stress response for {initiative.id} did not match the frozen response contract"
        ) from exc


__all__ = [
    "BaselineNotFeasible",
    "InvalidPerturbation",
    "PerturbationCatalogueTooLarge",
    "CounterfactualScenario",
    "generate_canonical_perturbations",
    "apply_canonical_perturbation",
    "validate_counterfactual_scenario",
    "run_stress_test",
]
