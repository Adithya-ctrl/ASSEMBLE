import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveResilienceSource,
  frontierRequestBody,
  recoveryRequestBody,
  requestMatchesSource,
  ResilienceRequestLanes,
  stressRequestBody,
} from "./resilience-integration";
import type { RecoveryRunRequest, StressRunRequest } from "./resilience-types";
import type { DemoFixture, InitiativeAnalysisResult, TransitionResponse } from "./types";

const community = {
  state_id: "S0",
  parent_state_id: null,
  organisations: [],
  people: [],
  spaces: [],
  resources: [],
};
const initiative = { id: "BASIC", name: "Basic", roles: [], venue: { minimum_capacity: 1, required_features: [] }, resources: [], candidate_start_slots: ["SAT_10" as const], duration_slots: 1 };
const action = { id: "TRAIN", name: "Train", cost: 2, preconditions: { person_capabilities: [], willing_learners: [], space_availability: [] }, effects: [] };
const demo: DemoFixture = { fixture_version: "test", community, initiatives: [initiative], actions: [action] };
const feasible: InitiativeAnalysisResult = { initiative_id: "BASIC", status: "OPTIMAL", objective_value: 1, assignments: [], assembly_trace: [], solver_stats: { branches: 0, conflicts: 0, wall_time_seconds: 0 } };
const successor = { ...community, state_id: "S1", parent_state_id: "S0" };
const transition: TransitionResponse = { action_id: "TRAIN", predecessor_state_id: "S0", successor_state: successor, diff: { added_capabilities: {}, added_people: [], resource_quantity_changes: {} } };

test("derives only canonical baseline or accepted verified successor sources", () => {
  const baseline = deriveResilienceSource({ demo, community, analyses: { BASIC: feasible }, transition: null, verifiedResult: null, projectPath: [] });
  assert.equal(baseline.kind, "ready");
  if (baseline.kind !== "ready") return;
  assert.equal(baseline.baseCommunity, demo.community);
  assert.equal(baseline.source.stateId, "S0");
  assert.deepEqual(baseline.source.catalystPath, []);
  assert.deepEqual(baseline.initiatives, [{ id: "BASIC", label: "Basic" }]);

  const pending = deriveResilienceSource({ demo, community: successor, analyses: { BASIC: feasible }, transition, verifiedResult: null, projectPath: [] });
  assert.equal(pending.kind, "blocked");

  const trained = deriveResilienceSource({ demo, community: successor, analyses: { BASIC: feasible }, transition, verifiedResult: feasible, projectPath: ["TRAIN"] });
  assert.equal(trained.kind, "ready");
  if (trained.kind !== "ready") return;
  assert.equal(trained.baseCommunity, demo.community);
  assert.equal(trained.source.stateId, "S1");
  assert.deepEqual(trained.source.catalystPath, [{ id: "TRAIN", label: "Train" }]);
});

test("builds exact backend bodies without local provenance-only fields", () => {
  const stress: StressRunRequest = { sourceStateId: "S1", sourceContentHash: "a".repeat(64), catalystPath: ["TRAIN"], initiativeId: "BASIC" };
  const recovery: RecoveryRunRequest = { ...stress, perturbationId: "P1", perturbationBinding: { id: "P1", type: "MAKE_ASSIGNED_PERSON_UNAVAILABLE", initiative_id: "BASIC", target_id: "PERSON", label: "Person unavailable", source_content_hash: "a".repeat(64), before_available_slots: ["SAT_10"], after_available_slots: [] } };
  assert.deepEqual(Object.keys(stressRequestBody(demo.community, stress)).sort(), ["base_community", "catalyst_path", "initiative_id"]);
  assert.deepEqual(Object.keys(recoveryRequestBody(demo.community, recovery)).sort(), ["base_community", "catalyst_path", "initiative_id", "perturbation_id"]);
  assert.deepEqual(Object.keys(frontierRequestBody(demo.community, { sourceStateId: "S1", catalystPath: ["TRAIN"], expectedInitiativeIds: ["BASIC"], expectedActionIds: ["TRAIN"] })).sort(), ["base_community", "catalyst_path"]);
  assert.equal(stressRequestBody(demo.community, stress).base_community, demo.community);
});

test("source bindings are ordered and request lanes reject stale completions independently", () => {
  assert.equal(requestMatchesSource({ sourceStateId: "S1", catalystPath: ["TRAIN"] }, { stateId: "S1", label: "Trained", catalystPath: [{ id: "TRAIN", label: "Train" }] }), true);
  assert.equal(requestMatchesSource({ sourceStateId: "S1", catalystPath: [] }, { stateId: "S1", label: "Trained", catalystPath: [{ id: "TRAIN", label: "Train" }] }), false);

  const lanes = new ResilienceRequestLanes();
  const stress = lanes.begin("stress");
  const recovery = lanes.begin("recovery");
  assert.equal(lanes.isCurrent(stress), true);
  assert.equal(lanes.isCurrent(recovery), true);
  lanes.invalidate("recovery");
  assert.equal(lanes.isCurrent(stress), true);
  assert.equal(lanes.isCurrent(recovery), false);
  lanes.invalidateAll();
  assert.equal(lanes.isCurrent(stress), false);
});
