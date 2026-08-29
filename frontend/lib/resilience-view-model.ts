import {
  parseFrontierResponse,
  parseRecompileResponse,
  parseStressResponse,
  perturbationBindingsMatch,
  ResilienceContractError,
} from "./resilience-contract";
import type {
  FrontierRunRequest,
  PerturbationBinding,
  RecoveryRunRequest,
  ResilienceSourceSummary,
  ResilienceTaskState,
  StressRunRequest,
} from "./resilience-types";

export const NON_OPERATIONAL_EVIDENCE_NOTICE =
  "Counterfactual receipts are analytical evidence only. They do not create, apply, sequence, or update community or Project state.";

export function technicalDisclosureState(judgeMode: boolean): {
  instanceKey: "judge-forced-open" | "normal-default-closed";
  forcedOpen: true | undefined;
} {
  return judgeMode
    ? { instanceKey: "judge-forced-open", forcedOpen: true }
    : { instanceKey: "normal-default-closed", forcedOpen: undefined };
}

export type ViewPhase = "idle" | "loading" | "error" | "invalid" | "ready";

interface BaseViewModel {
  phase: ViewPhase;
  liveSummary: string;
}

export interface StressOutcomeView {
  perturbationId: string;
  label: string;
  typeLabel: string;
  criticality: "RESILIENT" | "DEGRADED" | "CRITICAL" | "UNKNOWN";
  statusLabel: string;
  meaning: string;
  beforeAfter: string;
  binding: PerturbationBinding;
  technical: Array<{ label: string; value: string }>;
}

export interface StressViewModel extends BaseViewModel {
  headline: string;
  description: string;
  ratioLabel: string;
  catalogueSize: number;
  decisiveCount: number;
  resilientCount: number;
  degradedCount: number;
  criticalCount: number;
  unknownCount: number;
  outcomes: StressOutcomeView[];
  technical: Array<{ label: string; value: string }>;
}

export interface RecoveryRoleView {
  roleId: string;
  roleLabel: string;
  beforePerson: string;
  afterPerson: string;
  changed: boolean;
  summary: string;
}

export interface RecoveryViewModel extends BaseViewModel {
  headline: string;
  description: string;
  statusLabel: string;
  stage1: { status: string; claim: string } | null;
  stage2: { status: string; claim: string } | null;
  minimumLabel: string;
  burdenLabel: string;
  roleDiffs: RecoveryRoleView[];
  technical: Array<{ label: string; value: string }>;
}

export interface FrontierActionView {
  actionId: string;
  name: string;
  costLabel: string;
  applicable: boolean;
  applicabilityLabel: string;
  newlyFeasible: string[];
  lostFeasible: string[];
  unknown: string[];
  coverageLabel: string;
  isPareto: boolean;
  isHighestLeverage: boolean;
  explanation: string;
  technical: Array<{ label: string; value: string }>;
}

export interface FrontierViewModel extends BaseViewModel {
  headline: string;
  description: string;
  baselineBuildable: string[];
  baselineBlocked: string[];
  baselineUnknown: string[];
  highestLeverageLabel: string;
  uncertainty: boolean;
  actions: FrontierActionView[];
  technical: Array<{ label: string; value: string }>;
}

