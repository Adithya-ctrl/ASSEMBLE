import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveResilienceSource,
  frontierRequestBody,
  requestMatchesSource,
  ResilienceRequestLanes,
  recoveryRequestBody,
  stressRequestBody,
} from "../../../frontend/lib/resilience-integration";
import type { RecoveryRunRequest, StressRunRequest } from "../../../frontend/lib/resilience-types";
import type { DemoFixture, InitiativeAnalysisResult, TransitionResponse } from "../../../frontend/lib/types";
import { GenerationLanes, deferred } from "../../../frontend/lib/adversarial/stale-responses";
import { clone } from "../../../frontend/lib/adversarial/test-support";

const sourceHash = "a".repeat(64);
const community = {
  state_id: "S0",
  parent_state_id: null,
  organisations: [],
  people: [],
  spaces: [],
  resources: [],
};
const initiative = {
  id: "BASIC",
  name: "Basic",
  roles: [],
  venue: { minimum_capacity: 1, required_features: [] },
  resources: [],
  candidate_start_slots: ["SAT_10" as const],
  duration_slots: 1,
};
const action = {
  id: "TRAIN",
  name: "Train",
  cost: 2,
  preconditions: { person_capabilities: [], willing_learners: [], space_availability: [] },
  effects: [],
};
const demo: DemoFixture = { fixture_version: "test", community, initiatives: [initiative], actions: [action] };
const feasible: InitiativeAnalysisResult = {
  initiative_id: "BASIC",
  status: "OPTIMAL",
  objective_value: 1,
  assignments: [],
  assembly_trace: [],
  solver_stats: { branches: 0, conflicts: 0, wall_time_seconds: 0 },
};
const successor = { ...community, state_id: "S1", parent_state_id: "S0" };
const transition: TransitionResponse = {
  action_id: "TRAIN",
  predecessor_state_id: "S0",
  successor_state: successor,
  diff: { added_capabilities: {}, added_people: [], resource_quantity_changes: {} },
};

test("same-lane supersession aborts and withholds a late completion", async () => {
  const lanes = new GenerationLanes(["stress", "recovery", "frontier"] as const);
  const oldTicket = lanes.begin("stress");
  const oldResult = deferred<string>();
  const committed: string[] = [];

  const oldConsumer = oldResult.promise.then((value) => {
    if (lanes.isCurrent(oldTicket)) committed.push(value);
  });
  const newTicket = lanes.begin("stress");
  assert.equal(oldTicket.controller.signal.aborted, true);
  assert.equal(lanes.isCurrent(oldTicket), false);
  assert.equal(lanes.isCurrent(newTicket), true);

  oldResult.resolve("stale-stress-response");
  await oldConsumer;
  assert.deepEqual(committed, []);
});

test("lane invalidation is independent and invalidateAll closes every ticket", () => {
  const lanes = new GenerationLanes(["stress", "recovery", "frontier"] as const);
  const stress = lanes.begin("stress");
  const recovery = lanes.begin("recovery");
  const frontier = lanes.begin("frontier");

  lanes.invalidate("recovery");
  assert.equal(lanes.isCurrent(stress), true);
  assert.equal(lanes.isCurrent(recovery), false);
  assert.equal(lanes.isCurrent(frontier), true);

  lanes.invalidateAll();
  assert.equal(lanes.isCurrent(stress), false);
  assert.equal(lanes.isCurrent(frontier), false);
  assert.equal(lanes.generation("stress"), 2);
  assert.equal(lanes.generation("recovery"), 3);
});

test("a rejected late completion cannot become a transport error after invalidation", async () => {
  const lanes = new GenerationLanes(["project"] as const);
  const ticket = lanes.begin("project");
  const response = deferred<string>();
  const errors: unknown[] = [];
  const consumer = response.promise.catch((error: unknown) => {
    if (lanes.isCurrent(ticket)) errors.push(error);
  });

  lanes.invalidate("project");
  response.reject(new Error("late network failure"));
  await consumer;
  assert.deepEqual(errors, []);
});

test("production resilience lanes retain cross-lane independence", () => {
  const lanes: ResilienceRequestLanes = new ResilienceRequestLanes();
  const stress = lanes.begin("stress");
  const recovery = lanes.begin("recovery");
  const frontier = lanes.begin("frontier");

  lanes.invalidate("recovery");
  assert.equal(lanes.isCurrent(stress), true);
  assert.equal(lanes.isCurrent(recovery), false);
  assert.equal(lanes.isCurrent(frontier), true);
  lanes.invalidate("stress");
  assert.equal(lanes.isCurrent(frontier), true);
});

