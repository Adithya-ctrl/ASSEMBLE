import assert from "node:assert/strict";
import test from "node:test";

import {
  NON_OPERATIONAL_EVIDENCE_NOTICE,
  buildFrontierViewModel,
  buildRecoveryViewModel,
  buildStressViewModel,
  technicalDisclosureState,
} from "./resilience-view-model";
import {
  allCriticalStressFixture,
  FRONTIER_ACTION_IDS,
  FRONTIER_INITIATIVE_IDS,
  s0FrontierFixture,
  SOURCE_HASH,
  trainedBasicRecoveryFixture,
  trainedFrontierFixture,
} from "./resilience-test-fixtures";
import type {
  FrontierRunRequest,
  RecoveryRunRequest,
  ResilienceSourceSummary,
  ResilienceTaskState,
  StressRunRequest,
} from "./resilience-types";

const s0: ResilienceSourceSummary = {
  stateId: "S0",
  label: "Declared community",
  contentHash: SOURCE_HASH,
  catalystPath: [],
};

const trained: ResilienceSourceSummary = {
  stateId: "S_TRAINED",
  label: "Community after training",
  contentHash: SOURCE_HASH,
  catalystPath: [{ id: "TRAIN_DIGITAL_HELPERS", label: "Train digital helpers" }],
};

function ready<Request>(request: Request, result: unknown): ResilienceTaskState<Request> {
  return { request, result, error: null, loading: false };
}

test("renders the truthful production Basic S0 4/4 critical ratio-zero result", () => {
  const request: StressRunRequest = {
    sourceStateId: "S0",
    sourceContentHash: SOURCE_HASH,
    catalystPath: [],
    initiativeId: "BASIC_WORKSHOP",
  };
  const view = buildStressViewModel(ready(request, allCriticalStressFixture()), s0);
  assert.equal(view.phase, "ready");
  assert.equal(view.catalogueSize, 4);
  assert.equal(view.decisiveCount, 4);
  assert.equal(view.criticalCount, 4);
  assert.equal(view.unknownCount, 0);
  assert.equal(view.ratioLabel, "0%");
  assert.match(view.headline, /Every tested disruption stops this plan/);
  assert.ok(view.outcomes.every((item) => item.criticality === "CRITICAL"));
});

test("renders the truthful trained Clinic 6/6 critical fixture without invented resilience", () => {
  const request: StressRunRequest = {
    sourceStateId: "S_TRAINED",
    sourceContentHash: SOURCE_HASH,
    catalystPath: ["TRAIN_DIGITAL_HELPERS"],
    initiativeId: "MULTILINGUAL_CLINIC",
  };
  const view = buildStressViewModel(
    ready(request, allCriticalStressFixture("MULTILINGUAL_CLINIC", 6, "S_TRAINED")),
    trained,
  );
  assert.deepEqual(
    {
      catalogue: view.catalogueSize,
      decisive: view.decisiveCount,
      critical: view.criticalCount,
      ratio: view.ratioLabel,
    },
    { catalogue: 6, decisive: 6, critical: 6, ratio: "0%" },
  );
});

test("renders trained Basic recovery as PRIYA to LEO with SAM preserved and burden 24", () => {
  const currentStress = buildStressViewModel(
    ready(
      {
        sourceStateId: "S_TRAINED",
        sourceContentHash: SOURCE_HASH,
        catalystPath: ["TRAIN_DIGITAL_HELPERS"],
        initiativeId: "BASIC_WORKSHOP",
      },
      allCriticalStressFixture("BASIC_WORKSHOP", 4, "S_TRAINED"),
    ),
    trained,
  );
  const request: RecoveryRunRequest = {
    sourceStateId: "S_TRAINED",
    sourceContentHash: SOURCE_HASH,
    catalystPath: ["TRAIN_DIGITAL_HELPERS"],
    initiativeId: "BASIC_WORKSHOP",
    perturbationId: "PERTURBATION_1",
    perturbationBinding: trainedBasicRecoveryFixture().perturbation,
  };
  const view = buildRecoveryViewModel(
    ready(request, trainedBasicRecoveryFixture()),
    trained,
    currentStress,
  );
  assert.equal(view.phase, "ready");
  assert.equal(view.minimumLabel, "1 assignment");
  assert.equal(view.burdenLabel, "24");
  assert.deepEqual(
    view.roleDiffs.map((item) => [item.roleLabel, item.summary]),
    [
      ["Digital Helper", "Priya → Leo"],
      ["Facilitator", "Sam preserved"],
    ],
  );
  assert.match(view.stage1?.claim ?? "", /Minimum proven/);
  assert.match(view.stage2?.claim ?? "", /proven optimal/);
  assert.ok(view.technical.some((fact) => fact.label === "Validated response JSON"));

  const catalogueWithoutSelection = {
    ...currentStress,
    outcomes: currentStress.outcomes.filter((item) => item.perturbationId !== request.perturbationId),
  };
  assert.equal(
    buildRecoveryViewModel(
      ready(request, trainedBasicRecoveryFixture()),
      trained,
      catalogueWithoutSelection,
    ).phase,
    "invalid",
  );
});

