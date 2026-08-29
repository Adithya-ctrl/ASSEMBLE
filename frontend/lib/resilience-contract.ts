import {
  SOLVER_STATUSES,
  STRESS_CRITICALITIES,
  type CapabilityFrontierResponse,
  type FrontierActionResult,
  type FrontierRunRequest,
  type PerturbationSpec,
  type RecompileResponse,
  type RecoveryRunRequest,
  type ResilienceAnalysisResult,
  type ResilienceSolverStatus,
  type ResilienceStateDiff,
  type StressOutcome,
  type StressRunRequest,
  type StressTestResponse,
} from "./resilience-types";

type JsonRecord = Record<string, unknown>;

const HASH = /^[0-9a-f]{64}$/;
const OPERATIONAL_MAPPING_KEYS = new Set([
  "parentstateid",
  "predecessorstateid",
  "successorstateid",
  "operationalstateid",
  "appliedstateid",
  "project",
  "projects",
  "projectid",
  "projectstateid",
  "sourceplanid",
  "verifiedstateid",
  "applyurl",
  "createprojecturl",
]);
const FEASIBLE_STATUSES = new Set<ResilienceSolverStatus>(["OPTIMAL", "FEASIBLE"]);

export class ResilienceContractError extends Error {
  readonly code = "RESILIENCE_RESPONSE_CONTRACT_ERROR";

  constructor(readonly issue: string) {
    super(`Resilience response was withheld: ${issue}`);
    this.name = "ResilienceContractError";
  }
}

function fail(path: string, message: string): never {
  throw new ResilienceContractError(`${path} ${message}`);
}

function record(value: unknown, path: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    fail(path, "must be an object.");
  }
  return value as JsonRecord;
}

function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) fail(path, "must be an array.");
  return value;
}

function stringValue(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) fail(path, "must be a non-empty string.");
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  return value === null ? null : stringValue(value, path);
}

function booleanValue(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") fail(path, "must be a boolean.");
  return value;
}

function nullableBoolean(value: unknown, path: string): boolean | null {
  return value === null ? null : booleanValue(value, path);
}

function numberValue(value: unknown, path: string, minimum = 0): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum) {
    fail(path, `must be a finite number greater than or equal to ${minimum}.`);
  }
  return value;
}

function integerValue(value: unknown, path: string, minimum = 0): number {
  const parsed = numberValue(value, path, minimum);
  if (!Number.isInteger(parsed)) fail(path, "must be an integer.");
  return parsed;
}

function nullableInteger(value: unknown, path: string, minimum = 0): number | null {
  return value === null ? null : integerValue(value, path, minimum);
}

function signedNullableInteger(value: unknown, path: string): number | null {
  if (value === null) return null;
  if (typeof value !== "number" || !Number.isInteger(value)) fail(path, "must be an integer or null.");
  return value;
}

function stringArray(value: unknown, path: string, unique = false): string[] {
  const values = array(value, path).map((item, index) => stringValue(item, `${path}[${index}]`));
  if (unique && new Set(values).size !== values.length) fail(path, "must not contain duplicates.");
  return values;
}

function statusValue(value: unknown, path: string): ResilienceSolverStatus {
  if (typeof value !== "string" || !(SOLVER_STATUSES as readonly string[]).includes(value)) {
    fail(path, "contains an unsupported solver status.");
  }
  return value as ResilienceSolverStatus;
}

function sameOrdered(actual: readonly string[], expected: readonly string[]): boolean {
  return actual.length === expected.length && actual.every((item, index) => item === expected[index]);
}

function sorted(values: Iterable<string>): string[] {
  return [...values].sort((left, right) => left.localeCompare(right));
}

function assertExactSet(actual: readonly string[], expected: readonly string[], path: string): void {
  if (!sameOrdered(sorted(actual), sorted(expected))) fail(path, "does not match the expected identifiers.");
}

function assertNoOperationalMapping(value: unknown, path = "response", seen = new WeakSet<object>()): void {
  if (typeof value !== "object" || value === null) return;
  if (seen.has(value)) fail(path, "must be an acyclic JSON value.");
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertNoOperationalMapping(item, `${path}[${index}]`, seen));
  } else {
    for (const [key, item] of Object.entries(value)) {
      const normalizedKey = key.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
      const stateTransitionTerm =
        "(?:parent|predecessor|successor|applied|verified|mapped|materialized|created)";
      const mapsOperationalState =
        normalizedKey.includes("operational") ||
        new RegExp(`${stateTransitionTerm}.*state|state.*${stateTransitionTerm}`).test(normalizedKey);
      const mapsOperationalAction =
        /(?:apply|create|materialize).*(?:url|href|endpoint|route)/.test(normalizedKey);
      if (
        OPERATIONAL_MAPPING_KEYS.has(normalizedKey) ||
        normalizedKey.includes("project") ||
        mapsOperationalState ||
        mapsOperationalAction
      ) {
        fail(`${path}.${key}`, "must not map analytical evidence to operational lineage or Projects.");
      }
      assertNoOperationalMapping(item, `${path}.${key}`, seen);
    }
  }
  seen.delete(value);
}

