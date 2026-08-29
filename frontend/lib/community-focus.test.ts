import assert from "node:assert/strict";
import test from "node:test";

import { focusIfConnected } from "./focus-utils";

test("focus return targets a still-connected entity trigger", () => {
  let focusCalls = 0;
  const focused = focusIfConnected({ isConnected: true, focus: () => { focusCalls += 1; } });
  assert.equal(focused, true);
  assert.equal(focusCalls, 1);
});

test("focus return ignores a stale entity trigger", () => {
  let focusCalls = 0;
  const focused = focusIfConnected({ isConnected: false, focus: () => { focusCalls += 1; } });
  assert.equal(focused, false);
  assert.equal(focusCalls, 0);
});
