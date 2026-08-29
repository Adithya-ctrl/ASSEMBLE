import type {
  CapabilityFrontierResponse,
  FrontierActionResult,
  RecompileResponse,
  ResilienceAnalysisResult,
  ResilienceSolverStatus,
  StressOutcome,
  StressTestResponse,
} from "./resilience-types";

export const SOURCE_HASH = "a".repeat(64);

const solverStats = {
  branches: 0,
  conflicts: 0,
  wall_time_seconds: 0.01,
};

export function feasibleResult(
  initiativeId: string,
  objectiveValue: number,
  assignments = [
    { role_instance_id: "DIGITAL_HELPER", person_id: "PRIYA" },
    { role_instance_id: "FACILITATOR", person_id: "SAM" },
  ],
): ResilienceAnalysisResult {
  return {
    initiative_id: initiativeId,
    status: "OPTIMAL",
    objective_value: objectiveValue,
    assignments,
    assembly_trace: [{ requirement_kind: "role", requirement_id: "DIGITAL_HELPER" }],
    solver_stats: solverStats,
  };
}

function criticalOutcome(index: number, initiativeId: string, sourceStateId: string): StressOutcome {
  const kind = index % 3;
  const id = `PERTURBATION_${index + 1}`;
  const common = {
    id,
    initiative_id: initiativeId,
    target_id: kind === 0 ? `PERSON_${index + 1}` : kind === 1 ? "COMMUNITY_HALL" : `RESOURCE_${index + 1}`,
    label:
      kind === 0
        ? `Person ${index + 1} becomes unavailable`
        : kind === 1
          ? "Community hall becomes unavailable"
          : `Resource ${index + 1} drops below the required quantity`,
    source_content_hash: SOURCE_HASH,
  };
  const perturbation = kind === 0
    ? {
        ...common,
        type: "MAKE_ASSIGNED_PERSON_UNAVAILABLE" as const,
        before_available_slots: ["SAT_10"],
        after_available_slots: [] as [],
      }
    : kind === 1
      ? {
          ...common,
          type: "MAKE_SELECTED_VENUE_UNAVAILABLE" as const,
          before_available_slots: ["SAT_10"],
          after_available_slots: [] as [],
        }
      : {
          ...common,
          type: "REDUCE_AVAILABLE_RESOURCE" as const,
          requirement_id: common.target_id,
          required_quantity: 2,
          before_quantity: 3,
          after_quantity: 1,
        };
  return {
    source_state_id: sourceStateId,
    perturbation_id: id,
    scenario_state_id: `CF_STRESS_V1_${index + 1}`,
    perturbation,
    status: "INFEASIBLE",
    survived: false,
    criticality: "CRITICAL",
    objective_value: null,
    objective_delta: null,
    objective_degradation: null,
    assignment_changes: null,
    changed_roles: [],
    baseline_venue_id: "COMMUNITY_HALL",
    after_venue_id: null,
    baseline_start_slot: "SAT_10",
    after_start_slot: null,
    blockers: [{ groups: ["roles"], facts: [{ note: "No complete witness remains." }], restored_feasibility_when_relaxed: true }],
    solver_stats: solverStats,
  };
}

export function allCriticalStressFixture(
  initiativeId = "BASIC_WORKSHOP",
  count = 4,
  sourceStateId = "S0",
): StressTestResponse {
  const outcomes = Array.from({ length: count }, (_, index) =>
    criticalOutcome(index, initiativeId, sourceStateId),
  );
  return {
    initiative_id: initiativeId,
    source_state_id: sourceStateId,
    source_content_hash: SOURCE_HASH,
    baseline_result: feasibleResult(initiativeId, 18),
    catalogue_size: count,
    decisive_count: count,
    survived_count: 0,
    failed_count: count,
    unknown_count: 0,
    resilience_ratio: 0,
    outcomes,
    critical_perturbation_ids: outcomes.map((item) => item.perturbation_id),
  };
}

export function trainedBasicRecoveryFixture(): RecompileResponse {
  const stress = allCriticalStressFixture();
  const perturbation = stress.outcomes[0].perturbation;
  return {
    initiative_id: "BASIC_WORKSHOP",
    source_state_id: "S_TRAINED",
    perturbation_id: perturbation.id,
    scenario_state_id: "CF_STRESS_V1_RECOVERY",
    perturbation,
    status: "OPTIMAL",
    minimum_assignment_changes: 1,
    preserved_assignments: 1,
    changed_assignments: 1,
    role_diffs: [
      {
        role_id: "DIGITAL_HELPER",
        before_person_id: "PRIYA",
        after_person_id: "LEO",
        changed: true,
      },
      {
        role_id: "FACILITATOR",
        before_person_id: "SAM",
        after_person_id: "SAM",
        changed: false,
      },
    ],
    new_result: feasibleResult("BASIC_WORKSHOP", 24, [
      { role_instance_id: "DIGITAL_HELPER", person_id: "LEO" },
      { role_instance_id: "FACILITATOR", person_id: "SAM" },
    ]),
    blockers: [],
    stage1_status: "OPTIMAL",
    stage1_solver_stats: solverStats,
    stage2_status: "OPTIMAL",
    stage2_solver_stats: solverStats,
    minimum_proven: true,
    secondary_burden_optimal: true,
    explanation: "One assignment must change; the secondary burden is optimal at 24.",
  };
}