test("source binding rejects old state, old path and old initiative independently", () => {
  const source = {
    stateId: "S1",
    label: "Verified successor",
    contentHash: sourceHash,
    catalystPath: [{ id: "TRAIN", label: "Train" }],
  };
  assert.equal(requestMatchesSource({ sourceStateId: "S1", catalystPath: ["TRAIN"] }, source), true);
  assert.equal(requestMatchesSource({ sourceStateId: "S0", catalystPath: ["TRAIN"] }, source), false);
  assert.equal(requestMatchesSource({ sourceStateId: "S1", catalystPath: [] }, source), false);
  assert.equal(requestMatchesSource({ sourceStateId: "S1", catalystPath: ["OTHER"] }, source), false);
});

test("resilience request bodies are replay-safe and exclude client provenance fields", () => {
  const catalystPath = ["TRAIN"];
  const stressRequest: StressRunRequest = {
    sourceStateId: "S1",
    sourceContentHash: sourceHash,
    catalystPath,
    initiativeId: "BASIC",
  };
  const recoveryRequest: RecoveryRunRequest = {
    ...stressRequest,
    perturbationId: "P1",
    perturbationBinding: {
      id: "P1",
      type: "MAKE_ASSIGNED_PERSON_UNAVAILABLE",
      initiative_id: "BASIC",
      target_id: "PERSON",
      label: "Person unavailable",
      source_content_hash: sourceHash,
      before_available_slots: ["SAT_10"],
      after_available_slots: [],
    },
  };
  const stressBody = stressRequestBody(community, stressRequest);
  const recoveryBody = recoveryRequestBody(community, recoveryRequest);
  const frontierBody = frontierRequestBody(community, {
    sourceStateId: "S1",
    catalystPath: ["TRAIN"],
    expectedInitiativeIds: ["BASIC"],
    expectedActionIds: ["TRAIN"],
  });

  assert.deepEqual(Object.keys(stressBody).sort(), ["base_community", "catalyst_path", "initiative_id"]);
  assert.deepEqual(Object.keys(recoveryBody).sort(), ["base_community", "catalyst_path", "initiative_id", "perturbation_id"]);
  assert.deepEqual(Object.keys(frontierBody).sort(), ["base_community", "catalyst_path"]);
  assert.equal("source_state_id" in stressBody, false);
  assert.equal("source_content_hash" in stressBody, false);
  assert.notEqual(stressBody.catalyst_path, stressRequest.catalystPath);

  catalystPath[0] = "MUTATED";
  assert.deepEqual(stressBody.catalyst_path, ["TRAIN"]);
  assert.equal(stressBody.base_community, community);
});

test("source derivation blocks pending and foreign successors before any resilience lane starts", () => {
  const baseline = deriveResilienceSource({
    demo,
    community,
    analyses: { BASIC: feasible },
    transition: null,
    verifiedResult: null,
    projectPath: [],
  });
  assert.equal(baseline.kind, "ready");

  const pending = deriveResilienceSource({
    demo,
    community: successor,
    analyses: { BASIC: feasible },
    transition,
    verifiedResult: null,
    projectPath: [],
  });
  assert.equal(pending.kind, "blocked");

  const foreignPath = deriveResilienceSource({
    demo,
    community: successor,
    analyses: { BASIC: feasible },
    transition,
    verifiedResult: feasible,
    projectPath: ["OTHER"],
  });
  assert.equal(foreignPath.kind, "blocked");

  const accepted = deriveResilienceSource({
    demo,
    community: successor,
    analyses: { BASIC: feasible },
    transition,
    verifiedResult: feasible,
    projectPath: ["TRAIN"],
  });
  assert.equal(accepted.kind, "ready");
  if (accepted.kind === "ready") assert.equal(accepted.sourceKey.includes("TRAIN"), true);
});

test("cloned source payloads stay detached from source-state mutation", () => {
  const request: StressRunRequest = {
    sourceStateId: "S0",
    sourceContentHash: sourceHash,
    catalystPath: [],
    initiativeId: "BASIC",
  };
  const body = stressRequestBody(community, request);
  const copied = clone(body);
  copied.base_community.state_id = "S_FORGED";
  assert.equal(body.base_community.state_id, "S0");
  assert.equal(community.state_id, "S0");
});
