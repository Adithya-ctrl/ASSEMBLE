import assert from "node:assert/strict";
import test from "node:test";

import {
  parseFrontierResponse,
  parseRecompileResponse,
  parseStressResponse,
  ResilienceContractError,
} from "./resilience-contract";
import {
  allCriticalStressFixture,
  FRONTIER_ACTION_IDS,
  FRONTIER_INITIATIVE_IDS,
  s0FrontierFixture,
  SOURCE_HASH,
  trainedBasicRecoveryFixture,
} from "./resilience-test-fixtures";
import type {
  FrontierRunRequest,
  RecoveryRunRequest,
  StressRunRequest,
  StressTestResponse,
} from "./resilience-types";

const stressRequest: StressRunRequest = {
  sourceStateId: "S0",
  sourceContentHash: SOURCE_HASH,
  catalystPath: [],
  initiativeId: "BASIC_WORKSHOP",
};

const recoveryRequest: RecoveryRunRequest = {
  sourceStateId: "S_TRAINED",
  sourceContentHash: SOURCE_HASH,
  catalystPath: ["TRAIN_DIGITAL_HELPERS"],
  initiativeId: "BASIC_WORKSHOP",
  perturbationId: "PERTURBATION_1",
  perturbationBinding: trainedBasicRecoveryFixture().perturbation,
};

const frontierRequest: FrontierRunRequest = {
  sourceStateId: "S0",
  sourceContentHash: SOURCE_HASH,
  catalystPath: [],
  expectedInitiativeIds: FRONTIER_INITIATIVE_IDS,
  expectedActionIds: FRONTIER_ACTION_IDS,
};

function clone<T>(value: T): T {
  return structuredClone(value);
}

function contractFailure(run: () => unknown, message: RegExp): void {
  assert.throws(run, (error: unknown) => {
    assert.ok(error instanceof ResilienceContractError);
    assert.match(error.message, message);
    return true;
  });
}

test("accepts the bound all-critical stress, trained recovery and S0 frontier fixtures", () => {
  assert.equal(parseStressResponse(allCriticalStressFixture(), stressRequest).resilience_ratio, 0);
  assert.equal(parseRecompileResponse(trainedBasicRecoveryFixture(), recoveryRequest).changed_assignments, 1);
  assert.equal(
    parseFrontierResponse(s0FrontierFixture(), frontierRequest).highest_leverage_action_id,
    "TRAIN_DIGITAL_HELPERS",
  );
});

test("stress fails closed on binding, namespace, count, ratio and UNKNOWN dishonesty", () => {
  const wrongSource = clone(allCriticalStressFixture());
  wrongSource.source_state_id = "S_OTHER";
  contractFailure(() => parseStressResponse(wrongSource, stressRequest), /source_state_id/);

  const operationalReceipt = clone(allCriticalStressFixture());
  operationalReceipt.outcomes[0].scenario_state_id = "S_OPERATIONAL";
  contractFailure(() => parseStressResponse(operationalReceipt, stressRequest), /domain-separated stress receipt/);

  const wrongCount = clone(allCriticalStressFixture());
  wrongCount.failed_count = 3;
  contractFailure(() => parseStressResponse(wrongCount, stressRequest), /count fields/);

  const wrongRatio = clone(allCriticalStressFixture());
  wrongRatio.resilience_ratio = 0.5;
  contractFailure(() => parseStressResponse(wrongRatio, stressRequest), /survived divided by decisive/);

  const dishonestUnknown = clone(allCriticalStressFixture());
  Object.assign(dishonestUnknown.outcomes[0], {
    status: "UNKNOWN",
    criticality: "UNKNOWN",
    survived: null,
    objective_value: 10,
  });
  contractFailure(() => parseStressResponse(dishonestUnknown, stressRequest), /plan metrics/);
});