function assertHash(value: unknown, path: string): string {
  const parsed = stringValue(value, path);
  if (!HASH.test(parsed)) fail(path, "must be a lowercase 64-character content hash.");
  return parsed;
}

function validateSolverStats(value: unknown, path: string): void {
  const stats = record(value, path);
  integerValue(stats.branches, `${path}.branches`);
  integerValue(stats.conflicts, `${path}.conflicts`);
  numberValue(stats.wall_time_seconds, `${path}.wall_time_seconds`);
}

function validateBlockingSets(value: unknown, path: string): number {
  const blockers = array(value, path);
  blockers.forEach((item, index) => {
    const blocker = record(item, `${path}[${index}]`);
    if (stringArray(blocker.groups, `${path}[${index}].groups`).length === 0) {
      fail(`${path}[${index}].groups`, "must identify at least one requirement group.");
    }
    if (array(blocker.facts, `${path}[${index}].facts`).length === 0) {
      fail(`${path}[${index}].facts`, "must include at least one factual blocker.");
    }
    booleanValue(
      blocker.restored_feasibility_when_relaxed,
      `${path}[${index}].restored_feasibility_when_relaxed`,
    );
  });
  return blockers.length;
}

function validateAnalysisResult(
  value: unknown,
  path: string,
  expectedInitiative?: string,
  expectedStatus?: ResilienceSolverStatus,
): ResilienceAnalysisResult {
  const result = record(value, path);
  const initiativeId = stringValue(result.initiative_id, `${path}.initiative_id`);
  const status = statusValue(result.status, `${path}.status`);
  const objective = nullableInteger(result.objective_value, `${path}.objective_value`);
  const assignments = array(result.assignments, `${path}.assignments`);
  const trace = array(result.assembly_trace, `${path}.assembly_trace`);
  validateSolverStats(result.solver_stats, `${path}.solver_stats`);

  const assignmentRoleIds = assignments.map((item, index) => {
    const assignment = record(item, `${path}.assignments[${index}]`);
    const roleId = stringValue(
      assignment.role_instance_id,
      `${path}.assignments[${index}].role_instance_id`,
    );
    stringValue(assignment.person_id, `${path}.assignments[${index}].person_id`);
    return roleId;
  });
  if (new Set(assignmentRoleIds).size !== assignmentRoleIds.length) {
    fail(`${path}.assignments`, "must contain unique role-instance witnesses.");
  }
  trace.forEach((item, index) => record(item, `${path}.assembly_trace[${index}]`));

  const feasible = FEASIBLE_STATUSES.has(status);
  if (feasible && (objective === null || assignments.length === 0 || trace.length === 0)) {
    fail(path, "claims feasibility without a complete objective, assignment witness, and trace.");
  }
  if (!feasible && (objective !== null || assignments.length > 0 || trace.length > 0)) {
    fail(path, "attaches an objective or witness to an INFEASIBLE or UNKNOWN result.");
  }
  if (expectedInitiative !== undefined && initiativeId !== expectedInitiative) {
    fail(`${path}.initiative_id`, "does not match the bound initiative.");
  }
  if (expectedStatus !== undefined && status !== expectedStatus) {
    fail(`${path}.status`, "does not match the enclosing result status.");
  }
  return result as unknown as ResilienceAnalysisResult;
}

function validatePerturbation(
  value: unknown,
  path: string,
  expectedInitiative: string,
  expectedHash?: string,
): PerturbationSpec {
  const item = record(value, path);
  stringValue(item.id, `${path}.id`);
  const initiativeId = stringValue(item.initiative_id, `${path}.initiative_id`);
  const targetId = stringValue(item.target_id, `${path}.target_id`);
  const label = stringValue(item.label, `${path}.label`);
  const sourceHash = assertHash(item.source_content_hash, `${path}.source_content_hash`);
  const type = stringValue(item.type, `${path}.type`);
  if (label.length > 160) fail(`${path}.label`, "exceeds the 160-character contract limit.");
  if (initiativeId !== expectedInitiative) fail(`${path}.initiative_id`, "does not match the bound initiative.");
  if (expectedHash !== undefined && sourceHash !== expectedHash) {
    fail(`${path}.source_content_hash`, "does not match the bound source content.");
  }

  if (type === "MAKE_ASSIGNED_PERSON_UNAVAILABLE" || type === "MAKE_SELECTED_VENUE_UNAVAILABLE") {
    const before = stringArray(item.before_available_slots, `${path}.before_available_slots`, true);
    const after = stringArray(item.after_available_slots, `${path}.after_available_slots`, true);
    if (before.length === 0 || after.length !== 0) {
      fail(path, "must clear exactly one selected block's non-empty availability.");
    }
  } else if (type === "REDUCE_AVAILABLE_RESOURCE") {
    const requirementId = stringValue(item.requirement_id, `${path}.requirement_id`);
    const required = integerValue(item.required_quantity, `${path}.required_quantity`, 1);
    const before = integerValue(item.before_quantity, `${path}.before_quantity`);
    const after = integerValue(item.after_quantity, `${path}.after_quantity`);
    if (targetId !== requirementId || before < required || after !== required - 1 || after === before) {
      fail(path, "does not describe the exact one-fact resource reduction.");
    }
  } else {
    fail(`${path}.type`, "contains an unsupported perturbation type.");
  }
  return item as unknown as PerturbationSpec;
}