function humanize(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function emptyStress(phase: ViewPhase, summary: string): StressViewModel {
  return {
    phase,
    liveSummary: summary,
    headline: phase === "loading" ? "Testing resilience…" : "Test a buildable initiative",
    description:
      phase === "error" || phase === "invalid"
        ? summary
        : "Choose a buildable initiative to test every returned one-fact disruption.",
    ratioLabel: "—",
    catalogueSize: 0,
    decisiveCount: 0,
    resilientCount: 0,
    degradedCount: 0,
    criticalCount: 0,
    unknownCount: 0,
    outcomes: [],
    technical: [],
  };
}

function invalidMessage(error: unknown): string {
  return error instanceof ResilienceContractError
    ? "Returned evidence did not match this source and was withheld. Run the analysis again."
    : "The returned evidence could not be read safely. Run the analysis again.";
}

function sourceMatches(
  source: ResilienceSourceSummary,
  request: {
    sourceStateId: string;
    sourceContentHash?: string;
    catalystPath: readonly string[];
  },
): boolean {
  const currentPath = source.catalystPath.map((item) => item.id);
  return (
    source.stateId === request.sourceStateId &&
    currentPath.length === request.catalystPath.length &&
    currentPath.every((item, index) => item === request.catalystPath[index]) &&
    (source.contentHash === undefined || source.contentHash === request.sourceContentHash)
  );
}

export function buildStressViewModel(
  task: ResilienceTaskState<StressRunRequest>,
  source: ResilienceSourceSummary,
): StressViewModel {
  if (task.loading) return emptyStress("loading", "Stress test in progress.");
  if (task.error) return emptyStress("error", `${task.error.code}: ${task.error.message}`);
  if (task.result === null) return emptyStress("idle", "No stress result yet.");
  if (task.request === null || !sourceMatches(source, task.request)) {
    return emptyStress("invalid", "The stress result belongs to a different source and was withheld.");
  }

  try {
    const result = parseStressResponse(task.result, task.request);
    const resilientCount = result.outcomes.filter((item) => item.criticality === "RESILIENT").length;
    const degradedCount = result.outcomes.filter((item) => item.criticality === "DEGRADED").length;
    const criticalCount = result.outcomes.filter((item) => item.criticality === "CRITICAL").length;
    const ratioLabel = result.resilience_ratio === null
      ? "No decisive ratio"
      : `${Math.round(result.resilience_ratio * 100)}%`;
    const allCritical = criticalCount === result.catalogue_size;
    const headline = result.decisive_count === 0
      ? "The test remains unresolved"
      : allCritical
        ? "Every tested disruption stops this plan"
        : `${result.survived_count} of ${result.decisive_count} decisive tests stay buildable`;
    const description = result.unknown_count > 0
      ? `${result.unknown_count} outcome${result.unknown_count === 1 ? " is" : "s are"} UNKNOWN and excluded from the ratio.`
      : `${result.catalogue_size} one-fact disruption${result.catalogue_size === 1 ? " was" : "s were"} tested against the same proved source.`;
    const outcomes = result.outcomes.map((outcome): StressOutcomeView => {
      const perturbation = outcome.perturbation;
      const typeLabel = perturbation.type === "MAKE_ASSIGNED_PERSON_UNAVAILABLE"
        ? "Person availability"
        : perturbation.type === "MAKE_SELECTED_VENUE_UNAVAILABLE"
          ? "Venue availability"
          : "Resource availability";
      const beforeAfter = perturbation.type === "REDUCE_AVAILABLE_RESOURCE"
        ? `Before: ${perturbation.before_quantity} available. After: ${perturbation.after_quantity}; ${perturbation.required_quantity} required.`
        : `Before: available at ${perturbation.before_available_slots.map(humanize).join(", ")}. After: unavailable.`;
      const meaning = outcome.criticality === "RESILIENT"
        ? "The same people, venue, time and burden still work."
        : outcome.criticality === "DEGRADED"
          ? `A feasible plan remains, but ${outcome.assignment_changes ?? 0} assignment${outcome.assignment_changes === 1 ? " changes" : "s change"} or another meaningful plan fact differs.`
          : outcome.criticality === "CRITICAL"
            ? "No feasible plan remains under this single disruption."
            : "The solver did not resolve this disruption; no survival or failure claim is made.";
      return {
        perturbationId: outcome.perturbation_id,
        label: perturbation.label,
        typeLabel,
        criticality: outcome.criticality,
        statusLabel: humanize(outcome.criticality),
        meaning,
        beforeAfter,
        binding: perturbation,
        technical: [
          { label: "Perturbation ID", value: outcome.perturbation_id },
          { label: "Scenario receipt", value: outcome.scenario_state_id },
          { label: "Solver status", value: outcome.status },
          { label: "Branches", value: String(outcome.solver_stats.branches) },
          { label: "Conflicts", value: String(outcome.solver_stats.conflicts) },
          { label: "Wall time", value: String(outcome.solver_stats.wall_time_seconds) },
          { label: "Validated outcome JSON", value: JSON.stringify(outcome) },
        ],
      };
    });
    return {
      phase: "ready",
      liveSummary: `${humanize(result.initiative_id)} stress test complete. ${headline}.`,
      headline,
      description,
      ratioLabel,
      catalogueSize: result.catalogue_size,
      decisiveCount: result.decisive_count,
      resilientCount,
      degradedCount,
      criticalCount,
      unknownCount: result.unknown_count,
      outcomes,
      technical: [
        { label: "Source state", value: result.source_state_id },
        { label: "Source content hash", value: result.source_content_hash },
        { label: "Initiative ID", value: result.initiative_id },
        { label: "Baseline burden", value: String(result.baseline_result.objective_value) },
        { label: "Validated response JSON", value: JSON.stringify(result) },
      ],
    };
  } catch (error) {
    return emptyStress("invalid", invalidMessage(error));
  }
}

function emptyRecovery(phase: ViewPhase, summary: string): RecoveryViewModel {
  return {
    phase,
    liveSummary: summary,
    headline: phase === "loading" ? "Finding minimum disruption…" : "Select a returned disruption",
    description:
      phase === "error" || phase === "invalid"
        ? summary
        : "Recovery starts only from a disruption returned by the current stress test.",
    statusLabel: "Not run",
    stage1: null,
    stage2: null,
    minimumLabel: "Not proven",
    burdenLabel: "Not available",
    roleDiffs: [],
    technical: [],
  };
}

export function buildRecoveryViewModel(
  task: ResilienceTaskState<RecoveryRunRequest>,
  source: ResilienceSourceSummary,
  currentStress: StressViewModel,
): RecoveryViewModel {
  if (task.loading) return emptyRecovery("loading", "Recovery analysis in progress.");
  if (task.error) return emptyRecovery("error", `${task.error.code}: ${task.error.message}`);
  if (task.result === null) return emptyRecovery("idle", "No recovery result yet.");
  if (task.request === null || !sourceMatches(source, task.request)) {
    return emptyRecovery("invalid", "The recovery result belongs to a different source and was withheld.");
  }
  const selectedStressOutcome = currentStress.phase === "ready"
    ? currentStress.outcomes.find((item) => item.perturbationId === task.request?.perturbationId)
    : undefined;
  if (
    selectedStressOutcome === undefined ||
    !perturbationBindingsMatch(selectedStressOutcome.binding, task.request.perturbationBinding)
  ) {
    return emptyRecovery(
      "invalid",
      "The recovery result is not bound to a disruption in the current stress catalogue and was withheld.",
    );
  }

  try {
    const result = parseRecompileResponse(task.result, task.request);
    const feasible = result.status === "OPTIMAL" || result.status === "FEASIBLE";
    const headline = feasible
      ? "Minimum-disruption recovery found"
      : result.status === "INFEASIBLE"
        ? "No feasible recovery was found"
        : "Recovery remains unresolved";
    const description = result.status === "UNKNOWN"
      ? "The proof stopped without converting uncertainty into a minimum or a recovery witness."
      : result.explanation;
    const roleDiffs = result.role_diffs.map((item): RecoveryRoleView => ({
      roleId: item.role_id,
      roleLabel: humanize(item.role_id),
      beforePerson: humanize(item.before_person_id),
      afterPerson: humanize(item.after_person_id),
      changed: item.changed,
      summary: item.changed
        ? `${humanize(item.before_person_id)} → ${humanize(item.after_person_id)}`
        : `${humanize(item.before_person_id)} preserved`,
    }));
    return {
      phase: "ready",
      liveSummary: `${headline}. ${result.explanation}`,
      headline,
      description,
      statusLabel: humanize(result.status),
      stage1: {
        status: humanize(result.stage1_status),
        claim: result.minimum_proven
          ? `Minimum proven: ${result.minimum_assignment_changes} changed assignment${result.minimum_assignment_changes === 1 ? "" : "s"}.`
          : "No minimum is claimed.",
      },
      stage2: result.stage2_status === null
        ? null
        : {
            status: humanize(result.stage2_status),
            claim: result.secondary_burden_optimal
              ? "Secondary burden is proven optimal."
              : "A feasible secondary result is shown without an optimality claim.",
          },
      minimumLabel: result.minimum_proven
        ? `${result.minimum_assignment_changes} assignment${result.minimum_assignment_changes === 1 ? "" : "s"}`
        : "Not proven",
      burdenLabel: result.new_result?.objective_value === null || result.new_result === null
        ? "Not available"
        : String(result.new_result.objective_value),
      roleDiffs,
      technical: [
        { label: "Source state", value: result.source_state_id },
        { label: "Perturbation ID", value: result.perturbation_id },
        { label: "Scenario receipt", value: result.scenario_state_id },
        { label: "Stage 1 branches", value: String(result.stage1_solver_stats.branches) },
        ...(result.stage2_solver_stats
          ? [{ label: "Stage 2 branches", value: String(result.stage2_solver_stats.branches) }]
          : []),
        { label: "Validated response JSON", value: JSON.stringify(result) },
      ],
    };
  } catch (error) {
    return emptyRecovery("invalid", invalidMessage(error));
  }
}

function emptyFrontier(phase: ViewPhase, summary: string): FrontierViewModel {
  return {
    phase,
    liveSummary: summary,
    headline: phase === "loading" ? "Comparing one-action possibilities…" : "Compare capability options",
    description:
      phase === "error" || phase === "invalid"
        ? summary
        : "Each action is assessed independently from the same source; this is not a sequence.",
    baselineBuildable: [],
    baselineBlocked: [],
    baselineUnknown: [],
    highestLeverageLabel: "Not evaluated",
    uncertainty: false,
    actions: [],
    technical: [],
  };
}

export function buildFrontierViewModel(
  task: ResilienceTaskState<FrontierRunRequest>,
  source: ResilienceSourceSummary,
): FrontierViewModel {
  if (task.loading) return emptyFrontier("loading", "Capability frontier analysis in progress.");
  if (task.error) return emptyFrontier("error", `${task.error.code}: ${task.error.message}`);
  if (task.result === null) return emptyFrontier("idle", "No capability frontier result yet.");
  if (task.request === null || !sourceMatches(source, task.request)) {
    return emptyFrontier("invalid", "The frontier result belongs to a different source and was withheld.");
  }

  try {
    const result = parseFrontierResponse(task.result, task.request);
    const actionById = new Map(result.action_results.map((item) => [item.action_id, item]));
    const highest = result.highest_leverage_action_id === null
      ? null
      : actionById.get(result.highest_leverage_action_id);
    const headline = result.uncertainty_could_change_winner
      ? "Highest leverage is withheld"
      : highest
        ? `${highest.action_name} has the highest leverage`
        : "No action has a proven positive unlock";
    const actions = result.action_results.map((item): FrontierActionView => ({
      actionId: item.action_id,
      name: item.action_name,
      costLabel: `${item.cost} cost point${item.cost === 1 ? "" : "s"}`,
      applicable: item.applicable,
      applicabilityLabel: item.applicable ? "Applicable" : "Not applicable from this source",
      newlyFeasible: item.newly_feasible_initiatives.map(humanize),
      lostFeasible: item.lost_feasible_initiatives.map(humanize),
      unknown: item.unknown_initiatives.map(humanize),
      coverageLabel: item.decisive_coverage_complete
        ? "Complete decisive coverage"
        : item.applicable
          ? "Coverage includes UNKNOWN"
          : "Not evaluated",
      isPareto: result.pareto_action_ids.includes(item.action_id),
      isHighestLeverage: result.highest_leverage_action_id === item.action_id,
      explanation: item.explanation,
      technical: [
        { label: "Action ID", value: item.action_id },
        ...(item.scenario_state_id ? [{ label: "Scenario receipt", value: item.scenario_state_id }] : []),
        ...(item.scenario_content_hash ? [{ label: "Scenario hash", value: item.scenario_content_hash }] : []),
        { label: "Validated action JSON", value: JSON.stringify(item) },
      ],
    }));
    return {
      phase: "ready",
      liveSummary: `${headline}. ${result.ranking_explanation}`,
      headline,
      description: result.ranking_explanation,
      baselineBuildable: result.baseline_buildable_ids.map(humanize),
      baselineBlocked: result.baseline_blocked_ids.map(humanize),
      baselineUnknown: result.baseline_unknown_ids.map(humanize),
      highestLeverageLabel: highest?.action_name ?? (result.uncertainty_could_change_winner ? "Withheld due to uncertainty" : "None"),
      uncertainty: result.uncertainty_could_change_winner,
      actions,
      technical: [
        { label: "Source state", value: result.source_state_id },
        { label: "Validated response JSON", value: JSON.stringify(result) },
      ],
    };
  } catch (error) {
    return emptyFrontier("invalid", invalidMessage(error));
  }
}