const S0_BASELINE: Record<string, ResilienceSolverStatus> = {
  BASIC_WORKSHOP: "OPTIMAL",
  MULTILINGUAL_CLINIC: "INFEASIBLE",
  REPAIR_SHARE: "INFEASIBLE",
};

function frontierAction(
  actionId: string,
  actionName: string,
  cost: number,
  statusesAfter: Record<string, ResilienceSolverStatus>,
  newlyFeasible: string[],
): FrontierActionResult {
  return {
    source_state_id: "S0",
    action_id: actionId,
    action_name: actionName,
    cost,
    applicable: true,
    scenario_state_id: `CF_FRONTIER_V1_${actionId}`,
    scenario_content_hash: "b".repeat(64),
    newly_feasible_initiatives: newlyFeasible,
    lost_feasible_initiatives: [],
    unknown_initiatives: [],
    total_feasible_after: Object.values(statusesAfter).filter(
      (status) => status === "OPTIMAL" || status === "FEASIBLE",
    ).length,
    produced_diff: {
      added_capabilities: {},
      added_people: [],
      resource_quantity_changes: {},
    },
    statuses_after: statusesAfter,
    decisive_coverage_complete: true,
    explanation: "Evaluated independently from the same source.",
  };
}

export const FRONTIER_INITIATIVE_IDS = [
  "BASIC_WORKSHOP",
  "MULTILINGUAL_CLINIC",
  "REPAIR_SHARE",
] as const;

export const FRONTIER_ACTION_IDS = [
  "TRAIN_DIGITAL_HELPERS",
  "RECRUIT_HELPER_A",
  "RECRUIT_HELPER_B",
  "BORROW_TWO_LAPTOPS",
] as const;

export function s0FrontierFixture(): CapabilityFrontierResponse {
  const unchanged = { ...S0_BASELINE };
  const training = {
    BASIC_WORKSHOP: "OPTIMAL",
    MULTILINGUAL_CLINIC: "OPTIMAL",
    REPAIR_SHARE: "INFEASIBLE",
  } satisfies Record<string, ResilienceSolverStatus>;
  return {
    source_state_id: "S0",
    baseline_statuses: { ...S0_BASELINE },
    baseline_buildable_ids: ["BASIC_WORKSHOP"],
    baseline_blocked_ids: ["MULTILINGUAL_CLINIC", "REPAIR_SHARE"],
    baseline_unknown_ids: [],
    action_results: [
      frontierAction("TRAIN_DIGITAL_HELPERS", "Train digital helpers", 2, training, ["MULTILINGUAL_CLINIC"]),
      frontierAction("RECRUIT_HELPER_A", "Recruit helper A", 3, { ...unchanged }, []),
      frontierAction("RECRUIT_HELPER_B", "Recruit helper B", 3, { ...unchanged }, []),
      frontierAction("BORROW_TWO_LAPTOPS", "Borrow two laptops", 1, { ...unchanged }, []),
    ],
    pareto_action_ids: ["TRAIN_DIGITAL_HELPERS", "BORROW_TWO_LAPTOPS"],
    highest_leverage_action_id: "TRAIN_DIGITAL_HELPERS",
    ranking_explanation: "Training unlocks one initiative and is highest leverage.",
    uncertainty_could_change_winner: false,
  };
}

export function trainedFrontierFixture(): CapabilityFrontierResponse {
  const baseline = {
    BASIC_WORKSHOP: "OPTIMAL",
    MULTILINGUAL_CLINIC: "OPTIMAL",
    REPAIR_SHARE: "INFEASIBLE",
  } satisfies Record<string, ResilienceSolverStatus>;
  const training: FrontierActionResult = {
    source_state_id: "S_TRAINED",
    action_id: "TRAIN_DIGITAL_HELPERS",
    action_name: "Train digital helpers",
    cost: 2,
    applicable: false,
    scenario_state_id: null,
    scenario_content_hash: null,
    newly_feasible_initiatives: [],
    lost_feasible_initiatives: [],
    unknown_initiatives: [],
    total_feasible_after: null,
    produced_diff: null,
    statuses_after: {},
    decisive_coverage_complete: false,
    explanation: "Training is already present in the source.",
  };
  const remaining = FRONTIER_ACTION_IDS.slice(1).map((id, index) => ({
    ...frontierAction(id, id.replaceAll("_", " "), id === "BORROW_TWO_LAPTOPS" ? 1 : 3, { ...baseline }, []),
    source_state_id: "S_TRAINED",
    scenario_state_id: `CF_FRONTIER_V1_TRAINED_${index}`,
  }));
  return {
    source_state_id: "S_TRAINED",
    baseline_statuses: baseline,
    baseline_buildable_ids: ["BASIC_WORKSHOP", "MULTILINGUAL_CLINIC"],
    baseline_blocked_ids: ["REPAIR_SHARE"],
    baseline_unknown_ids: [],
    action_results: [training, ...remaining],
    pareto_action_ids: ["BORROW_TWO_LAPTOPS"],
    highest_leverage_action_id: null,
    ranking_explanation: "No remaining complete action unlocks another initiative.",
    uncertainty_could_change_winner: false,
  };
}