function perturbationFingerprint(value: PerturbationSpec): string {
  const base = {
    id: value.id,
    type: value.type,
    initiative_id: value.initiative_id,
    target_id: value.target_id,
    label: value.label,
    source_content_hash: value.source_content_hash,
  };
  return value.type === "REDUCE_AVAILABLE_RESOURCE"
    ? JSON.stringify({
        ...base,
        requirement_id: value.requirement_id,
        required_quantity: value.required_quantity,
        before_quantity: value.before_quantity,
        after_quantity: value.after_quantity,
      })
    : JSON.stringify({
        ...base,
        before_available_slots: value.before_available_slots,
        after_available_slots: value.after_available_slots,
      });
}

export function perturbationBindingsMatch(
  left: PerturbationSpec,
  right: PerturbationSpec,
): boolean {
  return perturbationFingerprint(left) === perturbationFingerprint(right);
}

function validateStressOutcome(
  value: unknown,
  path: string,
  sourceStateId: string,
  initiativeId: string,
  sourceHash: string,
  baselineObjective: number,
  baselineRoleIds: ReadonlySet<string>,
): StressOutcome {
  const outcome = record(value, path);
  if (stringValue(outcome.source_state_id, `${path}.source_state_id`) !== sourceStateId) {
    fail(`${path}.source_state_id`, "does not match the stress response source.");
  }
  const perturbationId = stringValue(outcome.perturbation_id, `${path}.perturbation_id`);
  const scenarioId = stringValue(outcome.scenario_state_id, `${path}.scenario_state_id`);
  if (!scenarioId.startsWith("CF_STRESS_V1_") || scenarioId === sourceStateId) {
    fail(`${path}.scenario_state_id`, "is not a domain-separated stress receipt.");
  }
  const perturbation = validatePerturbation(
    outcome.perturbation,
    `${path}.perturbation`,
    initiativeId,
    sourceHash,
  );
  if (perturbation.id !== perturbationId) {
    fail(`${path}.perturbation_id`, "does not match its typed perturbation.");
  }

  const status = statusValue(outcome.status, `${path}.status`);
  const survived = nullableBoolean(outcome.survived, `${path}.survived`);
  const criticality = stringValue(outcome.criticality, `${path}.criticality`);
  if (!(STRESS_CRITICALITIES as readonly string[]).includes(criticality)) {
    fail(`${path}.criticality`, "contains an unsupported stress criticality.");
  }
  const objectiveValue = nullableInteger(outcome.objective_value, `${path}.objective_value`);
  const objectiveDelta = signedNullableInteger(outcome.objective_delta, `${path}.objective_delta`);
  const objectiveDegradation = nullableInteger(
    outcome.objective_degradation,
    `${path}.objective_degradation`,
  );
  const assignmentChanges = nullableInteger(outcome.assignment_changes, `${path}.assignment_changes`);
  const changedRoles = stringArray(outcome.changed_roles, `${path}.changed_roles`, true);
  const baselineVenue = stringValue(outcome.baseline_venue_id, `${path}.baseline_venue_id`);
  const afterVenue = nullableString(outcome.after_venue_id, `${path}.after_venue_id`);
  const baselineStart = stringValue(outcome.baseline_start_slot, `${path}.baseline_start_slot`);
  const afterStart = nullableString(outcome.after_start_slot, `${path}.after_start_slot`);
  const blockerCount = validateBlockingSets(outcome.blockers, `${path}.blockers`);
  validateSolverStats(outcome.solver_stats, `${path}.solver_stats`);

  if (FEASIBLE_STATUSES.has(status)) {
    if (survived !== true) fail(`${path}.survived`, "must be true for a feasible perturbation.");
    if (
      objectiveValue === null ||
      objectiveDelta === null ||
      objectiveDegradation === null ||
      assignmentChanges === null ||
      afterVenue === null ||
      afterStart === null
    ) {
      fail(path, "claims feasibility without complete before/after plan metrics.");
    }
    if (
      objectiveDelta !== objectiveValue - baselineObjective ||
      objectiveDegradation !== Math.max(0, objectiveDelta)
    ) {
      fail(path, "objective delta and degradation do not reconcile with the baseline.");
    }
    if (assignmentChanges !== changedRoles.length) {
      fail(path, "assignment changes do not match the complete changed-role list.");
    }
    if (changedRoles.some((roleId) => !baselineRoleIds.has(roleId))) {
      fail(`${path}.changed_roles`, "must refer only to roles in the complete baseline witness.");
    }
    if (blockerCount !== 0) fail(`${path}.blockers`, "must be empty for a feasible perturbation.");
    const unchanged =
      assignmentChanges === 0 &&
      afterVenue === baselineVenue &&
      afterStart === baselineStart &&
      objectiveDelta === 0;
    const expectedCriticality = unchanged ? "RESILIENT" : "DEGRADED";
    if (criticality !== expectedCriticality) {
      fail(`${path}.criticality`, "does not match the complete meaningful before/after plan.");
    }
  } else {
    if (
      objectiveValue !== null ||
      objectiveDelta !== null ||
      objectiveDegradation !== null ||
      assignmentChanges !== null ||
      changedRoles.length > 0 ||
      afterVenue !== null ||
      afterStart !== null
    ) {
      fail(path, "attaches plan metrics to a non-feasible perturbation.");
    }
    if (status === "INFEASIBLE" && (survived !== false || criticality !== "CRITICAL")) {
      fail(path, "must label an INFEASIBLE perturbation as failed and CRITICAL.");
    }
    if (status === "UNKNOWN" && (survived !== null || criticality !== "UNKNOWN")) {
      fail(path, "must preserve an unresolved perturbation as non-decisive UNKNOWN.");
    }
  }
  return outcome as unknown as StressOutcome;
}

