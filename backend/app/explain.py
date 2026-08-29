"""Deterministic, bounded explanations for infeasible initiatives.

The reasoning layer deliberately depends on a small analyser protocol instead
of importing the CP-SAT implementation at module import time.  This keeps the
bounded algorithms testable while allowing the integration owner to wire the
authoritative solver in once its public entry point is available.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from enum import StrEnum
import importlib
import inspect
from typing import Protocol, cast

from app.api_models import (
    BlockingFact,
    BlockingRequirementSet,
    ExplainResponse,
    InitiativeAnalysisResult,
    RequirementGroup,
    SolverStatus,
)
from app.errors import AnalyserContractError
from app.models import CommunityState, InitiativeBlueprint, PersonBlock, TimeSlot, occupied_slots


class Analyser(Protocol):
    """Narrow protocol consumed by M2.

    ``relaxed_groups`` is empty for a normal solve.  A non-empty collection
    asks the authoritative analyser to omit those named hard-constraint groups
    for this bounded diagnostic run.  The return value may be an
    ``InitiativeAnalysisResult``, a bare status string/enum, or an exact status
    mapping with an optional matching ``initiative_id``.  Any richer result
    must satisfy the full ``InitiativeAnalysisResult`` contract.
    """

    def __call__(
        self,
        community: CommunityState,
        initiative: InitiativeBlueprint,
        *,
        relaxed_groups: Collection[RequirementGroup] = (),
    ) -> object: ...


AnalysisCallable = Callable[..., object]


def coerce_status(result: object) -> SolverStatus:
    """Return a frozen solver status from common analyser result shapes."""

    if isinstance(result, SolverStatus):
        return result
    if isinstance(result, StrEnum):
        value = str(result.value)
    elif isinstance(result, str):
        value = result
    elif isinstance(result, Mapping):
        value = result.get("status")  # type: ignore[assignment]
        if isinstance(value, StrEnum):
            value = value.value
    else:
        value = getattr(result, "status", None)
        if isinstance(value, StrEnum):
            value = value.value
    if not isinstance(value, str):
        raise AnalyserContractError(
            "authoritative analyser must return a result exposing status"
        )
    try:
        return SolverStatus(value.upper())
    except ValueError as exc:
        raise AnalyserContractError(f"unknown solver status {value!r}") from exc


def is_feasible(result: object) -> bool:
    """Whether a solver result is a decisive feasible result."""

    return coerce_status(result) in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}


def _resolve_default_analyser() -> AnalysisCallable:
    """Find the M1 analyser lazily, preserving importability before M1 lands."""

    try:
        module = importlib.import_module("app.solver")
    except ImportError as exc:  # pragma: no cover - exercised at integration time
        raise AnalyserContractError("app.solver is not available") from exc

    for name in (
        "analyse_initiative",
        "analyze_initiative",
        "solve_initiative",
        "analyse_one",
        "analyze_one",
        "run_analysis",
        "analyse",
        "analyze",
    ):
        candidate = getattr(module, name, None)
        if callable(candidate):
            return cast(AnalysisCallable, candidate)
    for name in ("AuthoritativeAnalyser", "AuthoritativeAnalyzer", "Analyser", "Analyzer"):
        candidate = getattr(module, name, None)
        if candidate is not None:
            instance = candidate() if inspect.isclass(candidate) else candidate
            for method_name in ("analyse", "analyze", "solve", "analyse_initiative"):
                method = getattr(instance, method_name, None)
                if callable(method):
                    return cast(AnalysisCallable, method)
    raise AnalyserContractError(
        "app.solver does not expose a supported initiative analyser entry point"
    )


def resolve_analyser(analyser: AnalysisCallable | None) -> AnalysisCallable:
    return analyser if analyser is not None else _resolve_default_analyser()


def _parameter_names(fn: AnalysisCallable) -> tuple[inspect.Parameter, ...] | None:
    try:
        return tuple(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return None


def _model_snapshot(model: CommunityState | InitiativeBlueprint) -> dict[str, object]:
    """Return a stable value snapshot for analyser-boundary mutation checks."""

    # Python-mode dumps retain sets, so value equality is independent of the
    # iteration order a deep copy may assign to those sets.
    return model.model_dump(mode="python")


def _is_exact_status_only_result(
    result: object,
    initiative: InitiativeBlueprint,
) -> bool:
    """Whether ``result`` uses the documented lightweight analyser seam."""

    if isinstance(result, (SolverStatus, StrEnum, str)):
        return True
    if not isinstance(result, Mapping):
        return False
    keys = set(result)
    if keys == {"status"}:
        return True
    if keys == {"initiative_id", "status"}:
        supplied_initiative_id = result["initiative_id"]
        if (
            not isinstance(supplied_initiative_id, str)
            or supplied_initiative_id != initiative.id
        ):
            raise AnalyserContractError(
                f"status receipt for {initiative.id} has a mismatched initiative"
            )
        return True
    return False


def _validate_rich_analyser_result(
    result: object,
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Collection[RequirementGroup],
) -> InitiativeAnalysisResult:
    """Validate source binding, status invariants, and any returned witness."""

    payload = (
        result.model_dump(mode="python")
        if isinstance(result, InitiativeAnalysisResult)
        else result
    )
    try:
        validated = InitiativeAnalysisResult.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise AnalyserContractError(
            "rich analyser result does not match InitiativeAnalysisResult"
        ) from exc

    if validated.initiative_id != initiative.id:
        raise AnalyserContractError(
            f"analyser result for {initiative.id} has a mismatched initiative"
        )

    if validated.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        # Import lazily so the explanation protocol remains importable without
        # loading the CP-SAT implementation until a rich witness needs replay.
        from app.solver import validate_analysis_witness

        try:
            valid = validate_analysis_witness(
                community,
                initiative,
                validated,
                relaxed_groups=relaxed_groups,
            )
        except Exception as exc:
            raise AnalyserContractError(
                f"feasible analyser result for {initiative.id} could not be replayed"
            ) from exc
        if not valid:
            raise AnalyserContractError(
                f"feasible analyser result for {initiative.id} failed canonical replay"
            )
    return validated


def call_analyser(
    analyser: AnalysisCallable | None,
    community: CommunityState,
    initiative: InitiativeBlueprint,
    *,
    relaxed_groups: Collection[RequirementGroup] = (),
) -> object:
    """Invoke and validate an analyser through the explicit M2 relaxation seam.

    The keyword is intentionally strict when relaxation is requested.  A
    two-argument solver cannot truthfully answer a relax-and-resolve query, so
    this fails closed rather than silently claiming a blocking set.  Inputs are
    isolated and rich results are source-bound and canonically replayed.
    """

    fn = resolve_analyser(analyser)
    groups = tuple(relaxed_groups)
    parameters = _parameter_names(fn)
    relaxation_names = (
        "relaxed_groups",
        "relax_groups",
        "ignored_groups",
        "disabled_groups",
    )
    named_parameter = None
    if parameters is not None:
        names = {parameter.name for parameter in parameters}
        named_parameter = next(
            (
                name
                for name in relaxation_names
                if any(
                    parameter.name == name
                    and parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    )
                    for parameter in parameters
                )
            ),
            None,
        )
        has_var_keyword = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters)
        if named_parameter is None and has_var_keyword:
            named_parameter = "relaxed_groups"

    def invoke(
        analysis_community: CommunityState,
        analysis_initiative: InitiativeBlueprint,
    ) -> object:
        if groups:
            if named_parameter is not None:
                return fn(
                    analysis_community,
                    analysis_initiative,
                    **{named_parameter: frozenset(groups)},
                )
            if parameters is not None:
                positional = [
                    parameter
                    for parameter in parameters
                    if parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                ]
                if len(positional) >= 3:
                    return fn(
                        analysis_community,
                        analysis_initiative,
                        frozenset(groups),
                    )
            raise AnalyserContractError(
                "authoritative analyser must accept relaxed_groups "
                "(or an equivalent third argument)"
            )

        # For baseline calls, a plain two-argument analyser is sufficient.  If
        # it advertises the seam, passing an empty set keeps invocation uniform.
        if named_parameter is not None:
            return fn(
                analysis_community,
                analysis_initiative,
                **{named_parameter: frozenset()},
            )
        if parameters is not None:
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
            if len(positional) >= 3:
                return fn(analysis_community, analysis_initiative, frozenset())
        return fn(analysis_community, analysis_initiative)

    # Third-party analysers receive disposable inputs.  Snapshotting both
    # copies before and after the call makes mutation a contract breach while
    # preventing it from leaking into the caller or witness validation state.
    caller_community_snapshot = _model_snapshot(community)
    caller_initiative_snapshot = _model_snapshot(initiative)
    analysis_community = community.model_copy(deep=True)
    analysis_initiative = initiative.model_copy(deep=True)
    try:
        raw_result = invoke(analysis_community, analysis_initiative)
    except Exception as exc:
        if _model_snapshot(analysis_community) != caller_community_snapshot:
            raise AnalyserContractError(
                "analysis state was mutated; authoritative analyser mutated its input "
                "(community)"
            ) from exc
        if _model_snapshot(analysis_initiative) != caller_initiative_snapshot:
            raise AnalyserContractError(
                "analysis initiative was mutated; authoritative analyser mutated its input "
                "(initiative)"
            ) from exc
        raise

    if _model_snapshot(analysis_community) != caller_community_snapshot:
        raise AnalyserContractError(
            "analysis state was mutated; authoritative analyser mutated its input "
            "(community)"
        )
    if _model_snapshot(analysis_initiative) != caller_initiative_snapshot:
        raise AnalyserContractError(
            "analysis initiative was mutated; authoritative analyser mutated its input "
            "(initiative)"
        )
    if _model_snapshot(community) != caller_community_snapshot:
        raise AnalyserContractError("authoritative analyser mutated the caller community")
    if _model_snapshot(initiative) != caller_initiative_snapshot:
        raise AnalyserContractError("authoritative analyser mutated the caller initiative")

    if _is_exact_status_only_result(raw_result, initiative):
        # Coercion here rejects unknown values before any caller can interpret
        # the lightweight status as a valid solver outcome.
        coerce_status(raw_result)
        return raw_result
    return _validate_rich_analyser_result(
        raw_result,
        community,
        initiative,
        relaxed_groups=groups,
    )


def _initiative_slot_options(initiative: InitiativeBlueprint) -> tuple[tuple[TimeSlot, ...], ...]:
    return tuple(occupied_slots(start, initiative.duration_slots) for start in initiative.candidate_start_slots)


def _available_for_any_start(available_slots: Collection[TimeSlot], options: Sequence[Sequence[TimeSlot]]) -> bool:
    return any(set(option).issubset(available_slots) for option in options)


def _missing_slot_note(
    item_slots: Collection[TimeSlot],
    options: Sequence[Sequence[TimeSlot]],
) -> str | None:
    """Describe the exact slots preventing every candidate start."""

    missing = sorted(
        {
            slot
            for option in options
            for slot in option
            if slot not in item_slots
        },
        key=lambda slot: slot.value,
    )
    if not missing:
        return None
    return f"missing slots: {', '.join(slot.value for slot in missing)}"


def _role_eligible(person: PersonBlock, role: object) -> bool:
    required_capabilities = getattr(role, "required_capabilities")
    required_languages = getattr(role, "required_languages")
    return set(required_capabilities).issubset(person.capabilities) and set(required_languages).issubset(person.languages)


def _fact(
    *,
    required: int | None = None,
    available: int | None = None,
    capability: str | None = None,
    language: str | None = None,
    requirement_id: str | None = None,
    relevant_ids: Iterable[str] = (),
    note: str | None = None,
) -> BlockingFact:
    return BlockingFact(
        required=required,
        available=available,
        capability=capability,
        language=language,
        requirement_id=requirement_id,
        relevant_ids=sorted(set(relevant_ids)),
        note=note,
    )


def inventory_facts(
    community: CommunityState,
    initiative: InitiativeBlueprint,
) -> dict[RequirementGroup, tuple[BlockingFact, ...]]:
    """Build deterministic requirement-vs-inventory facts for every group."""

    people = sorted(community.people, key=lambda item: item.id)
    spaces = sorted(community.spaces, key=lambda item: item.id)
    resources = {item.id: item for item in community.resources}
    options = _initiative_slot_options(initiative)
    facts: dict[RequirementGroup, list[BlockingFact]] = {group: [] for group in RequirementGroup}

    capability_counts: dict[str, int] = {}
    for role in initiative.roles:
        for capability in sorted(role.required_capabilities):
            capability_counts[capability] = capability_counts.get(capability, 0) + 1
    for capability, required in sorted(capability_counts.items()):
        available_ids = [person.id for person in people if capability in person.capabilities]
        facts[RequirementGroup.ROLE_CAPABILITY].append(
            _fact(
                required=required,
                available=len(available_ids),
                capability=capability,
                relevant_ids=available_ids,
            )
        )

    language_counts: dict[str, int] = {}
    for role in initiative.roles:
        for language in sorted(role.required_languages):
            language_counts[language] = language_counts.get(language, 0) + 1
    for language, required in sorted(language_counts.items()):
        available_ids = [person.id for person in people if language in person.languages]
        facts[RequirementGroup.LANGUAGE].append(
            _fact(required=required, available=len(available_ids), language=language, relevant_ids=available_ids)
        )

    for role in sorted(initiative.roles, key=lambda item: item.id):
        eligible_ids = [person.id for person in people if _role_eligible(person, role)]
        available_ids = [
            person.id
            for person in people
            if person.id in eligible_ids and _available_for_any_start(person.available_slots, options)
        ]
        unavailable = [
            person
            for person in people
            if person.id in eligible_ids
            and not _available_for_any_start(person.available_slots, options)
        ]
        unavailable_notes = [
            f"{person.id} {_missing_slot_note(person.available_slots, options)}"
            for person in unavailable
        ]
        facts[RequirementGroup.AVAILABILITY].append(
            _fact(
                required=1,
                available=len(available_ids),
                requirement_id=role.id,
                relevant_ids=eligible_ids,
                note="; ".join(
                    [
                        f"{role.label} eligible people available for a candidate start",
                        *unavailable_notes,
                    ]
                ),
            )
        )

    venue_candidates = [
        space
        for space in spaces
        if initiative.venue.required_features.issubset(space.features)
        and space.capacity >= initiative.venue.minimum_capacity
    ]
    available_venue_ids = [
        space.id
        for space in venue_candidates
        if _available_for_any_start(space.available_slots, options)
    ]
    unavailable_venue_notes = [
        f"{space.id} {_missing_slot_note(space.available_slots, options)}"
        for space in venue_candidates
        if not _available_for_any_start(space.available_slots, options)
    ]
    facts[RequirementGroup.AVAILABILITY].append(
        _fact(
            required=1,
            available=len(available_venue_ids),
            requirement_id="venue",
            relevant_ids=(space.id for space in venue_candidates),
            note="; ".join(
                ["venue candidates available for a candidate start", *unavailable_venue_notes]
            ),
        )
    )

    for requirement in sorted(initiative.resources, key=lambda item: item.resource_id):
        resource = resources.get(requirement.resource_id)
        resource_available = resource is not None and _available_for_any_start(
            resource.available_slots, options
        )
        missing_note = (
            _missing_slot_note(resource.available_slots, options)
            if resource is not None and not resource_available
            else None
        )
        facts[RequirementGroup.AVAILABILITY].append(
            _fact(
                required=1,
                available=int(resource_available),
                requirement_id=requirement.resource_id,
                relevant_ids=(requirement.resource_id,) if resource is not None else (),
                note="resource available for a candidate start"
                + (f"; {missing_note}" if missing_note else ""),
            )
        )

    for feature in sorted(initiative.venue.required_features):
        available_ids = [
            space.id
            for space in spaces
            if feature in space.features
        ]
        facts[RequirementGroup.VENUE_FEATURE].append(
            _fact(required=1, available=len(available_ids), capability=feature, relevant_ids=available_ids)
        )

    qualifying_spaces = [
        space
        for space in spaces
        if initiative.venue.required_features.issubset(space.features)
    ]
    maximum_capacity = max((space.capacity for space in qualifying_spaces), default=0)
    facts[RequirementGroup.VENUE_CAPACITY].append(
        _fact(
            required=initiative.venue.minimum_capacity,
            available=maximum_capacity,
            requirement_id="venue",
            relevant_ids=(space.id for space in qualifying_spaces),
            note="maximum capacity among spaces meeting requested features and time",
        )
    )

    for requirement in sorted(initiative.resources, key=lambda item: item.resource_id):
        resource = resources.get(requirement.resource_id)
        available = resource.quantity if resource is not None else 0
        facts[RequirementGroup.RESOURCE_QUANTITY].append(
            _fact(
                required=requirement.quantity,
                available=available,
                requirement_id=requirement.resource_id,
                relevant_ids=(requirement.resource_id,) if resource is not None else (),
            )
        )

    duration = initiative.duration_slots
    contribution_ids = [
        person.id
        for person in people
        if person.max_contribution_slots >= duration
        and any(_role_eligible(person, role) for role in initiative.roles)
    ]
    facts[RequirementGroup.MAXIMUM_CONTRIBUTION].append(
        _fact(
            required=len(initiative.roles),
            available=len(contribution_ids),
            requirement_id="roles",
            relevant_ids=contribution_ids,
            note="people able to contribute one full initiative duration",
        )
    )
    return {group: tuple(group_facts) for group, group_facts in facts.items() if group_facts}


def _groups_with_facts(facts: Mapping[RequirementGroup, Sequence[BlockingFact]]) -> tuple[RequirementGroup, ...]:
    return tuple(group for group in RequirementGroup if facts.get(group))


def _facts_for_groups(
    groups: Iterable[RequirementGroup],
    facts: Mapping[RequirementGroup, Sequence[BlockingFact]],
) -> list[BlockingFact]:
    """Prefer concrete deficits while retaining facts for interaction-only pairs."""

    selected: list[BlockingFact] = []
    for group in groups:
        group_facts = list(facts.get(group, ()))
        deficits = [
            fact
            for fact in group_facts
            if fact.required is not None
            and fact.available is not None
            and fact.available < fact.required
        ]
        selected.extend(deficits or group_facts)
    return selected


def explain_infeasibility(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    analyser: AnalysisCallable | None = None,
) -> ExplainResponse:
    """Explain an infeasible initiative via bounded relax-and-resolve runs."""

    runs = 0
    baseline = call_analyser(analyser, community, initiative)
    runs += 1
    status = coerce_status(baseline)
    if status is not SolverStatus.INFEASIBLE:
        return ExplainResponse(
            initiative_id=initiative.id,
            status=status,
            blocking_requirement_sets=[],
            method="bounded_relax_and_resolve",
            solver_runs=runs,
        )

    facts = inventory_facts(community, initiative)
    groups = _groups_with_facts(facts)
    restored: list[tuple[tuple[RequirementGroup, ...], bool]] = []
    for group in groups:
        candidate = (group,)
        result = call_analyser(analyser, community, initiative, relaxed_groups=candidate)
        runs += 1
        if is_feasible(result):
            restored.append((candidate, True))

    if not restored:
        for left_index, left in enumerate(groups):
            for right in groups[left_index + 1 :]:
                candidate = (left, right)
                result = call_analyser(analyser, community, initiative, relaxed_groups=candidate)
                runs += 1
                if is_feasible(result):
                    restored.append((candidate, True))

    blocking_sets = [
        BlockingRequirementSet(
            groups=list(candidate),
            facts=_facts_for_groups(candidate, facts),
            restored_feasibility_when_relaxed=restored_feasible,
        )
        for candidate, restored_feasible in restored
    ]
    return ExplainResponse(
        initiative_id=initiative.id,
        status=status,
        blocking_requirement_sets=blocking_sets,
        method="bounded_relax_and_resolve",
        solver_runs=runs,
    )


# Short aliases make the module pleasant to use from the integration adapter
# while retaining the explicit name used in tests and documentation.
explain = explain_infeasibility
explain_initiative = explain_infeasibility
explain_blocking_requirements = explain_infeasibility
build_inventory_facts = inventory_facts
