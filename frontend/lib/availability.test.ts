import assert from "node:assert/strict";
import test from "node:test";

import { sortAvailabilitySlots } from "./availability";

test("availability labels sort chronologically without mutating source order", () => {
  const source = ["SAT_12", "SAT_10", "SAT_11"] as const;

  assert.deepEqual(sortAvailabilitySlots(source), ["SAT_10", "SAT_11", "SAT_12"]);
  assert.deepEqual(source, ["SAT_12", "SAT_10", "SAT_11"]);
});

test("availability sorting is deterministic for multiple days and unknown labels", () => {
  assert.deepEqual(
    sortAvailabilitySlots(["SUN_9", "SAT_13", "SAT_8", "CUSTOM_SLOT", "MON_18"]),
    ["MON_18", "SAT_8", "SAT_13", "SUN_9", "CUSTOM_SLOT"],
  );
});