function validateBoundRequest(request: StressRunRequest): void {
  stringValue(request.sourceStateId, "request.sourceStateId");
  stringValue(request.initiativeId, "request.initiativeId");
  const path = [...request.catalystPath];
  if (path.length > 2 || new Set(path).size !== path.length || path.some((item) => !item)) {
    fail("request.catalystPath", "must contain zero to two unique action IDs.");
  }
  if (request.sourceContentHash !== undefined && !HASH.test(request.sourceContentHash)) {
    fail("request.sourceContentHash", "must be a lowercase 64-character content hash.");
  }
}

export function parseStressResponse(payload: unknown, request: StressRunRequest): StressTestResponse {
  validateBoundRequest(request);
  assertNoOperationalMapping(payload);
  const response = record(payload, "stress");
  const initiativeId = stringValue(response.initiative_id, "stress.initiative_id");
  const sourceStateId = stringValue(response.source_state_id, "stress.source_state_id");
  const sourceHash = assertHash(response.source_content_hash, "stress.source_content_hash");
  if (initiativeId !== request.initiativeId) fail("stress.initiative_id", "does not match the request.");
  if (sourceStateId !== request.sourceStateId) fail("stress.source_state_id", "does not match the request.");
  if (request.sourceContentHash !== undefined && sourceHash !== request.sourceContentHash) {
    fail("stress.source_content_hash", "does not match the request binding.");
  }
  const baseline = validateAnalysisResult(
    response.baseline_result,
    "stress.baseline_result",
    initiativeId,
  );
  if (!FEASIBLE_STATUSES.has(baseline.status)) fail("stress.baseline_result.status", "must be feasible.");
  if (baseline.objective_value === null) {
    fail("stress.baseline_result.objective_value", "must be present for a feasible baseline.");
  }

  const outcomes = array(response.outcomes, "stress.outcomes").map((item, index) =>
    validateStressOutcome(
      item,
      `stress.outcomes[${index}]`,
      sourceStateId,
      initiativeId,
      sourceHash,
      baseline.objective_value as number,
      new Set(baseline.assignments.map((assignment) => assignment.role_instance_id)),
    ),
  );
  const catalogueSize = integerValue(response.catalogue_size, "stress.catalogue_size", 1);
  if (catalogueSize > 20 || catalogueSize !== outcomes.length) {
    fail("stress.catalogue_size", "must equal the complete bounded outcome catalogue.");
  }
  const survived = integerValue(response.survived_count, "stress.survived_count");
  const failed = integerValue(response.failed_count, "stress.failed_count");
  const unknown = integerValue(response.unknown_count, "stress.unknown_count");
  const decisive = integerValue(response.decisive_count, "stress.decisive_count");
  const actualSurvived = outcomes.filter((item) => item.survived === true).length;
  const actualFailed = outcomes.filter((item) => item.survived === false).length;
  const actualUnknown = outcomes.filter((item) => item.survived === null).length;
  if (
    survived !== actualSurvived ||
    failed !== actualFailed ||
    unknown !== actualUnknown ||
    decisive !== survived + failed ||
    catalogueSize !== decisive + unknown
  ) {
    fail("stress", "count fields do not match the complete outcome catalogue.");
  }
  const ratio = response.resilience_ratio === null
    ? null
    : numberValue(response.resilience_ratio, "stress.resilience_ratio");
  if (ratio !== null && ratio > 1) fail("stress.resilience_ratio", "must be between zero and one.");
  if ((ratio === null) !== (decisive === 0)) {
    fail("stress.resilience_ratio", "must be null exactly when there are no decisive outcomes.");
  }
  if (ratio !== null && Math.abs(ratio - survived / decisive) > 1e-12) {
    fail("stress.resilience_ratio", "does not match survived divided by decisive outcomes.");
  }
  const perturbationIds = outcomes.map((item) => item.perturbation_id);
  const scenarioIds = outcomes.map((item) => item.scenario_state_id);
  if (new Set(perturbationIds).size !== outcomes.length || new Set(scenarioIds).size !== outcomes.length) {
    fail("stress.outcomes", "must contain unique perturbation and scenario receipts.");
  }
  const criticalIds = stringArray(
    response.critical_perturbation_ids,
    "stress.critical_perturbation_ids",
    true,
  );
  const expectedCritical = outcomes
    .filter((item) => item.criticality === "CRITICAL")
    .map((item) => item.perturbation_id);
  if (!sameOrdered(criticalIds, expectedCritical)) {
    fail("stress.critical_perturbation_ids", "does not match ordered CRITICAL outcomes.");
  }
  return response as unknown as StressTestResponse;
}

