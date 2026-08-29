export type SolverStatus = "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN";

export type TimeSlot = "SAT_10" | "SAT_11" | "SAT_12" | "SAT_13";

export type RequirementKind = "role" | "venue" | "resource" | "time";

export interface OrganisationBlock {
  id: string;
  name: string;
}

export interface PersonBlock {
  id: string;
  name: string;
  organisation_id: string;
  capabilities: string[];
  languages: string[];
  willing_to_learn: string[];
  available_slots: TimeSlot[];
  max_contribution_slots: number;
}

export interface SpaceBlock {
  id: string;
  name: string;
  organisation_id: string;
  available_slots: TimeSlot[];
  capacity: number;
  features: string[];
}

export interface ResourceBlock {
  id: string;
  name: string;
  organisation_id: string;
  quantity: number;
  available_slots: TimeSlot[];
  shareable: boolean;
}

export interface CommunityState {
  state_id: string;
  parent_state_id: string | null;
  organisations: OrganisationBlock[];
  people: PersonBlock[];
  spaces: SpaceBlock[];
  resources: ResourceBlock[];
}

export interface RoleRequirement {
  id: string;
  label: string;
  required_capabilities: string[];
  required_languages: string[];
  allow_shared_person: boolean;
}

export interface InitiativeBlueprint {
  id: string;
  name: string;
  roles: RoleRequirement[];
  venue: {
    minimum_capacity: number;
    required_features: string[];
  };
  resources: Array<{ resource_id: string; quantity: number }>;
  candidate_start_slots: TimeSlot[];
  duration_slots: number;
}

export interface CatalystAction {
  id: string;
  name: string;
  cost: number;
  preconditions: {
    person_capabilities: Array<{ person_id: string; capability_id: string }>;
    willing_learners: Array<{ person_id: string; capability_id: string }>;
    space_availability: Array<{ space_id: string; slots: TimeSlot[] }>;
  };
  effects: Array<
    | { type: "add_capability"; person_id: string; capability_id: string }
    | { type: "add_person"; person: PersonBlock }
    | { type: "add_resource_quantity"; resource_id: string; quantity: number }
  >;
}

export interface DemoFixture {
  fixture_version: string;
  community: CommunityState;
  initiatives: InitiativeBlueprint[];
  actions: CatalystAction[];
}

export interface CompileSummary {
  people: number;
  organisations: number;
  spaces: number;
  resources: number;
  decision_variables: number;
  hard_constraints: number;
}

export interface RoleAssignment {
  role_instance_id: string;
  person_id: string;
}

export interface AssemblyTraceEntry {
  requirement_kind: RequirementKind;
  requirement_id: string;
  selected_ids: string[];
  facts: Record<string, unknown>;
}

export interface SolverStats {
  branches: number;
  conflicts: number;
  wall_time_seconds: number;
}

export interface InitiativeAnalysisResult {
  initiative_id: string;
  status: SolverStatus;
  objective_value: number | null;
  assignments: RoleAssignment[];
  assembly_trace: AssemblyTraceEntry[];
  solver_stats: SolverStats;
}

export interface AnalyseResponse {
  compile: CompileSummary;
  results: InitiativeAnalysisResult[];
}

export interface BlockingFact {
  required: number | null;
  available: number | null;
  capability: string | null;
  language: string | null;
  requirement_id: string | null;
  relevant_ids: string[];
  note: string | null;
}

export interface BlockingRequirementSet {
  groups: string[];
  facts: BlockingFact[];
  restored_feasibility_when_relaxed: boolean;
}

export interface ExplainResponse {
  initiative_id: string;
  status: SolverStatus;
  blocking_requirement_sets: BlockingRequirementSet[];
  method: "bounded_relax_and_resolve";
  solver_runs: number;
}

export interface UnlockResponse {
  label: "minimum_modelled_unlock";
  target_initiative_id: string;
  interventions: string[];
  total_cost: number;
  catalogue_size: number;
  candidate_paths_evaluated: number;
  resulting_status: SolverStatus;
}

export interface StateDiff {
  added_capabilities: Record<string, string[]>;
  added_people: string[];
  resource_quantity_changes: Record<string, number>;
}

export interface TransitionResponse {
  action_id: string;
  predecessor_state_id: string;
  successor_state: CommunityState;
  diff: StateDiff;
}

export interface PlanNode {
  state_id: string;
  action_path: string[];
  cumulative_cost: number;
  target_status: SolverStatus;
  prune_reason: string | null;
}

export interface PlanResponse {
  target_initiative_id: string;
  path: string[];
  total_cost: number;
  states: string[];
  nodes: PlanNode[];
  target_status_before: SolverStatus;
  target_status_after: SolverStatus;
}

export type ProjectStatus = "READY" | "NOT_READY";

export interface ProjectCatalystOutput {
  action_id: string;
  action_name: string;
  predecessor_state_id: string;
  successor_state_id: string;
  diff: StateDiff;
}

export interface ProjectSchedule {
  start_slot: string;
  end_slot: string;
  occupied_slots: string[];
  duration_slots: number;
}

export interface ProjectVenue {
  venue_id: string;
  venue_name: string;
  organisation_id: string;
  capacity: number;
  features: string[];
}

export interface ProjectOperationalAssignment {
  role_id: string;
  role_label: string;
  person_id: string;
  person_name: string;
  organisation_id: string;
  organisation_name: string;
  person_capabilities: string[];
  person_languages: string[];
  matched_capabilities: string[];
  matched_languages: string[];
  available_slots: string[];
}

export interface ProjectResourceAllocation {
  resource_id: string;
  resource_name: string;
  organisation_id: string;
  quantity_required: number;
  quantity_available: number;
  allocated_slots: string[];
  shareable: boolean;
}

export interface ProjectReadinessCheck {
  check_id: string;
  label: string;
  ready: boolean;
  evidence: string[];
}

export interface Project {
  id: string;
  source_plan_id: string;
  source_initiative_id: string;
  source_initiative_name: string;
  title: string;
  short_description: string;
  objective: string;
  status: ProjectStatus;
  base_state_id: string;
  verified_state_id: string;
  catalyst_path: string[];
  catalyst_outputs: ProjectCatalystOutput[];
  host_organisation_id: string;
  host_organisation_name: string;
  venue: ProjectVenue;
  schedule: ProjectSchedule;
  operational_assignments: ProjectOperationalAssignment[];
  resources: ProjectResourceAllocation[];
  capability_modules: string[];
  accessibility_requirements: string[];
  supported_languages: string[];
  participant_capacity: number;
  readiness: {
    status: ProjectStatus;
    checks: ProjectReadinessCheck[];
    missing: string[];
  };
  created_at: string;
  updated_at: string;
}

export interface CreateProjectResponse {
  project: Project;
  verification: InitiativeAnalysisResult;
}

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}
