import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const matrix = readFileSync(new URL("./BROWSER_MATRIX_PREPARED.md", import.meta.url), "utf8");
const gaps = readFileSync(new URL("./NONVISUAL_GAP_MAP.md", import.meta.url), "utf8");

test("browser matrix and gap map distinguish executed evidence from explicit gaps", () => {
  assert.match(matrix, /Status: `EXECUTED — MIXED PASS \/ PARTIAL \/ NOT VERIFIED`/);
  assert.match(gaps, /Status: `EXECUTED — PURE GATES GREEN; MOUNTED GAPS EXPLICIT`/);
  for (const set of ["F", "Q", "R", "X", "Y"]) {
    assert.match(matrix, new RegExp(`## ${set} —`));
    assert.match(gaps, new RegExp(`\| ${set} \|`));
  }
  assert.doesNotMatch(matrix, /\| NOT RUN \|/);
  assert.doesNotMatch(gaps, /PREPARED \/ NOT RUN/);
  assert.match(matrix, /400% NOT VERIFIED/);
  assert.match(matrix, /Firefox and WebKit\/Safari execution/);
  assert.match(gaps, /not mislabelled as mounted browser evidence/i);
});