export function parseRecompileResponse(
  payload: unknown,
  request: RecoveryRunRequest,
): RecompileResponse {
  validateBoundRequest(request);
  stringValue(request.perturbationId, "request.perturbationId");
  assertNoOperationalMapping(payload);
  const response = record(payload, "recovery");
  const initiativeId = stringValue(response.initiative_id, "recovery.initiative_id");
  const sourceStateId = stringValue(response.source_state_id, "recovery.source_state_id");
  const perturbationId = stringValue(response.perturbation_id, "recovery.perturbation_id");
  const scenarioId = stringValue(response.scenario_state_id, "recovery.scenario_state_id");
  if (initiativeId !== request.initiativeId || sourceStateId !== request.sourceStateId) {
    fail("recovery", "does not match the bound source and initiative.");
  }
  if (perturbationId !== request.perturbationId) {
    fail("recovery.perturbation_id", "does not match the selected returned perturbation.");
  }
  if (!scenarioId.startsWith("CF_STRESS_V1_") || scenarioId === sourceStateId) {
    fail("recovery.scenario_state_id", "is not a domain-separated stress receipt.");
  }
  const perturbation = validatePerturbation(
    response.perturbation,
    "recovery.perturbation",
    initiativeId,
    request.sourceContentHash,
  );
  if (perturbation.id !== perturbationId) {
    fail("recovery.perturbation", "does not match the selected perturbation ID.");
  }
  const binding = validatePerturbation(
    request.perturbationBinding,
    "request.perturbationBinding",
    initiativeId,
    request.sourceContentHash,
  );
  if (
    binding.id !== request.perturbationId ||
    !perturbationBindingsMatch(binding, perturbation)
  ) {
    fail("recovery.perturbation", "does not match the exact returned perturbation binding.");
  }

  const status = statusValue(response.status, "recovery.status");
  const stage1 = statusValue(response.stage1_status, "recovery.stage1_status");
  const stage2 = response.stage2_status === null
    ? null
    : statusValue(response.stage2_status, "recovery.stage2_status");
  validateSolverStats(response.stage1_solver_stats, "recovery.stage1_solver_stats");
  if ((response.stage2_solver_stats === null) !== (stage2 === null)) {
    fail("recovery.stage2_solver_stats", "must be present exactly when Stage 2 ran.");
  }
  if (stage2 !== null) validateSolverStats(response.stage2_solver_stats, "recovery.stage2_solver_stats");
  const minimumProven = booleanValue(response.minimum_proven, "recovery.minimum_proven");
  const secondaryOptimal = booleanValue(
    response.secondary_burden_optimal,
    "recovery.secondary_burden_optimal",
  );
  const minimum = nullableInteger(
    response.minimum_assignment_changes,
    "recovery.minimum_assignment_changes",
  );
  if (minimumProven !== (stage1 === "OPTIMAL") || (minimumProven && minimum === null)) {
    fail("recovery.minimum_proven", "requires an OPTIMAL Stage 1 and a proven scalar.");
  }
  if (!minimumProven && minimum !== null) {
    fail("recovery.minimum_assignment_changes", "must be null when Stage 1 is not proven optimal.");
  }
  if ((stage1 === "FEASIBLE" || stage1 === "UNKNOWN") && (status !== "UNKNOWN" || stage2 !== null)) {
    fail("recovery", "must fail closed to UNKNOWN without Stage 2 after a non-optimal Stage 1.");
  }
  if (stage1 === "INFEASIBLE" && (status !== "INFEASIBLE" || stage2 !== null)) {
    fail("recovery", "must stop as INFEASIBLE after Stage 1.");
  }
  if (stage1 === "OPTIMAL" && stage2 === null) fail("recovery.stage2_status", "is required after Stage 1 OPTIMAL.");
  if (secondaryOptimal !== (stage2 === "OPTIMAL")) {
    fail("recovery.secondary_burden_optimal", "may be true only for an OPTIMAL Stage 2.");
  }
  if (stage2 !== null && status !== stage2) fail("recovery.status", "must match the Stage 2 status.");

  const roleDiffs = array(response.role_diffs, "recovery.role_diffs").map((item, index) => {
    const diff = record(item, `recovery.role_diffs[${index}]`);
    const before = stringValue(diff.before_person_id, `recovery.role_diffs[${index}].before_person_id`);
    const after = stringValue(diff.after_person_id, `recovery.role_diffs[${index}].after_person_id`);
    const changed = booleanValue(diff.changed, `recovery.role_diffs[${index}].changed`);
    stringValue(diff.role_id, `recovery.role_diffs[${index}].role_id`);
    if (changed !== (before !== after)) fail(`recovery.role_diffs[${index}].changed`, "does not match before/after people.");
    return diff;
  });
  const changedAssignments = nullableInteger(response.changed_assignments, "recovery.changed_assignments");
  const preservedAssignments = nullableInteger(
    response.preserved_assignments,
    "recovery.preserved_assignments",
  );
  const feasible = FEASIBLE_STATUSES.has(status);
  if (feasible !== (response.new_result !== null)) {
    fail("recovery.new_result", "must be present exactly for a feasible recovery.");
  }
  if (!feasible) {
    if (roleDiffs.length > 0 || changedAssignments !== null || preservedAssignments !== null) {
      fail("recovery", "must not expose assignment claims for INFEASIBLE or UNKNOWN recovery.");
    }
  } else {
    if (!minimumProven) fail("recovery", "cannot expose a feasible witness without a proven minimum.");
    const newResult = validateAnalysisResult(
      response.new_result,
      "recovery.new_result",
      initiativeId,
      status,
    );
    const roleIds = roleDiffs.map((item) => stringValue(item.role_id, "recovery.role_diffs.role_id"));
    if (new Set(roleIds).size !== roleIds.length) fail("recovery.role_diffs", "must contain unique roles.");
    const changed = roleDiffs.filter((item) => item.changed === true).length;
    if (
      changedAssignments !== changed ||
      preservedAssignments !== roleDiffs.length - changed ||
      minimum !== changed
    ) {
      fail("recovery", "assignment counts do not match the complete role diff and proven minimum.");
    }
    const assignmentRoles = newResult.assignments.map((item) => item.role_instance_id);
    if (!sameOrdered(assignmentRoles, roleIds)) {
      fail("recovery.new_result.assignments", "does not match the ordered role diff.");
    }
    newResult.assignments.forEach((assignment, index) => {
      if (assignment.person_id !== roleDiffs[index].after_person_id) {
        fail(`recovery.new_result.assignments[${index}]`, "does not match the recovered person.");
      }
    });
  }
  validateBlockingSets(response.blockers, "recovery.blockers");
  const explanation = stringValue(response.explanation, "recovery.explanation");
  if (explanation.length > 320) fail("recovery.explanation", "exceeds the contract limit.");
  return response as unknown as RecompileResponse;
}

