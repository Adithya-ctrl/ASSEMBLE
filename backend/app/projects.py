"""Create an executable Project only from a replayed, solver-verified plan."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from app.api_models import InitiativeAnalysisResult, SolverStatus
from app.errors import AnalyserContractError
from app.interventions import canonical_state_hash, transition_state
from app.models import CatalystAction, CommunityState, InitiativeBlueprint
from app.project_models import (
    CreateProjectRequest,
    CreateProjectResponse,
    Project,
    ProjectCatalystOutput,
    ProjectOperationalAssignment,
    ProjectReadiness,
    ProjectReadinessCheck,
    ProjectResourceAllocation,
    ProjectSchedule,
    ProjectStatus,
    ProjectVenue,
)
from app.solver import solve_initiative, validate_analysis_witness


class ProjectPlanNotFeasible(ValueError):
    """Raised when the replayed plan does not produce a complete solver witness."""


class CommunityStateMismatch(ValueError):
    """Raised when project creation does not begin from the authoritative fixture."""


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}_{sha256(encoded.encode('utf-8')).hexdigest()[:20].upper()}"


def _trace_by_kind(result: InitiativeAnalysisResult) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for entry in result.assembly_trace:
        grouped.setdefault(entry.requirement_kind, []).append(entry)
    return grouped


def _build_project(
    request: CreateProjectRequest,
    initiative: InitiativeBlueprint,
    actions: Sequence[CatalystAction],
) -> CreateProjectResponse:
    actions_by_id = {action.id: action for action in actions}
    current = request.base_community.model_copy(deep=True)
    catalyst_outputs: list[ProjectCatalystOutput] = []
    for action_id in request.catalyst_path:
        transition = transition_state(current, action_id, actions)
        action = actions_by_id[action_id]
        catalyst_outputs.append(
            ProjectCatalystOutput(
                action_id=action.id,
                action_name=action.name,
                predecessor_state_id=transition.predecessor_state_id,
                successor_state_id=transition.successor_state.state_id,
                diff=transition.diff,
            )
        )
        current = transition.successor_state

    verification = solve_initiative(current, initiative)
    if verification.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        raise ProjectPlanNotFeasible(
            f"initiative {initiative.id} is {verification.status} after replaying the submitted path"
        )
    if not validate_analysis_witness(current, initiative, verification):
        raise AnalyserContractError(
            f"project verification for {initiative.id} failed canonical replay"
        )

    trace = _trace_by_kind(verification)
    role_trace = {entry.requirement_id: entry for entry in trace.get("role", [])}
    venue_entry = trace["venue"][0]
    time_entry = trace["time"][0]
    resource_trace = {entry.requirement_id: entry for entry in trace.get("resource", [])}
    people = {person.id: person for person in current.people}
    organisations = {organisation.id: organisation for organisation in current.organisations}
    spaces = {space.id: space for space in current.spaces}
    resources = {resource.id: resource for resource in current.resources}

    assignments: list[ProjectOperationalAssignment] = []
    for role in initiative.roles:
        entry = role_trace[role.id]
        person = people[entry.selected_ids[0]]
        organisation = organisations[person.organisation_id]
        assignments.append(
            ProjectOperationalAssignment(
                role_id=role.id,
                role_label=role.label,
                person_id=person.id,
                person_name=person.name,
                organisation_id=organisation.id,
                organisation_name=organisation.name,
                person_capabilities=sorted(person.capabilities),
                person_languages=sorted(person.languages),
                matched_capabilities=sorted(role.required_capabilities & person.capabilities),
                matched_languages=sorted(role.required_languages & person.languages),
                available_slots=sorted(slot.value for slot in person.available_slots),
            )
        )

    venue = spaces[venue_entry.selected_ids[0]]
    venue_organisation = organisations[venue.organisation_id]
    occupied_slots = [str(slot) for slot in time_entry.facts["occupied_slots"]]
    schedule = ProjectSchedule(
        start_slot=str(time_entry.facts["start_slot"]),
        end_slot=occupied_slots[-1],
        occupied_slots=occupied_slots,
        duration_slots=int(time_entry.facts["duration_slots"]),
    )
    project_venue = ProjectVenue(
        venue_id=venue.id,
        venue_name=venue.name,
        organisation_id=venue.organisation_id,
        capacity=venue.capacity,
        features=sorted(venue.features),
    )

    allocations: list[ProjectResourceAllocation] = []
    for requirement in initiative.resources:
        entry = resource_trace[requirement.resource_id]
        resource = resources[requirement.resource_id]
        allocations.append(
            ProjectResourceAllocation(
                resource_id=resource.id,
                resource_name=resource.name,
                organisation_id=resource.organisation_id,
                quantity_required=requirement.quantity,
                quantity_available=int(entry.facts["quantity_available"]),
                allocated_slots=occupied_slots,
                shareable=resource.shareable,
            )
        )

    checks = [
        ProjectReadinessCheck(
            check_id="ROLES_READY",
            label="Operational roles assigned",
            ready=len(assignments) == len(initiative.roles),
            evidence=[f"{item.role_label}: {item.person_name}" for item in assignments],
        ),
        ProjectReadinessCheck(
            check_id="VENUE_READY",
            label="Venue capacity and features verified",
            ready=(
                venue.capacity >= initiative.venue.minimum_capacity
                and initiative.venue.required_features <= venue.features
            ),
            evidence=[f"{venue.name}: capacity {venue.capacity}", *sorted(venue.features)],
        ),
        ProjectReadinessCheck(
            check_id="RESOURCES_READY",
            label="Resources allocated",
            ready=all(item.quantity_available >= item.quantity_required for item in allocations),
            evidence=[
                f"{item.resource_name}: {item.quantity_required} required / {item.quantity_available} available"
                for item in allocations
            ] or ["No additional resources required"],
        ),
        ProjectReadinessCheck(
            check_id="LANGUAGE_READY",
            label="Required languages matched",
            ready=all(
                not role.required_languages
                or set(role.required_languages) <= set(assignment.matched_languages)
                for role, assignment in zip(initiative.roles, assignments, strict=True)
            ),
            evidence=[
                f"{item.role_label}: {', '.join(item.matched_languages) or 'no language requirement'}"
                for item in assignments
            ],
        ),
        ProjectReadinessCheck(
            check_id="SCHEDULE_READY",
            label="Shared time window verified",
            ready=bool(occupied_slots),
            evidence=[f"{schedule.start_slot} to {schedule.end_slot}", *occupied_slots],
        ),
    ]
    missing = [check.label for check in checks if not check.ready]
    readiness = ProjectReadiness(
        status=ProjectStatus.READY if not missing else ProjectStatus.NOT_READY,
        checks=checks,
        missing=missing,
    )

    source_payload = {
        "base_state_id": request.base_community.state_id,
        "base_state_content_hash": canonical_state_hash(request.base_community),
        "verified_state_id": current.state_id,
        "verified_state_content_hash": canonical_state_hash(current),
        "initiative_id": initiative.id,
        "catalyst_path": request.catalyst_path,
    }
    source_plan_id = _stable_id("PLAN", source_payload)
    project_id = _stable_id(
        "PROJECT",
        {
            **source_payload,
            "title": request.title,
            "short_description": request.short_description,
            "objective": request.objective,
        },
    )
    created_at = datetime.now(UTC)
    project = Project(
        id=project_id,
        source_plan_id=source_plan_id,
        source_initiative_id=initiative.id,
        source_initiative_name=initiative.name,
        title=request.title,
        short_description=request.short_description,
        objective=request.objective,
        status=readiness.status,
        base_state_id=request.base_community.state_id,
        verified_state_id=current.state_id,
        catalyst_path=request.catalyst_path,
        catalyst_outputs=catalyst_outputs,
        host_organisation_id=venue_organisation.id,
        host_organisation_name=venue_organisation.name,
        venue=project_venue,
        schedule=schedule,
        operational_assignments=assignments,
        resources=allocations,
        capability_modules=sorted(
            {capability for role in initiative.roles for capability in role.required_capabilities}
        ),
        accessibility_requirements=sorted(
            feature for feature in initiative.venue.required_features if "accessible" in feature
        ),
        supported_languages=sorted(
            {language for assignment in assignments for language in people[assignment.person_id].languages}
        ),
        participant_capacity=initiative.venue.minimum_capacity,
        readiness=readiness,
        created_at=created_at,
        updated_at=created_at,
    )
    return CreateProjectResponse(project=project, verification=verification)


def create_project_from_plan(
    request: CreateProjectRequest,
    initiative: InitiativeBlueprint,
    actions: Sequence[CatalystAction],
    authoritative_base: CommunityState,
) -> CreateProjectResponse:
    """Replay a 0..2 action path, verify it, and derive an operational Project."""

    same_identity = (
        request.base_community.state_id == authoritative_base.state_id
        and request.base_community.parent_state_id == authoritative_base.parent_state_id
    )
    same_content = canonical_state_hash(request.base_community) == canonical_state_hash(authoritative_base)
    if not same_identity or not same_content:
        raise CommunityStateMismatch(
            "base_community does not match the authoritative demo fixture state"
        )
    if len(request.catalyst_path) != len(set(request.catalyst_path)):
        raise ValueError("catalyst_path must not contain duplicate action IDs")
    action_ids = {action.id for action in actions}
    unknown = [action_id for action_id in request.catalyst_path if action_id not in action_ids]
    if unknown:
        raise ValueError(f"unknown action {unknown[0]}")
    return _build_project(request, initiative, actions)
