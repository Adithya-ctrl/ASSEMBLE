"""Frozen HTTP request and response contracts for ASSEMBLE."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from app.models import (
    MAX_ACTIONS,
    MAX_INITIATIVES,
    MAX_REQUIREMENTS,
    CatalystAction,
    CommunityState,
    ContractModel,
    StableId,
    TimeSlot,
)


MAX_PERTURBATIONS = 20


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

    @field_validator("max_depth", mode="before")
    @classmethod
    def max_depth_is_strict_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("max_depth must be the integer 2")
        return value


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


class PerturbationType(StrEnum):
    MAKE_ASSIGNED_PERSON_UNAVAILABLE = "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
    MAKE_SELECTED_VENUE_UNAVAILABLE = "MAKE_SELECTED_VENUE_UNAVAILABLE"
    REDUCE_AVAILABLE_RESOURCE = "REDUCE_AVAILABLE_RESOURCE"


class StressCriticality(StrEnum):
    CRITICAL = "CRITICAL"
    DEGRADED = "DEGRADED"
    RESILIENT = "RESILIENT"
    UNKNOWN = "UNKNOWN"


class PersonUnavailablePerturbation(ContractModel):
    id: StableId
    type: Literal[PerturbationType.MAKE_ASSIGNED_PERSON_UNAVAILABLE]
    initiative_id: StableId
    target_id: StableId
    label: str = Field(min_length=1, max_length=160)
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    before_available_slots: list[TimeSlot] = Field(max_length=len(TimeSlot))
    after_available_slots: list[TimeSlot] = Field(max_length=len(TimeSlot))

    @model_validator(mode="after")
    def exact_availability_delta(self) -> "PersonUnavailablePerturbation":
        if not self.before_available_slots or self.after_available_slots != []:
            raise ValueError("person unavailability requires non-empty before slots and an empty after list")
        if len(self.before_available_slots) != len(set(self.before_available_slots)):
            raise ValueError("before_available_slots must not contain duplicates")
        return self


class VenueUnavailablePerturbation(ContractModel):
    id: StableId
    type: Literal[PerturbationType.MAKE_SELECTED_VENUE_UNAVAILABLE]
    initiative_id: StableId
    target_id: StableId
    label: str = Field(min_length=1, max_length=160)
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    before_available_slots: list[TimeSlot] = Field(max_length=len(TimeSlot))
    after_available_slots: list[TimeSlot] = Field(max_length=len(TimeSlot))

    @model_validator(mode="after")
    def exact_availability_delta(self) -> "VenueUnavailablePerturbation":
        if not self.before_available_slots or self.after_available_slots != []:
            raise ValueError("venue unavailability requires non-empty before slots and an empty after list")
        if len(self.before_available_slots) != len(set(self.before_available_slots)):
            raise ValueError("before_available_slots must not contain duplicates")
        return self


class ResourceAvailabilityPerturbation(ContractModel):
    id: StableId
    type: Literal[PerturbationType.REDUCE_AVAILABLE_RESOURCE]
    initiative_id: StableId
    target_id: StableId
    label: str = Field(min_length=1, max_length=160)
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    requirement_id: StableId
    required_quantity: int = Field(ge=1)
    before_quantity: int = Field(ge=0)
    after_quantity: int = Field(ge=0)

    @model_validator(mode="after")
    def exact_resource_delta(self) -> "ResourceAvailabilityPerturbation":
        if self.target_id != self.requirement_id:
            raise ValueError("resource perturbation target must equal its requirement ID")
        if self.before_quantity < self.required_quantity:
            raise ValueError("resource perturbation requires a feasible before quantity")
        if self.after_quantity != self.required_quantity - 1:
            raise ValueError("resource after quantity must be exactly required quantity minus one")
        if self.after_quantity == self.before_quantity:
            raise ValueError("resource perturbation must change available quantity")
        return self


PerturbationSpec = Annotated[
    PersonUnavailablePerturbation
    | VenueUnavailablePerturbation
    | ResourceAvailabilityPerturbation,
    Field(discriminator="type"),
]


class StressTestRequest(ContractModel):
    base_community: CommunityState
    initiative_id: StableId
    catalyst_path: list[StableId] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def unique_path(self) -> "StressTestRequest":
        if len(self.catalyst_path) != len(set(self.catalyst_path)):
            raise ValueError("catalyst_path must not contain duplicate action IDs")
        return self


class PerturbationOutcome(ContractModel):
    source_state_id: StableId
    perturbation_id: StableId
    scenario_state_id: StableId
    perturbation: PerturbationSpec
    status: SolverStatus
    survived: bool | None
    criticality: StressCriticality
    objective_value: int | None = Field(default=None, ge=0)
    objective_delta: int | None = None
    objective_degradation: int | None = Field(default=None, ge=0)
    assignment_changes: int | None = Field(default=None, ge=0)
    changed_roles: list[StableId] = Field(default_factory=list, max_length=MAX_REQUIREMENTS)
    baseline_venue_id: StableId
    after_venue_id: StableId | None = None
    baseline_start_slot: TimeSlot
    after_start_slot: TimeSlot | None = None
    blockers: list[BlockingRequirementSet] = Field(default_factory=list, max_length=MAX_REQUIREMENTS)
    solver_stats: SolverStats

    @model_validator(mode="after")
    def status_matches_outcome(self) -> "PerturbationOutcome":
        feasible = self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        if feasible and self.survived is not True:
            raise ValueError("feasible perturbations must be marked survived")
        if self.status is SolverStatus.INFEASIBLE and self.survived is not False:
            raise ValueError("infeasible perturbations must be marked failed")
        if self.status is SolverStatus.UNKNOWN and self.survived is not None:
            raise ValueError("UNKNOWN perturbations must be non-decisive")
        if not feasible and (
            self.objective_value is not None
            or self.objective_delta is not None
            or self.objective_degradation is not None
            or self.assignment_changes is not None
            or self.changed_roles
            or self.after_venue_id is not None
            or self.after_start_slot is not None
        ):
            raise ValueError("non-feasible perturbations must not carry plan metrics")
        if feasible:
            unchanged = (
                self.assignment_changes == 0
                and self.after_venue_id == self.baseline_venue_id
                and self.after_start_slot == self.baseline_start_slot
                and self.objective_delta == 0
            )
            expected = StressCriticality.RESILIENT if unchanged else StressCriticality.DEGRADED
            if self.criticality is not expected:
                raise ValueError("feasible criticality must reflect the complete meaningful plan")
        elif self.status is SolverStatus.INFEASIBLE and self.criticality is not StressCriticality.CRITICAL:
            raise ValueError("only INFEASIBLE perturbations are CRITICAL")
        elif self.status is SolverStatus.UNKNOWN and self.criticality is not StressCriticality.UNKNOWN:
            raise ValueError("UNKNOWN perturbations require UNKNOWN criticality")
        return self


class StressTestResponse(ContractModel):
    initiative_id: StableId
    source_state_id: StableId
    source_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    baseline_result: InitiativeAnalysisResult
    catalogue_size: int = Field(ge=1, le=MAX_PERTURBATIONS)
    decisive_count: int = Field(ge=0, le=MAX_PERTURBATIONS)
    survived_count: int = Field(ge=0, le=MAX_PERTURBATIONS)
    failed_count: int = Field(ge=0, le=MAX_PERTURBATIONS)
    unknown_count: int = Field(ge=0, le=MAX_PERTURBATIONS)
    resilience_ratio: float | None = Field(default=None, ge=0, le=1)
    outcomes: list[PerturbationOutcome] = Field(min_length=1, max_length=MAX_PERTURBATIONS)
    critical_perturbation_ids: list[StableId] = Field(default_factory=list, max_length=MAX_PERTURBATIONS)

    @model_validator(mode="after")
    def counts_match_catalogue(self) -> "StressTestResponse":
        if self.baseline_result.initiative_id != self.initiative_id:
            raise ValueError("baseline result must match the response initiative")
        if self.baseline_result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            raise ValueError("stress baseline must be feasible")
        if self.catalogue_size != len(self.outcomes):
            raise ValueError("catalogue_size must equal the full outcome count")
        actual_survived = sum(outcome.survived is True for outcome in self.outcomes)
        actual_failed = sum(outcome.survived is False for outcome in self.outcomes)
        actual_unknown = sum(outcome.survived is None for outcome in self.outcomes)
        if (
            self.survived_count != actual_survived
            or self.failed_count != actual_failed
            or self.unknown_count != actual_unknown
            or self.decisive_count != actual_survived + actual_failed
        ):
            raise ValueError("stress counts must be derived exactly from outcome statuses")
        if self.decisive_count != self.survived_count + self.failed_count:
            raise ValueError("decisive_count must equal survived_count plus failed_count")
        if self.catalogue_size != self.decisive_count + self.unknown_count:
            raise ValueError("catalogue counts must include decisive and UNKNOWN outcomes")
        if (self.resilience_ratio is None) != (self.decisive_count == 0):
            raise ValueError("resilience_ratio is present exactly when decisive outcomes exist")
        if self.resilience_ratio is not None and abs(
            self.resilience_ratio - (self.survived_count / self.decisive_count)
        ) > 1e-12:
            raise ValueError("resilience_ratio must use the complete decisive catalogue")
        perturbation_ids = [outcome.perturbation_id for outcome in self.outcomes]
        scenario_ids = [outcome.scenario_state_id for outcome in self.outcomes]
        if len(perturbation_ids) != len(set(perturbation_ids)):
            raise ValueError("stress outcomes require unique perturbation IDs")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("stress outcomes require unique counterfactual scenario IDs")
        for outcome in self.outcomes:
            if outcome.source_state_id != self.source_state_id:
                raise ValueError("stress outcome source state does not match the response")
            if outcome.perturbation_id != outcome.perturbation.id:
                raise ValueError("outcome perturbation ID does not match its typed specification")
            if outcome.perturbation.initiative_id != self.initiative_id:
                raise ValueError("perturbation initiative does not match the response")
            if outcome.perturbation.source_content_hash != self.source_content_hash:
                raise ValueError("perturbation source hash does not match the response")
            if not outcome.scenario_state_id.startswith("CF_STRESS_V1_"):
                raise ValueError("stress scenarios require the CF_STRESS_V1 namespace")
        expected_critical = [
            outcome.perturbation_id
            for outcome in self.outcomes
            if outcome.criticality is StressCriticality.CRITICAL
        ]
        if self.critical_perturbation_ids != expected_critical:
            raise ValueError("critical perturbation IDs must match ordered CRITICAL outcomes")
        return self


class RecompileRequest(ContractModel):
    base_community: CommunityState
    initiative_id: StableId
    catalyst_path: list[StableId] = Field(default_factory=list, max_length=2)
    perturbation_id: StableId

    @model_validator(mode="after")
    def unique_path(self) -> "RecompileRequest":
        if len(self.catalyst_path) != len(set(self.catalyst_path)):
            raise ValueError("catalyst_path must not contain duplicate action IDs")
        return self


class RecompileRoleDiff(ContractModel):
    role_id: StableId
    before_person_id: StableId
    after_person_id: StableId
    changed: bool


class RecompileResponse(ContractModel):
    initiative_id: StableId
    source_state_id: StableId
    perturbation_id: StableId
    scenario_state_id: StableId
    perturbation: PerturbationSpec
    status: SolverStatus
    minimum_assignment_changes: int | None = Field(default=None, ge=0)
    preserved_assignments: int | None = Field(default=None, ge=0)
    changed_assignments: int | None = Field(default=None, ge=0)
    role_diffs: list[RecompileRoleDiff] = Field(default_factory=list, max_length=MAX_REQUIREMENTS)
    new_result: InitiativeAnalysisResult | None = None
    blockers: list[BlockingRequirementSet] = Field(default_factory=list, max_length=MAX_REQUIREMENTS)
    stage1_status: SolverStatus
    stage1_solver_stats: SolverStats
    stage2_status: SolverStatus | None = None
    stage2_solver_stats: SolverStats | None = None
    minimum_proven: bool
    secondary_burden_optimal: bool
    explanation: str = Field(min_length=1, max_length=320)

    @model_validator(mode="after")
    def proof_claims_match_status(self) -> "RecompileResponse":
        if self.perturbation_id != self.perturbation.id:
            raise ValueError("recompile perturbation ID does not match its typed specification")
        if self.perturbation.initiative_id != self.initiative_id:
            raise ValueError("recompile perturbation initiative does not match")
        if not self.scenario_state_id.startswith("CF_STRESS_V1_"):
            raise ValueError("recompile scenarios require the CF_STRESS_V1 namespace")
        if self.minimum_proven != (self.stage1_status is SolverStatus.OPTIMAL):
            raise ValueError("minimum_proven requires an OPTIMAL Stage 1 result")
        if not self.minimum_proven and self.minimum_assignment_changes is not None:
            raise ValueError("an unproven Stage 1 result cannot claim a minimum")
        if self.stage1_status in (SolverStatus.FEASIBLE, SolverStatus.UNKNOWN):
            if self.status is not SolverStatus.UNKNOWN or self.stage2_status is not None or self.stage2_solver_stats is not None:
                raise ValueError("non-optimal Stage 1 must fail closed to UNKNOWN without Stage 2")
        elif self.stage1_status is SolverStatus.INFEASIBLE:
            if self.status is not SolverStatus.INFEASIBLE or self.stage2_status is not None or self.stage2_solver_stats is not None:
                raise ValueError("infeasible Stage 1 must stop before Stage 2")
        elif self.stage2_status is None or self.stage2_solver_stats is None:
            raise ValueError("OPTIMAL Stage 1 requires a recorded Stage 2")
        if self.secondary_burden_optimal != (self.stage2_status is SolverStatus.OPTIMAL):
            raise ValueError("secondary burden is optimal only for OPTIMAL Stage 2")
        feasible = self.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        if feasible != (self.new_result is not None):
            raise ValueError("only a feasible recompile carries a new result")
        if feasible and not self.minimum_proven:
            raise ValueError("a feasible recompile requires a proven minimum-change bound")
        if not feasible and (self.role_diffs or self.preserved_assignments is not None or self.changed_assignments is not None):
            raise ValueError("non-feasible recompiles must not carry assignment claims")
        if self.stage2_status is not None and self.status is not self.stage2_status:
            raise ValueError("overall recompile status must equal Stage 2 status")
        if self.new_result is not None:
            if self.new_result.initiative_id != self.initiative_id or self.new_result.status is not self.status:
                raise ValueError("final witness must match recompile initiative and status")
            role_ids = [item.role_id for item in self.role_diffs]
            if len(role_ids) != len(set(role_ids)):
                raise ValueError("recompile role diffs require unique role IDs")
            changed = sum(item.changed for item in self.role_diffs)
            if any(item.changed != (item.before_person_id != item.after_person_id) for item in self.role_diffs):
                raise ValueError("role diff changed flags must match before/after people")
            if self.changed_assignments != changed or self.preserved_assignments != len(self.role_diffs) - changed:
                raise ValueError("assignment counts must match the complete role diff")
            if self.minimum_assignment_changes != changed:
                raise ValueError("final role diff must match the proven minimum")
            result_roles = [item.role_instance_id for item in self.new_result.assignments]
            if result_roles != role_ids:
                raise ValueError("final witness assignments must match ordered role diffs")
        return self


class CapabilityFrontierRequest(ContractModel):
    base_community: CommunityState
    catalyst_path: list[StableId] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def unique_path(self) -> "CapabilityFrontierRequest":
        if len(self.catalyst_path) != len(set(self.catalyst_path)):
            raise ValueError("catalyst_path must not contain duplicate action IDs")
        return self


class FrontierActionResult(ContractModel):
    source_state_id: StableId
    action_id: StableId
    action_name: str = Field(min_length=1, max_length=160)
    cost: int = Field(ge=0)
    applicable: bool
    scenario_state_id: StableId | None = None
    scenario_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    newly_feasible_initiatives: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    lost_feasible_initiatives: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    unknown_initiatives: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    total_feasible_after: int | None = Field(default=None, ge=0, le=MAX_INITIATIVES)
    produced_diff: StateDiff | None = None
    statuses_after: dict[StableId, SolverStatus] = Field(default_factory=dict, max_length=MAX_INITIATIVES)
    decisive_coverage_complete: bool
    explanation: str = Field(min_length=1, max_length=320)

    @model_validator(mode="after")
    def receipt_matches_applicability(self) -> "FrontierActionResult":
        receipt = (self.scenario_state_id, self.scenario_content_hash, self.produced_diff)
        if self.applicable:
            if any(item is None for item in receipt):
                raise ValueError("applicable frontier actions require a complete counterfactual receipt")
            if not self.scenario_state_id.startswith("CF_FRONTIER_V1_"):  # type: ignore[union-attr]
                raise ValueError("frontier scenarios require the CF_FRONTIER_V1 namespace")
            if self.total_feasible_after is None:
                raise ValueError("applicable frontier actions require a feasible total")
        else:
            if any(item is not None for item in receipt):
                raise ValueError("inapplicable frontier actions must not carry a scenario receipt")
            if self.statuses_after or self.newly_feasible_initiatives or self.lost_feasible_initiatives or self.unknown_initiatives:
                raise ValueError("inapplicable frontier actions must not carry analysis outcomes")
            if self.total_feasible_after is not None or self.decisive_coverage_complete:
                raise ValueError("inapplicable frontier actions have no coverage or feasible total")
        return self


class CapabilityFrontierResponse(ContractModel):
    source_state_id: StableId
    baseline_statuses: dict[StableId, SolverStatus] = Field(max_length=MAX_INITIATIVES)
    baseline_buildable_ids: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    baseline_blocked_ids: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    baseline_unknown_ids: list[StableId] = Field(default_factory=list, max_length=MAX_INITIATIVES)
    action_results: list[FrontierActionResult] = Field(max_length=MAX_ACTIONS)
    pareto_action_ids: list[StableId] = Field(default_factory=list, max_length=MAX_ACTIONS)
    highest_leverage_action_id: StableId | None = None
    ranking_explanation: str = Field(min_length=1, max_length=480)
    uncertainty_could_change_winner: bool

    @model_validator(mode="after")
    def frontier_counts_and_coverage_match(self) -> "CapabilityFrontierResponse":
        initiative_ids = set(self.baseline_statuses)
        feasible_statuses = {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        expected_buildable = sorted(
            key for key, status in self.baseline_statuses.items() if status in feasible_statuses
        )
        expected_blocked = sorted(
            key for key, status in self.baseline_statuses.items() if status is SolverStatus.INFEASIBLE
        )
        expected_unknown = sorted(
            key for key, status in self.baseline_statuses.items() if status is SolverStatus.UNKNOWN
        )
        if self.baseline_buildable_ids != expected_buildable or self.baseline_blocked_ids != expected_blocked or self.baseline_unknown_ids != expected_unknown:
            raise ValueError("frontier baseline sets must exactly partition baseline statuses")
        action_ids = [item.action_id for item in self.action_results]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("frontier actions require unique IDs")
        for item in self.action_results:
            if item.source_state_id != self.source_state_id:
                raise ValueError("frontier action source does not match the response")
            if not item.applicable:
                continue
            if set(item.statuses_after) != initiative_ids:
                raise ValueError("applicable frontier actions require exact all-initiative coverage")
            after_buildable = {
                key for key, status in item.statuses_after.items() if status in feasible_statuses
            }
            expected_new = sorted(after_buildable - set(self.baseline_buildable_ids) - set(self.baseline_unknown_ids))
            expected_lost = sorted(
                key
                for key in self.baseline_buildable_ids
                if item.statuses_after[key] is SolverStatus.INFEASIBLE
            )
            unresolved = sorted(
                key
                for key in initiative_ids
                if self.baseline_statuses[key] is SolverStatus.UNKNOWN
                or item.statuses_after[key] is SolverStatus.UNKNOWN
            )
            complete = not unresolved
            if item.newly_feasible_initiatives != expected_new or item.lost_feasible_initiatives != expected_lost:
                raise ValueError("frontier gains and losses must use decisive status pairs only")
            if item.unknown_initiatives != unresolved or item.decisive_coverage_complete != complete:
                raise ValueError("frontier UNKNOWN accounting must match coverage")
            if item.total_feasible_after != len(after_buildable):
                raise ValueError("frontier feasible total must match after statuses")
        rankable = {
            item.action_id
            for item in self.action_results
            if item.applicable and item.decisive_coverage_complete
        }
        if not set(self.pareto_action_ids) <= rankable:
            raise ValueError("Pareto actions must have complete decisive coverage")
        if self.highest_leverage_action_id is not None and self.highest_leverage_action_id not in rankable:
            raise ValueError("highest leverage action must have complete decisive coverage")
        if self.uncertainty_could_change_winner and self.highest_leverage_action_id is not None:
            raise ValueError("an uncertain winner must be null")
        return self


class ApiError(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ContractModel):
    error: ApiError