function validateStateDiff(value: unknown, path: string): ResilienceStateDiff {
  const diff = record(value, path);
  const capabilities = record(diff.added_capabilities, `${path}.added_capabilities`);
  Object.entries(capabilities).forEach(([key, item]) => stringArray(item, `${path}.added_capabilities.${key}`, true));
  stringArray(diff.added_people, `${path}.added_people`, true);
  const quantities = record(diff.resource_quantity_changes, `${path}.resource_quantity_changes`);
  Object.entries(quantities).forEach(([key, item]) => integerValue(item, `${path}.resource_quantity_changes.${key}`));
  return diff as unknown as ResilienceStateDiff;
}

function statusMap(value: unknown, path: string): Record<string, ResilienceSolverStatus> {
  const raw = record(value, path);
  return Object.fromEntries(
    Object.entries(raw).map(([key, item]) => [key, statusValue(item, `${path}.${key}`)]),
  );
}

function rankingKey(item: FrontierActionResult): [number, number, string] {
  return [-item.newly_feasible_initiatives.length, item.cost, item.action_id];
}

function compareRanking(left: FrontierActionResult, right: FrontierActionResult): number {
  const a = rankingKey(left);
  const b = rankingKey(right);
  return a[0] - b[0] || a[1] - b[1] || a[2].localeCompare(b[2]);
}

