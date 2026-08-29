import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_UI_PREFERENCES,
  decodeUiPreferences,
  encodeUiPreferences,
  readUiPreferencesCookie,
  UI_PREFERENCES_MAX_ENCODED_LENGTH,
  writeUiPreferencesCookie,
} from "./preferences";

test("round trips the allow-listed preference contract", () => {
  const preferences = { ...DEFAULT_UI_PREFERENCES, theme: "dark" as const, contrast: "high" as const, motion: "reduced" as const, inventoryView: "list" as const };
  assert.deepEqual(decodeUiPreferences(encodeUiPreferences(preferences)), preferences);
  assert.deepEqual(readUiPreferencesCookie(writeUiPreferencesCookie(preferences)), preferences);
});

test("invalid, oversized, stale and extended cookies fail closed", () => {
  assert.deepEqual(decodeUiPreferences("not-json"), DEFAULT_UI_PREFERENCES);
  assert.deepEqual(decodeUiPreferences("x".repeat(UI_PREFERENCES_MAX_ENCODED_LENGTH + 1)), DEFAULT_UI_PREFERENCES);
  assert.deepEqual(decodeUiPreferences(encodeURIComponent(JSON.stringify({ ...DEFAULT_UI_PREFERENCES, version: 0 }))), DEFAULT_UI_PREFERENCES);
  assert.deepEqual(decodeUiPreferences(encodeURIComponent(JSON.stringify({ ...DEFAULT_UI_PREFERENCES, accountId: "never-store" }))), DEFAULT_UI_PREFERENCES);
});