test("stress rejects inconsistent feasible witness and typed perturbation bindings", () => {
  const witnessless = clone(allCriticalStressFixture());
  witnessless.baseline_result.assignments = [];
  contractFailure(() => parseStressResponse(witnessless, stressRequest), /complete objective, assignment witness/);

  const duplicateBaselineRole = clone(allCriticalStressFixture());
  duplicateBaselineRole.baseline_result.assignments[1].role_instance_id =
    duplicateBaselineRole.baseline_result.assignments[0].role_instance_id;
  contractFailure(() => parseStressResponse(duplicateBaselineRole, stressRequest), /unique role-instance witnesses/);

  const wrongPerturbation = clone(allCriticalStressFixture());
  wrongPerturbation.outcomes[0].perturbation.id = "OTHER";
  contractFailure(() => parseStressResponse(wrongPerturbation, stressRequest), /typed perturbation/);

  const wrongHash = clone(allCriticalStressFixture());
  wrongHash.outcomes[0].perturbation.source_content_hash = "b".repeat(64);
  contractFailure(() => parseStressResponse(wrongHash, stressRequest), /bound source content/);

  const incompleteMetrics = clone(allCriticalStressFixture());
  Object.assign(incompleteMetrics.outcomes[0], {
    status: "OPTIMAL",
    survived: true,
    criticality: "DEGRADED",
    blockers: [],
  });
  contractFailure(() => parseStressResponse(incompleteMetrics, stressRequest), /complete before\/after plan metrics/);

  const inconsistentMetrics = clone(allCriticalStressFixture());
  Object.assign(inconsistentMetrics.outcomes[0], {
    status: "OPTIMAL",
    survived: true,
    criticality: "DEGRADED",
    objective_value: 21,
    objective_delta: 2,
    objective_degradation: 2,
    assignment_changes: 0,
    changed_roles: [],
    after_venue_id: "COMMUNITY_HALL",
    after_start_slot: "SAT_10",
    blockers: [],
  });
  contractFailure(() => parseStressResponse(inconsistentMetrics, stressRequest), /reconcile with the baseline/);

  const inventedRole = clone(allCriticalStressFixture());
  Object.assign(inventedRole.outcomes[0], {
    status: "OPTIMAL",
    survived: true,
    criticality: "DEGRADED",
    objective_value: 19,
    objective_delta: 1,
    objective_degradation: 1,
    assignment_changes: 1,
    changed_roles: ["NOT_A_BASELINE_ROLE"],
    after_venue_id: "COMMUNITY_HALL",
    after_start_slot: "SAT_10",
    blockers: [],
  });
  contractFailure(() => parseStressResponse(inventedRole, stressRequest), /complete baseline witness/);
});

test("recovery binds only the selected returned perturbation and preserves two-stage honesty", () => {
  const wrongSelection = clone(trainedBasicRecoveryFixture());
  wrongSelection.perturbation_id = "PERTURBATION_2";
  contractFailure(() => parseRecompileResponse(wrongSelection, recoveryRequest), /selected returned perturbation/);

  const wrongTypedBinding = clone(recoveryRequest);
  wrongTypedBinding.perturbationBinding.target_id = "OTHER_PERSON";
  contractFailure(
    () => parseRecompileResponse(trainedBasicRecoveryFixture(), wrongTypedBinding),
    /exact returned perturbation binding/,
  );

  const wrongAvailabilityDelta = clone(recoveryRequest);
  if (wrongAvailabilityDelta.perturbationBinding.type !== "REDUCE_AVAILABLE_RESOURCE") {
    wrongAvailabilityDelta.perturbationBinding.before_available_slots = ["SUN_10"];
  }
  contractFailure(
    () => parseRecompileResponse(trainedBasicRecoveryFixture(), wrongAvailabilityDelta),
    /exact returned perturbation binding/,
  );

  const unprovenMinimum = clone(trainedBasicRecoveryFixture());
  Object.assign(unprovenMinimum, {
    status: "UNKNOWN",
    stage1_status: "UNKNOWN",
    stage2_status: null,
    stage2_solver_stats: null,
    minimum_proven: false,
    new_result: null,
    role_diffs: [],
    changed_assignments: null,
    preserved_assignments: null,
  });
  contractFailure(() => parseRecompileResponse(unprovenMinimum, recoveryRequest), /must be null/);

  const dishonestSecondary = clone(trainedBasicRecoveryFixture());
  dishonestSecondary.secondary_burden_optimal = false;
  contractFailure(() => parseRecompileResponse(dishonestSecondary, recoveryRequest), /OPTIMAL Stage 2/);
});