function expectedPareto(candidates: FrontierActionResult[]): string[] {
  return candidates
    .filter((candidate) => !candidates.some((other) =>
      other !== candidate &&
      other.newly_feasible_initiatives.length >= candidate.newly_feasible_initiatives.length &&
      other.cost <= candidate.cost &&
      (
        other.newly_feasible_initiatives.length > candidate.newly_feasible_initiatives.length ||
        other.cost < candidate.cost
      ),
    ))
    .sort(compareRanking)
    .map((item) => item.action_id);
}

function incompleteCouldBeat(
  candidate: FrontierActionResult,
  winner: FrontierActionResult | undefined,
  baseline: Record<string, ResilienceSolverStatus>,
): boolean {
  const upperBound = Object.keys(baseline).filter((initiativeId) =>
    (baseline[initiativeId] === "INFEASIBLE" || baseline[initiativeId] === "UNKNOWN") &&
    candidate.statuses_after[initiativeId] !== "INFEASIBLE",
  ).length;
  if (upperBound <= 0) return false;
  if (winner === undefined) return true;
  const winnerCount = winner.newly_feasible_initiatives.length;
  if (upperBound !== winnerCount) return upperBound > winnerCount;
  return candidate.cost < winner.cost || (candidate.cost === winner.cost && candidate.action_id < winner.action_id);
}

