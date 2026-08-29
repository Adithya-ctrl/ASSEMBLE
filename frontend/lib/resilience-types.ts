export const RESILIENCE_MODES = ["stress", "recovery", "frontier"] as const;
export type ResilienceMode = (typeof RESILIENCE_MODES)[number];

export const SOLVER_STATUSES = ["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"] as const;
export type ResilienceSolverStatus = (typeof SOLVER_STATUSES)[number];

export const STRESS_CRITICALITIES = ["RESILIENT", "DEGRADED", "CRITICAL", "UNKNOWN"] as const;
export type StressCriticality = (typeof STRESS_CRITICALITIES)[number];

export type PerturbationType =
  | "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
  | "MAKE_SELECTED_VENUE_UNAVAILABLE"
  | "REDUCE_AVAILABLE_RESOURCE";

export interface ResilienceSolverStats {
  branches: number;
  conflicts: number;
  wall_time_seconds: number;
}

export interface ResilienceRoleAssignment {
  role_instance_id: string;
  person_id: string;
}

export interface ResilienceAnalysisResult {
  initiative_id: string;
  status: ResilienceSolverStatus;
  objective_value: number | null;
  assignments: ResilienceRoleAssignment[];
  assembly_trace: Array<Record<string, unknown>>;
  solver_stats: ResilienceSolverStats;
}

export interface ResilienceBlockingSet {
  groups: string[];
  facts: Array<Record<string, unknown>>;
  restored_feasibility_when_relaxed: boolean;
}

interface PerturbationBase {
  id: string;
  initiative_id: string;
  target_id: string;
  label: string;
  source_content_hash: string;
}

export interface PersonUnavailablePerturbation extends PerturbationBase {
  type: "MAKE_ASSIGNED_PERSON_UNAVAILABLE";
  before_available_slots: string[];
  after_available_slots: [];
}

export interface VenueUnavailablePerturbation extends PerturbationBase {
  type: "MAKE_SELECTED_VENUE_UNAVAILABLE";
  before_available_slots: string[];
  after_available_slots: [];
}

export interface ResourceAvailabilityPerturbation extends PerturbationBase {
  type: "REDUCE_AVAILABLE_RESOURCE";
  requirement_id: string;
  required_quantity: number;
  before_quantity: number;
  after_quantity: number;
}

export type PerturbationSpec =
  | PersonUnavailablePerturbation
  | VenueUnavailablePerturbation
  | ResourceAvailabilityPerturbation;

export interface StressOutcome {
  source_state_id: string;
  perturbation_id: string;
  scenario_state_id: string;
  perturbation: PerturbationSpec;
  status: ResilienceSolverStatus;
  survived: boolean | null;
  criticality: StressCriticality;
  objective_value: number | null;
  objective_delta: number | null;
  objective_degradation: number | null;
  assignment_changes: number | null;
  changed_roles: string[];
  baseline_venue_id: string;
  after_venue_id: string | null;
  baseline_start_slot: string;
  after_start_slot: string | null;
  blockers: ResilienceBlockingSet[];
  solver_stats: ResilienceSolverStats;
}

export interface StressTestResponse {
  initiative_id: string;
  source_state_id: string;
  source_content_hash: string;
  baseline_result: ResilienceAnalysisResult;
  catalogue_size: number;
  decisive_count: number;
  survived_count: number;
  failed_count: number;
  unknown_count: number;
  resilience_ratio: number | null;
  outcomes: StressOutcome[];
  critical_perturbation_ids: string[];
}

export interface RecompileRoleDiff {
  role_id: string;
  before_person_id: string;
  after_person_id: string;
  changed: boolean;
}

export interface RecompileResponse {
  initiative_id: string;
  source_state_id: string;
  perturbation_id: string;
  scenario_state_id: string;
  perturbation: PerturbationSpec;
  status: ResilienceSolverStatus;
  minimum_assignment_changes: number | null;
  preserved_assignments: number | null;
  changed_assignments: number | null;
  role_diffs: RecompileRoleDiff[];
  new_result: ResilienceAnalysisResult | null;
  blockers: ResilienceBlockingSet[];
  stage1_status: ResilienceSolverStatus;
  stage1_solver_stats: ResilienceSolverStats;
  stage2_status: ResilienceSolverStatus | null;
  stage2_solver_stats: ResilienceSolverStats | null;
  minimum_proven: boolean;
  secondary_burden_optimal: boolean;
  explanation: string;
}

export interface ResilienceStateDiff {
  added_capabilities: Record<string, string[]>;
  added_people: string[];
  resource_quantity_changes: Record<string, number>;
}

export interface FrontierActionResult {
  source_state_id: string;
  action_id: string;
  action_name: string;
  cost: number;
  applicable: boolean;
  scenario_state_id: string | null;
  scenario_content_hash: string | null;
  newly_feasible_initiatives: string[];
  lost_feasible_initiatives: string[];
  unknown_initiatives: string[];
  total_feasible_after: number | null;
  produced_diff: ResilienceStateDiff | null;
  statuses_after: Record<string, ResilienceSolverStatus>;
  decisive_coverage_complete: boolean;
  explanation: string;
}

export interface CapabilityFrontierResponse {
  source_state_id: string;
  baseline_statuses: Record<string, ResilienceSolverStatus>;
  baseline_buildable_ids: string[];
  baseline_blocked_ids: string[];
  baseline_unknown_ids: string[];
  action_results: FrontierActionResult[];
  pareto_action_ids: string[];
  highest_leverage_action_id: string | null;
  ranking_explanation: string;
  uncertainty_could_change_winner: boolean;
}

export interface ResilienceSourceSummary {
  stateId: string;
  label: string;
  contentHash?: string;
  catalystPath: ReadonlyArray<{ id: string; label: string }>;
}

export interface ResilienceInitiativeChoice {
  id: string;
  label: string;
}

export interface FrontierExpectations {
  initiativeIds: readonly string[];
  actionIds: readonly string[];
}

export interface StressRunRequest {
  sourceStateId: string;
  sourceContentHash?: string;
  catalystPath: readonly string[];
  initiativeId: string;
}

export type PerturbationBinding = PerturbationSpec;

export interface RecoveryRunRequest extends StressRunRequest {
  perturbationId: string;
  perturbationBinding: PerturbationBinding;
}

export interface FrontierRunRequest {
  sourceStateId: string;
  sourceContentHash?: string;
  catalystPath: readonly string[];
  expectedInitiativeIds: readonly string[];
  expectedActionIds: readonly string[];
}

export interface ResilienceTaskError {
  code: string;
  message: string;
}

export interface ResilienceTaskState<Request> {
  request: Request | null;
  result: unknown | null;
  error: ResilienceTaskError | null;
  loading: boolean;
}

export interface ResilienceLabProps {
  source: ResilienceSourceSummary;
  initiatives: readonly ResilienceInitiativeChoice[];
  frontierExpectations: FrontierExpectations;
  stress: ResilienceTaskState<StressRunRequest>;
  recovery: ResilienceTaskState<RecoveryRunRequest>;
  frontier: ResilienceTaskState<FrontierRunRequest>;
  judgeMode: boolean;
  onRunStress: (request: StressRunRequest) => void;
  onRunRecovery: (request: RecoveryRunRequest) => void;
  onRunFrontier: (request: FrontierRunRequest) => void;
}
