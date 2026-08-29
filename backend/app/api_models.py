"""Frozen HTTP request and response contracts for ASSEMBLE."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from app.models import MAX_ACTIONS, MAX_INITIATIVES, CatalystAction, CommunityState, ContractModel, StableId


class SolverStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class RequirementGroup(StrEnum):
    ROLE_CAPABILITY = "role_capability"
    LANGUAGE = "language"
    AVAILABILITY = "availability"
    VENUE_FEATURE = "venue_feature"
    VENUE_CAPACITY = "venue_capacity"
    RESOURCE_QUANTITY = "resource_quantity"
    MAXIMUM_CONTRIBUTION = "maximum_contribution"


class AnalyseRequest(ContractModel):
    community: CommunityState
    initiative_ids: list[StableId] = Field(min_length=1, max_length=MAX_INITIATIVES)


class ExplainRequest(ContractModel):
    community: CommunityState
    initiative_id: StableId


class UnlockRequest(ContractModel):
    community: CommunityState
    initiative_id: StableId
    actions: list[CatalystAction] = Field(min_length=1, max_length=MAX_ACTIONS)


class PlanRequest(ContractModel):
    community: CommunityState
    initiative_id: StableId
    actions: list[CatalystAction] = Field(min_length=1, max_length=MAX_ACTIONS)
    max_depth: Literal[2] = 2
    max_expanded_states: int = Field(default=20, ge=1, le=20, strict=True)


class TransitionRequest(ContractModel):
    community: CommunityState
    action_id: StableId
    actions: list[CatalystAction] = Field(min_length=1, max_length=MAX_ACTIONS)


class CompileSummary(ContractModel):
    people: int = Field(ge=0)
    organisations: int = Field(ge=0)
    spaces: int = Field(ge=0)
    resources: int = Field(ge=0)
    decision_variables: int = Field(ge=0)
    hard_constraints: int = Field(ge=0)


class RoleAssignment(ContractModel):
    role_instance_id: StableId
    person_id: StableId


class AssemblyTraceEntry(ContractModel):
    requirement_kind: Literal["role", "venue", "resource", "time"]
    requirement_id: str = Field(min_length=1)
    selected_ids: list[StableId] = Field(min_length=1)
    facts: dict[str, Any] = Field(default_factory=dict)


class SolverStats(ContractModel):
    branches: int = Field(ge=0)
    conflicts: int = Field(ge=0)
    wall_time_seconds: float = Field(ge=0)


class InitiativeAnalysisResult(ContractModel):
    initiative_id: StableId
    status: SolverStatus
    objective_value: int | None = Field(default=None, ge=0)
    assignments: list[RoleAssignment] = Field(default_factory=list)
    assembly_trace: list[AssemblyTraceEntry] = Field(default_factory=list)
    solver_stats: SolverStats

    @model_validator(mode="after")
    def status_matches_witness(self) -> "InitiativeAnalysisResult":
        feasible = self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        if feasible:
            if self.objective_value is None:
                raise ValueError("feasible results require an objective value")
            if not self.assignments or not self.assembly_trace:
                raise ValueError("feasible results require a complete assignment witness and trace")
        elif self.objective_value is not None or self.assignments or self.assembly_trace:
            raise ValueError(
                "INFEASIBLE and UNKNOWN results must not contain an objective or witness"
            )
        return self


class AnalyseResponse(ContractModel):
    compile: CompileSummary
    results: list[InitiativeAnalysisResult] = Field(min_length=1)


class BlockingFact(ContractModel):
    required: int | None = Field(default=None, ge=0)
    available: int | None = Field(default=None, ge=0)
    capability: str | None = None
    language: str | None = None
    requirement_id: str | None = None
    relevant_ids: list[StableId] = Field(default_factory=list)
    note: str | None = None


class BlockingRequirementSet(ContractModel):
    groups: list[RequirementGroup] = Field(min_length=1, max_length=2)
    facts: list[BlockingFact] = Field(min_length=1)
    restored_feasibility_when_relaxed: bool


class ExplainResponse(ContractModel):
    initiative_id: StableId
    status: SolverStatus
    blocking_requirement_sets: list[BlockingRequirementSet] = Field(default_factory=list)
    method: Literal["bounded_relax_and_resolve"]
    solver_runs: int = Field(ge=1)


class UnlockResponse(ContractModel):
    label: Literal["minimum_modelled_unlock"]
    target_initiative_id: StableId
    interventions: list[StableId] = Field(min_length=1)
    total_cost: int = Field(ge=0)
    catalogue_size: int = Field(ge=1)
    candidate_paths_evaluated: int = Field(ge=1)
    resulting_status: SolverStatus


class StateDiff(ContractModel):
    added_capabilities: dict[StableId, list[str]] = Field(default_factory=dict)
    added_people: list[StableId] = Field(default_factory=list)
    resource_quantity_changes: dict[StableId, int] = Field(default_factory=dict)


class TransitionResponse(ContractModel):
    action_id: StableId
    predecessor_state_id: StableId
    successor_state: CommunityState
    diff: StateDiff


class PlanNode(ContractModel):
    state_id: StableId
    action_path: list[StableId] = Field(default_factory=list)
    cumulative_cost: int = Field(ge=0)
    target_status: SolverStatus
    prune_reason: str | None = None


class PlanResponse(ContractModel):
    target_initiative_id: StableId
    path: list[StableId] = Field(min_length=1, max_length=2)
    total_cost: int = Field(ge=0)
    states: list[StableId] = Field(min_length=2, max_length=3)
    nodes: list[PlanNode] = Field(min_length=1, max_length=20)
    target_status_before: SolverStatus
    target_status_after: SolverStatus


class ApiError(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ContractModel):
    error: ApiError