export function parseFrontierResponse(
  payload: unknown,
  request: FrontierRunRequest,
): CapabilityFrontierResponse {
  stringValue(request.sourceStateId, "request.sourceStateId");
  if (request.sourceContentHash !== undefined && !HASH.test(request.sourceContentHash)) {
    fail("request.sourceContentHash", "must be a lowercase 64-character content hash.");
  }
  if (request.catalystPath.length > 2 || new Set(request.catalystPath).size !== request.catalystPath.length) {
    fail("request.catalystPath", "must contain zero to two unique action IDs.");
  }
  if (
    request.expectedInitiativeIds.length === 0 ||
    new Set(request.expectedInitiativeIds).size !== request.expectedInitiativeIds.length ||
    new Set(request.expectedActionIds).size !== request.expectedActionIds.length
  ) {
    fail("request", "must bind unique initiative and action catalogues.");
  }
  assertNoOperationalMapping(payload);
  const response = record(payload, "frontier");
  const sourceStateId = stringValue(response.source_state_id, "frontier.source_state_id");
  if (sourceStateId !== request.sourceStateId) fail("frontier.source_state_id", "does not match the request.");
  const baseline = statusMap(response.baseline_statuses, "frontier.baseline_statuses");
  assertExactSet(Object.keys(baseline), request.expectedInitiativeIds, "frontier.baseline_statuses");
  const buildable = stringArray(response.baseline_buildable_ids, "frontier.baseline_buildable_ids", true);
  const blocked = stringArray(response.baseline_blocked_ids, "frontier.baseline_blocked_ids", true);
  const unknown = stringArray(response.baseline_unknown_ids, "frontier.baseline_unknown_ids", true);
  const expectedBuildable = sorted(Object.keys(baseline).filter((id) => FEASIBLE_STATUSES.has(baseline[id])));
  const expectedBlocked = sorted(Object.keys(baseline).filter((id) => baseline[id] === "INFEASIBLE"));
  const expectedUnknown = sorted(Object.keys(baseline).filter((id) => baseline[id] === "UNKNOWN"));
  if (
    !sameOrdered(buildable, expectedBuildable) ||
    !sameOrdered(blocked, expectedBlocked) ||
    !sameOrdered(unknown, expectedUnknown)
  ) {
    fail("frontier", "baseline buildable, blocked, and UNKNOWN sets do not partition statuses.");
  }

  const actions = array(response.action_results, "frontier.action_results").map((value, index) => {
    const path = `frontier.action_results[${index}]`;
    const item = record(value, path);
    if (stringValue(item.source_state_id, `${path}.source_state_id`) !== sourceStateId) {
      fail(`${path}.source_state_id`, "does not match the frontier source.");
    }
    stringValue(item.action_id, `${path}.action_id`);
    const name = stringValue(item.action_name, `${path}.action_name`);
    if (name.length > 160) fail(`${path}.action_name`, "exceeds the contract limit.");
    integerValue(item.cost, `${path}.cost`);
    const applicable = booleanValue(item.applicable, `${path}.applicable`);
    const scenarioId = nullableString(item.scenario_state_id, `${path}.scenario_state_id`);
    const scenarioHash = item.scenario_content_hash === null
      ? null
      : assertHash(item.scenario_content_hash, `${path}.scenario_content_hash`);
    const newly = stringArray(item.newly_feasible_initiatives, `${path}.newly_feasible_initiatives`, true);
    const lost = stringArray(item.lost_feasible_initiatives, `${path}.lost_feasible_initiatives`, true);
    const unresolved = stringArray(item.unknown_initiatives, `${path}.unknown_initiatives`, true);
    const total = nullableInteger(item.total_feasible_after, `${path}.total_feasible_after`);
    const after = statusMap(item.statuses_after, `${path}.statuses_after`);
    const complete = booleanValue(item.decisive_coverage_complete, `${path}.decisive_coverage_complete`);
    const explanation = stringValue(item.explanation, `${path}.explanation`);
    if (explanation.length > 320) fail(`${path}.explanation`, "exceeds the contract limit.");

    if (!applicable) {
      if (
        scenarioId !== null ||
        scenarioHash !== null ||
        item.produced_diff !== null ||
        newly.length > 0 ||
        lost.length > 0 ||
        unresolved.length > 0 ||
        total !== null ||
        Object.keys(after).length > 0 ||
        complete
      ) {
        fail(path, "attaches receipts, outcomes, or coverage to an inapplicable action.");
      }
    } else {
      if (scenarioId === null || !scenarioId.startsWith("CF_FRONTIER_V1_") || scenarioId === sourceStateId) {
        fail(`${path}.scenario_state_id`, "is not a domain-separated frontier receipt.");
      }
      if (scenarioHash === null || item.produced_diff === null || total === null) {
        fail(path, "must carry a complete analytical receipt and feasible total.");
      }
      validateStateDiff(item.produced_diff, `${path}.produced_diff`);
      assertExactSet(Object.keys(after), request.expectedInitiativeIds, `${path}.statuses_after`);
      const afterBuildable = new Set(Object.keys(after).filter((id) => FEASIBLE_STATUSES.has(after[id])));
      const expectedNew = sorted([...afterBuildable].filter((id) => !buildable.includes(id) && !unknown.includes(id)));
      const expectedLost = sorted(buildable.filter((id) => after[id] === "INFEASIBLE"));
      const expectedUnresolved = sorted(Object.keys(after).filter((id) => baseline[id] === "UNKNOWN" || after[id] === "UNKNOWN"));
      if (!sameOrdered(newly, expectedNew) || !sameOrdered(lost, expectedLost)) {
        fail(path, "newly feasible and lost sets do not match decisive before/after statuses.");
      }
      if (!sameOrdered(unresolved, expectedUnresolved) || complete !== (expectedUnresolved.length === 0)) {
        fail(path, "UNKNOWN accounting does not match decisive coverage.");
      }
      if (total !== afterBuildable.size) fail(`${path}.total_feasible_after`, "does not match after statuses.");
    }
    return item as unknown as FrontierActionResult;
  });
  const actionIds = actions.map((item) => item.action_id);
  if (new Set(actionIds).size !== actionIds.length || !sameOrdered(actionIds, request.expectedActionIds)) {
    fail("frontier.action_results", "does not match the bound authoritative action catalogue.");
  }

  const rankable = actions.filter((item) => item.applicable && item.decisive_coverage_complete);
  const pareto = stringArray(response.pareto_action_ids, "frontier.pareto_action_ids", true);
  if (!sameOrdered(pareto, expectedPareto(rankable))) {
    fail("frontier.pareto_action_ids", "does not match complete-coverage cost/leverage dominance.");
  }
  const winner = [...rankable]
    .filter((item) => item.newly_feasible_initiatives.length > 0)
    .sort(compareRanking)[0];
  const expectedUncertainty = actions.some((item) =>
    item.applicable && !item.decisive_coverage_complete && incompleteCouldBeat(item, winner, baseline),
  );
  const uncertainty = booleanValue(
    response.uncertainty_could_change_winner,
    "frontier.uncertainty_could_change_winner",
  );
  if (uncertainty !== expectedUncertainty) {
    fail("frontier.uncertainty_could_change_winner", "does not match incomplete-coverage upper bounds.");
  }
  const highest = nullableString(response.highest_leverage_action_id, "frontier.highest_leverage_action_id");
  const expectedHighest = expectedUncertainty || winner === undefined ? null : winner.action_id;
  if (highest !== expectedHighest) {
    fail("frontier.highest_leverage_action_id", "does not match complete decisive leverage ranking.");
  }
  const explanation = stringValue(response.ranking_explanation, "frontier.ranking_explanation");
  if (explanation.length > 480) fail("frontier.ranking_explanation", "exceeds the contract limit.");
  return response as unknown as CapabilityFrontierResponse;
}
