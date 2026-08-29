"""Solve compiled ASSEMBLE initiatives and decode auditable witnesses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ortools.sat.python import cp_model

from app.api_models import (
    AssemblyTraceEntry,
    CompileSummary,
    InitiativeAnalysisResult,
    RoleAssignment,
    SolverStats,
    SolverStatus,
)
from app.compiler import (
    AVAILABILITY,
    CompiledInitiative,
    LANGUAGE,
    MAXIMUM_CONTRIBUTION,
    RESOURCE_QUANTITY,
    ROLE_CAPABILITY,
    VENUE_CAPACITY,
    VENUE_FEATURE,
    compile_initiative,
)
from app.errors import AnalyserContractError
from app.models import (
    CommunityState,
    InitiativeBlueprint,
    PersonBlock,
    RoleRequirement,
    TimeSlot,
    occupied_slots,
)


DEFAULT_TIME_LIMIT_SECONDS = 10.0


def _status_from_cp_sat(status: int) -> SolverStatus:
    if status == cp_model.OPTIMAL:
        return SolverStatus.OPTIMAL
    if status == cp_model.FEASIBLE:
        return SolverStatus.FEASIBLE
    if status == cp_model.INFEASIBLE:
        return SolverStatus.INFEASIBLE
    # cp_model.MODEL_INVALID is deliberately not reported as INFEASIBLE.  It
    # is a solver/model failure, so the safe public result is UNKNOWN.
    return SolverStatus.UNKNOWN


def _configure_solver(
    solver: cp_model.CpSolver,
    *,
    time_limit_seconds: float,
    num_search_workers: int,
    random_seed: int,
) -> None:
    if time_limit_seconds < 0:
        raise ValueError("time_limit_seconds must be non-negative")
    if num_search_workers < 1:
        raise ValueError("num_search_workers must be positive")
    if random_seed < 0:
        raise ValueError("random_seed must be non-negative")
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = int(num_search_workers)
    solver.parameters.random_seed = int(random_seed)
    solver.parameters.log_search_progress = False


def _objective_value(solver: cp_model.CpSolver) -> int | None:
    try:
        # The objective is integral.  Rounding protects the response contract
        # from CP-SAT's float accessor returning 23.999999999 in some builds.
        return int(round(solver.ObjectiveValue()))
    except (RuntimeError, ValueError):
        return None


def _selected_assignment_vars(
    compiled: CompiledInitiative,
    solver: cp_model.CpSolver,
) -> list[RoleAssignment]:
    selected: list[RoleAssignment] = []
    role_order = {role.id: index for index, role in enumerate(compiled.initiative.roles)}
    entries: list[tuple[int, str, str]] = []
    for (role_id, person_id), variable in compiled.assignment_vars.items():
        if solver.Value(variable):
            entries.append((role_order[role_id], role_id, person_id))
    for _, role_id, person_id in sorted(entries):
        selected.append(RoleAssignment(role_instance_id=role_id, person_id=person_id))
    return selected


def _selected_venue(
    compiled: CompiledInitiative,
    solver: cp_model.CpSolver,
) -> str | None:
    selected = [
        space_id
        for space_id, variable in compiled.venue_vars.items()
        if solver.Value(variable)
    ]
    return sorted(selected)[0] if selected else None


def _selected_start(
    compiled: CompiledInitiative,
    solver: cp_model.CpSolver,
) -> TimeSlot | None:
    selected = [
        start
        for start, variable in compiled.start_vars.items()
        if solver.Value(variable)
    ]
    return sorted(selected, key=lambda slot: slot.value)[0] if selected else None


def _role_facts(role: RoleRequirement) -> dict[str, Any]:
    capabilities = sorted(role.required_capabilities)
    languages = sorted(role.required_languages)
    facts: dict[str, Any] = {
        "label": role.label,
        "required_capabilities": capabilities,
        "required_languages": languages,
    }
    # Preserve the compact fields used in the frozen API example while also
    # retaining the complete declaration for roles with multiple predicates.
    if len(capabilities) == 1:
        facts["capability"] = capabilities[0]
    if len(languages) == 1:
        facts["language"] = languages[0]
    return facts


def _build_trace(
    compiled: CompiledInitiative,
    solver: cp_model.CpSolver,
    assignments: Sequence[RoleAssignment],
) -> list[AssemblyTraceEntry]:
    person_by_role = {assignment.role_instance_id: assignment.person_id for assignment in assignments}
    spaces_by_id = {space.id: space for space in compiled.community.spaces}
    resources_by_id = {resource.id: resource for resource in compiled.community.resources}
    venue_id = _selected_venue(compiled, solver)
    start = _selected_start(compiled, solver)

    trace: list[AssemblyTraceEntry] = []
    for role in compiled.initiative.roles:
        person_id = person_by_role.get(role.id)
        if person_id is None:
            continue
        trace.append(
            AssemblyTraceEntry(
                requirement_kind="role",
                requirement_id=role.id,
                selected_ids=[person_id],
                facts=_role_facts(role),
            )
        )

    if venue_id is not None:
        space = spaces_by_id.get(venue_id)
        facts: dict[str, Any] = {
            "minimum_capacity": compiled.initiative.venue.minimum_capacity,
            "required_features": sorted(compiled.initiative.venue.required_features),
        }
        if space is not None:
            facts.update(
                {
                    "capacity": space.capacity,
                    "features": sorted(space.features),
                }
            )
        trace.append(
            AssemblyTraceEntry(
                requirement_kind="venue",
                requirement_id="VENUE",
                selected_ids=[venue_id],
                facts=facts,
            )
        )

    for requirement in compiled.initiative.resources:
        resource = resources_by_id.get(requirement.resource_id)
        facts = {
            "quantity_required": requirement.quantity,
        }
        if resource is not None:
            facts.update(
                {
                    "quantity_available": resource.quantity,
                    "shareable": resource.shareable,
                }
            )
        trace.append(
            AssemblyTraceEntry(
                requirement_kind="resource",
                requirement_id=requirement.resource_id,
                selected_ids=[requirement.resource_id],
                facts=facts,
            )
        )

    if start is not None:
        occupied = compiled.occupied_slots_by_start[start]
        trace.append(
            AssemblyTraceEntry(
                requirement_kind="time",
                requirement_id="TIME",
                selected_ids=[start.value],
                facts={
                    "start_slot": start.value,
                    "occupied_slots": [slot.value for slot in occupied],
                    "duration_slots": compiled.initiative.duration_slots,
                },
            )
        )
    return trace


def _canonical_trace(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    assignment_by_role: Mapping[str, str],
    venue_id: str,
    start: TimeSlot,
) -> list[AssemblyTraceEntry] | None:
    """Recompute the one canonical trace shape from domain declarations."""

    spaces_by_id = {space.id: space for space in community.spaces}
    resources_by_id = {resource.id: resource for resource in community.resources}
    venue = spaces_by_id.get(venue_id)
    if venue is None:
        return None
    try:
        occupied = occupied_slots(start, initiative.duration_slots)
    except ValueError:
        return None

    trace = [
        AssemblyTraceEntry(
            requirement_kind="role",
            requirement_id=role.id,
            selected_ids=[assignment_by_role[role.id]],
            facts=_role_facts(role),
        )
        for role in initiative.roles
    ]
    trace.append(
        AssemblyTraceEntry(
            requirement_kind="venue",
            requirement_id="VENUE",
            selected_ids=[venue.id],
            facts={
                "minimum_capacity": initiative.venue.minimum_capacity,
                "required_features": sorted(initiative.venue.required_features),
                "capacity": venue.capacity,
                "features": sorted(venue.features),
            },
        )
    )
    for requirement in initiative.resources:
        resource = resources_by_id.get(requirement.resource_id)
        if resource is None:
            return None
        trace.append(
            AssemblyTraceEntry(
                requirement_kind="resource",
                requirement_id=requirement.resource_id,
                selected_ids=[requirement.resource_id],
                facts={
                    "quantity_required": requirement.quantity,
                    "quantity_available": resource.quantity,
                    "shareable": resource.shareable,
                },
            )
        )
    trace.append(
        AssemblyTraceEntry(
            requirement_kind="time",
            requirement_id="TIME",
            selected_ids=[start.value],
            facts={
                "start_slot": start.value,
                "occupied_slots": [slot.value for slot in occupied],
                "duration_slots": initiative.duration_slots,
            },
        )
    )
    return trace


def _domain_assignment_is_valid(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    assignment_by_role: Mapping[str, str],
    venue_id: str,
    start: TimeSlot,
    *,
    relaxed_groups: frozenset[str] = frozenset(),
) -> bool:
    role_by_id = {role.id: role for role in initiative.roles}
    if set(assignment_by_role) != set(role_by_id):
        return False
    if start not in initiative.candidate_start_slots:
        return False
    try:
        occupied = occupied_slots(start, initiative.duration_slots)
    except ValueError:
        return False

    person_by_id = {person.id: person for person in community.people}
    selected_people: dict[str, PersonBlock] = {}
    for role_id, person_id in assignment_by_role.items():
        person = person_by_id.get(person_id)
        if person is None:
            return False
        role = role_by_id[role_id]
        if ROLE_CAPABILITY not in relaxed_groups and not role.required_capabilities <= person.capabilities:
            return False
        if LANGUAGE not in relaxed_groups and not role.required_languages <= person.languages:
            return False
        if AVAILABILITY not in relaxed_groups and not set(occupied) <= person.available_slots:
            return False
        selected_people[role_id] = person

    spaces_by_id = {space.id: space for space in community.spaces}
    venue = spaces_by_id.get(venue_id)
    if venue is None:
        return False
    if VENUE_CAPACITY not in relaxed_groups and venue.capacity < initiative.venue.minimum_capacity:
        return False
    if VENUE_FEATURE not in relaxed_groups and not initiative.venue.required_features <= venue.features:
        return False
    if AVAILABILITY not in relaxed_groups and not set(occupied) <= venue.available_slots:
        return False

    assigned_roles_by_person: dict[str, list[RoleRequirement]] = {}
    for role_id, person in selected_people.items():
        assigned_roles_by_person.setdefault(person.id, []).append(role_by_id[role_id])
    for roles in assigned_roles_by_person.values():
        for index, left_role in enumerate(roles):
            for right_role in roles[index + 1 :]:
                if not (left_role.allow_shared_person or right_role.allow_shared_person):
                    return False
    if MAXIMUM_CONTRIBUTION not in relaxed_groups:
        for person_id, roles in assigned_roles_by_person.items():
            has_shareable_pair = any(
                left_role.allow_shared_person or right_role.allow_shared_person
                for index, left_role in enumerate(roles)
                for right_role in roles[index + 1 :]
            )
            contribution = len(occupied) if has_shareable_pair else initiative.duration_slots * len(roles)
            if contribution > person_by_id[person_id].max_contribution_slots:
                return False

    resources_by_id = {resource.id: resource for resource in community.resources}
    for requirement in initiative.resources:
        resource = resources_by_id.get(requirement.resource_id)
        if resource is None:
            return False
        if RESOURCE_QUANTITY not in relaxed_groups and resource.quantity < requirement.quantity:
            return False
        if AVAILABILITY not in relaxed_groups and not set(occupied) <= resource.available_slots:
            return False
    return True


def validate_analysis_witness(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    result: InitiativeAnalysisResult,
    *,
    relaxed_groups: Iterable[str] = (),
) -> bool:
    """Validate a feasible result as a canonical, domain-derived witness."""

    groups = frozenset(relaxed_groups)
    if result.initiative_id != initiative.id:
        return False
    if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        return False
    if result.objective_value is None:
        return False

    declared_role_ids = [role.id for role in initiative.roles]
    assignment_role_ids = [assignment.role_instance_id for assignment in result.assignments]
    if assignment_role_ids != declared_role_ids:
        return False
    assignment_by_role = _normalise_assignments(result.assignments)
    if len(assignment_by_role) != len(declared_role_ids):
        return False

    venue_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "venue"]
    time_entries = [entry for entry in result.assembly_trace if entry.requirement_kind == "time"]
    if len(venue_entries) != 1 or len(time_entries) != 1:
        return False
    if len(venue_entries[0].selected_ids) != 1 or len(time_entries[0].selected_ids) != 1:
        return False
    venue_id = venue_entries[0].selected_ids[0]
    try:
        start = TimeSlot(time_entries[0].selected_ids[0])
    except ValueError:
        return False

    if not _domain_assignment_is_valid(
        community,
        initiative,
        assignment_by_role,
        venue_id,
        start,
        relaxed_groups=groups,
    ):
        return False
    expected_trace = _canonical_trace(community, initiative, assignment_by_role, venue_id, start)
    if expected_trace is None:
        return False
    actual_payload = [entry.model_dump(mode="json") for entry in result.assembly_trace]
    expected_payload = [entry.model_dump(mode="json") for entry in expected_trace]
    if actual_payload != expected_payload:
        return False

    expected_objective = 10 * len(set(assignment_by_role.values())) + 2 * len(initiative.roles)
    return result.objective_value == expected_objective


def _unknown_result(
    initiative_id: str,
    stats: SolverStats,
) -> InitiativeAnalysisResult:
    return InitiativeAnalysisResult(
        initiative_id=initiative_id,
        status=SolverStatus.UNKNOWN,
        objective_value=None,
        assignments=[],
        assembly_trace=[],
        solver_stats=stats,
    )


def solve_compiled(
    compiled: CompiledInitiative,
    *,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    max_time_seconds: float | None = None,
    num_search_workers: int = 1,
    random_seed: int = 0,
    solver: cp_model.CpSolver | None = None,
) -> InitiativeAnalysisResult:
    """Solve a compiled model and return a contract-valid decoded result.

    A timeout or model-invalid response is surfaced as ``UNKNOWN``.  In
    particular, no partial assignment is emitted for ``UNKNOWN`` because a
    partial CP-SAT incumbent is not a complete assembly witness.
    """

    if max_time_seconds is not None:
        if time_limit_seconds != DEFAULT_TIME_LIMIT_SECONDS and time_limit_seconds != max_time_seconds:
            raise ValueError("time_limit_seconds and max_time_seconds disagree")
        time_limit_seconds = max_time_seconds

    cp_solver = solver or cp_model.CpSolver()
    _configure_solver(
        cp_solver,
        time_limit_seconds=float(time_limit_seconds),
        num_search_workers=num_search_workers,
        random_seed=random_seed,
    )
    status_code = cp_solver.Solve(compiled.model)
    status = _status_from_cp_sat(status_code)
    stats = SolverStats(
        branches=max(0, int(cp_solver.NumBranches())),
        conflicts=max(0, int(cp_solver.NumConflicts())),
        wall_time_seconds=max(0.0, float(cp_solver.WallTime())),
    )

    if status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        return _unknown_result(compiled.initiative.id, stats) if status is SolverStatus.UNKNOWN else InitiativeAnalysisResult(
            initiative_id=compiled.initiative.id,
            status=status,
            objective_value=None,
            assignments=[],
            assembly_trace=[],
            solver_stats=stats,
        )

    assignments = _selected_assignment_vars(compiled, cp_solver)
    objective = _objective_value(cp_solver)
    if objective is None:
        raise AnalyserContractError(
            f"feasible solver result for {compiled.initiative.id} has no objective"
        )
    try:
        result = InitiativeAnalysisResult(
            initiative_id=compiled.initiative.id,
            status=status,
            objective_value=objective,
            assignments=assignments,
            assembly_trace=_build_trace(compiled, cp_solver, assignments),
            solver_stats=stats,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AnalyserContractError(
            f"feasible solver result for {compiled.initiative.id} could not be decoded"
        ) from exc
    if not validate_analysis_witness(
        compiled.community,
        compiled.initiative,
        result,
        relaxed_groups=compiled.relaxed_groups,
    ):
        raise AnalyserContractError(
            f"feasible solver result for {compiled.initiative.id} failed canonical replay"
        )
    return result


def solve_initiative(
    community_or_compiled: CommunityState | CompiledInitiative,
    initiative: InitiativeBlueprint | None = None,
    *,
    relax_groups: Iterable[str] | None = None,
    relaxed_groups: Iterable[str] | None = None,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    max_time_seconds: float | None = None,
    num_search_workers: int = 1,
    random_seed: int = 0,
    solver: cp_model.CpSolver | None = None,
) -> InitiativeAnalysisResult:
    """Compile and solve one initiative, or solve an existing compilation."""

    if isinstance(community_or_compiled, CompiledInitiative):
        if initiative is not None:
            raise ValueError("initiative must be omitted for a compiled model")
        if relax_groups is not None or relaxed_groups is not None:
            raise ValueError("relaxation belongs to compile_initiative")
        compiled = community_or_compiled
    else:
        if initiative is None:
            raise ValueError("initiative is required when passing a community")
        compiled = compile_initiative(
            community_or_compiled,
            initiative,
            relax_groups=relax_groups,
            relaxed_groups=relaxed_groups,
        )
    return solve_compiled(
        compiled,
        time_limit_seconds=time_limit_seconds,
        max_time_seconds=max_time_seconds,
        num_search_workers=num_search_workers,
        random_seed=random_seed,
        solver=solver,
    )


# British spelling is used by the HTTP endpoint; both spellings are kept as
# aliases for direct callers and tests.
analyse_initiative = solve_initiative
analyze_initiative = solve_initiative


def analyse_initiatives(
    community: CommunityState,
    initiatives: Sequence[InitiativeBlueprint],
    *,
    relax_groups: Iterable[str] | None = None,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    num_search_workers: int = 1,
    random_seed: int = 0,
) -> list[InitiativeAnalysisResult]:
    """Solve declared initiatives independently in declaration order."""

    return [
        solve_initiative(
            community,
            initiative,
            relax_groups=relax_groups,
            time_limit_seconds=time_limit_seconds,
            num_search_workers=num_search_workers,
            random_seed=random_seed,
        )
        for initiative in initiatives
    ]


def analyse_compiled_initiatives(
    compiled: Sequence[CompiledInitiative],
    *,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
    num_search_workers: int = 1,
    random_seed: int = 0,
) -> list[InitiativeAnalysisResult]:
    """Solve already-compiled initiatives without rebuilding their models."""

    return [
        solve_compiled(
            item,
            time_limit_seconds=time_limit_seconds,
            num_search_workers=num_search_workers,
            random_seed=random_seed,
        )
        for item in compiled
    ]


analyze_initiatives = analyse_initiatives
solve_many = analyse_initiatives
solve = solve_initiative


def build_compile_summary(
    community: CommunityState,
    initiatives: Sequence[InitiativeBlueprint],
    *,
    relax_groups: Iterable[str] | None = None,
) -> CompileSummary:
    """Return actual fixture and generated-model counts for an analyse call."""

    compiled = [
        compile_initiative(community, initiative, relax_groups=relax_groups)
        for initiative in initiatives
    ]
    return CompileSummary(
        people=len(community.people),
        organisations=len(community.organisations),
        spaces=len(community.spaces),
        resources=len(community.resources),
        decision_variables=sum(item.decision_variables for item in compiled),
        hard_constraints=sum(item.hard_constraints for item in compiled),
    )


def build_compile_summary_from_compiled(
    community: CommunityState,
    compiled: Sequence[CompiledInitiative],
) -> CompileSummary:
    """Derive counts from the exact compiled models used for solving."""

    return CompileSummary(
        people=len(community.people),
        organisations=len(community.organisations),
        spaces=len(community.spaces),
        resources=len(community.resources),
        decision_variables=sum(item.decision_variables for item in compiled),
        hard_constraints=sum(item.hard_constraints for item in compiled),
    )


compile_summary = build_compile_summary


def _trace_selected_id(
    trace: Sequence[AssemblyTraceEntry] | Sequence[Mapping[str, Any]],
    requirement_kind: str,
) -> str | None:
    for entry in trace:
        kind = entry.requirement_kind if isinstance(entry, AssemblyTraceEntry) else entry.get("requirement_kind")
        if kind != requirement_kind:
            continue
        selected_ids = entry.selected_ids if isinstance(entry, AssemblyTraceEntry) else entry.get("selected_ids", [])
        if selected_ids:
            return str(selected_ids[0])
    return None


def _normalise_assignments(
    assignments: Sequence[RoleAssignment] | Mapping[str, str] | Sequence[Mapping[str, str]],
) -> dict[str, str]:
    if isinstance(assignments, Mapping):
        return {str(role_id): str(person_id) for role_id, person_id in assignments.items()}
    result: dict[str, str] = {}
    for assignment in assignments:
        if isinstance(assignment, RoleAssignment):
            role_id, person_id = assignment.role_instance_id, assignment.person_id
        else:
            role_id = str(assignment["role_instance_id"])
            person_id = str(assignment["person_id"])
        if role_id in result:
            return {}
        result[role_id] = person_id
    return result


def replay_assignment(
    community: CommunityState,
    initiative: InitiativeBlueprint,
    result_or_assignments: InitiativeAnalysisResult
    | Sequence[RoleAssignment]
    | Mapping[str, str]
    | Sequence[Mapping[str, str]],
    *,
    venue_id: str | None = None,
    start_slot: TimeSlot | str | None = None,
) -> bool:
    """Independently replay a decoded assembly witness against the domain.

    The replay intentionally does not query CP-SAT.  It checks the concrete
    predicates (IDs, capabilities, language, availability, contribution,
    venue and resource facts) so a solver extraction bug cannot pass silently.
    """

    if isinstance(result_or_assignments, InitiativeAnalysisResult):
        return validate_analysis_witness(community, initiative, result_or_assignments)
    assignment_by_role = _normalise_assignments(result_or_assignments)
    if venue_id is None or start_slot is None or not assignment_by_role:
        return False
    try:
        start = start_slot if isinstance(start_slot, TimeSlot) else TimeSlot(str(start_slot))
    except ValueError:
        return False
    return _domain_assignment_is_valid(
        community,
        initiative,
        assignment_by_role,
        str(venue_id),
        start,
    )


validate_assignment = replay_assignment
replay_solution = replay_assignment
