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
  candidate_subsets_evaluated: number;
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

export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}