test("recovery rejects assignment flag, count and final witness drift", () => {
  const changedFlag = clone(trainedBasicRecoveryFixture());
  changedFlag.role_diffs[0].changed = false;
  contractFailure(() => parseRecompileResponse(changedFlag, recoveryRequest), /before\/after people/);

  const wrongCount = clone(trainedBasicRecoveryFixture());
  wrongCount.changed_assignments = 2;
  contractFailure(() => parseRecompileResponse(wrongCount, recoveryRequest), /assignment counts/);

  const wrongPerson = clone(trainedBasicRecoveryFixture());
  if (wrongPerson.new_result) wrongPerson.new_result.assignments[0].person_id = "PRIYA";
  contractFailure(() => parseRecompileResponse(wrongPerson, recoveryRequest), /recovered person/);
});

test("frontier rejects source/action drift, analytical receipt drift and UNKNOWN laundering", () => {
  const wrongActions = clone(s0FrontierFixture());
  wrongActions.action_results[0].action_id = "FORGED_ACTION";
  contractFailure(() => parseFrontierResponse(wrongActions, frontierRequest), /action catalogue/);

  const operationalReceipt = clone(s0FrontierFixture());
  operationalReceipt.action_results[0].scenario_state_id = "S_SUCCESSOR";
  contractFailure(() => parseFrontierResponse(operationalReceipt, frontierRequest), /domain-separated frontier receipt/);

  const launderedUnknown = clone(s0FrontierFixture());
  Object.assign(launderedUnknown.action_results[0], {
    statuses_after: {
      BASIC_WORKSHOP: "OPTIMAL",
      MULTILINGUAL_CLINIC: "UNKNOWN",
      REPAIR_SHARE: "INFEASIBLE",
    },
    newly_feasible_initiatives: ["MULTILINGUAL_CLINIC"],
  });
  contractFailure(() => parseFrontierResponse(launderedUnknown, frontierRequest), /decisive before\/after/);
});

test("frontier recomputes Pareto and highest-leverage claims", () => {
  const wrongPareto = clone(s0FrontierFixture());
  wrongPareto.pareto_action_ids = ["TRAIN_DIGITAL_HELPERS"];
  contractFailure(() => parseFrontierResponse(wrongPareto, frontierRequest), /cost\/leverage dominance/);

  const wrongWinner = clone(s0FrontierFixture());
  wrongWinner.highest_leverage_action_id = "BORROW_TWO_LAPTOPS";
  contractFailure(() => parseFrontierResponse(wrongWinner, frontierRequest), /leverage ranking/);
});

test("all counterfactual payloads reject operational and Project mapping fields", () => {
  const payload = clone(s0FrontierFixture()) as unknown as Record<string, unknown>;
  payload.successor_state_id = "S1";
  contractFailure(() => parseFrontierResponse(payload, frontierRequest), /operational lineage or Projects/);

  for (const forbiddenKey of [
    "successorStateId",
    "applied_state_id",
    "applied_to_state_id",
    "state_created_from_receipt",
    "project_state_id",
    "applied_project_id",
    "createProjectUrl",
  ]) {
    const aliasPayload = clone(allCriticalStressFixture()) as StressTestResponse & Record<string, unknown>;
    aliasPayload[forbiddenKey] = "S_OPERATIONAL";
    contractFailure(() => parseStressResponse(aliasPayload, stressRequest), /operational lineage or Projects/);
  }
});