test("renders S0 frontier leverage and Pareto truth without implying a sequence", () => {
  const request: FrontierRunRequest = {
    sourceStateId: "S0",
    sourceContentHash: SOURCE_HASH,
    catalystPath: [],
    expectedInitiativeIds: FRONTIER_INITIATIVE_IDS,
    expectedActionIds: FRONTIER_ACTION_IDS,
  };
  const view = buildFrontierViewModel(ready(request, s0FrontierFixture()), s0);
  assert.equal(view.phase, "ready");
  assert.equal(view.highestLeverageLabel, "Train digital helpers");
  assert.deepEqual(
    view.actions.filter((item) => item.isPareto).map((item) => item.actionId),
    ["TRAIN_DIGITAL_HELPERS", "BORROW_TWO_LAPTOPS"],
  );
  assert.equal(view.actions.find((item) => item.actionId === "TRAIN_DIGITAL_HELPERS")?.isHighestLeverage, true);
  assert.doesNotMatch(`${view.headline} ${view.description}`, /next|then|sequence/i);
  assert.ok(view.technical.some((fact) => fact.label === "Validated response JSON"));
});

test("renders trained frontier with training inapplicable and no highest leverage", () => {
  const request: FrontierRunRequest = {
    sourceStateId: "S_TRAINED",
    sourceContentHash: SOURCE_HASH,
    catalystPath: ["TRAIN_DIGITAL_HELPERS"],
    expectedInitiativeIds: FRONTIER_INITIATIVE_IDS,
    expectedActionIds: FRONTIER_ACTION_IDS,
  };
  const view = buildFrontierViewModel(ready(request, trainedFrontierFixture()), trained);
  assert.equal(view.phase, "ready");
  assert.equal(view.highestLeverageLabel, "None");
  const training = view.actions.find((item) => item.actionId === "TRAIN_DIGITAL_HELPERS");
  assert.equal(training?.applicable, false);
  assert.match(training?.applicabilityLabel ?? "", /Not applicable/);
});

test("loading, transport errors, stale bindings and malformed results have stable safe states", () => {
  const request: StressRunRequest = {
    sourceStateId: "S0",
    catalystPath: [],
    initiativeId: "BASIC_WORKSHOP",
  };
  assert.equal(
    buildStressViewModel({ request, result: null, error: null, loading: true }, s0).phase,
    "loading",
  );
  assert.equal(
    buildStressViewModel(
      { request, result: null, error: { code: "SERVICE_BUSY", message: "Try again." }, loading: false },
      s0,
    ).phase,
    "error",
  );
  assert.equal(
    buildStressViewModel(ready({ ...request, sourceStateId: "S_OLD" }, allCriticalStressFixture()), s0).phase,
    "invalid",
  );
  assert.equal(
    buildStressViewModel(
      ready({ ...request, sourceContentHash: "b".repeat(64) }, allCriticalStressFixture()),
      s0,
    ).phase,
    "invalid",
  );
  assert.equal(
    buildStressViewModel(
      ready({ ...request, sourceContentHash: SOURCE_HASH, catalystPath: ["TRAIN_DIGITAL_HELPERS"] }, allCriticalStressFixture()),
      s0,
    ).phase,
    "invalid",
  );
  assert.equal(buildStressViewModel(ready(request, { status: "OPTIMAL" }), s0).phase, "invalid");
});

test("the evidence notice explicitly blocks operational interpretation", () => {
  assert.match(NON_OPERATIONAL_EVIDENCE_NOTICE, /analytical evidence only/i);
  assert.match(NON_OPERATIONAL_EVIDENCE_NOTICE, /do not create, apply, sequence, or update/i);
});

test("Judge-mode disclosure remounts closed when normal mode resumes", () => {
  const judge = technicalDisclosureState(true);
  const normal = technicalDisclosureState(false);
  assert.equal(judge.forcedOpen, true);
  assert.equal(normal.forcedOpen, undefined);
  assert.notEqual(judge.instanceKey, normal.instanceKey);
  assert.equal(normal.instanceKey, "normal-default-closed");
});
