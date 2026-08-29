import type { InventoryView } from "./workflow-types";

export const UI_PREFERENCES_COOKIE = "assemble_ui_preferences";
export const UI_PREFERENCES_VERSION = 1;
export const UI_PREFERENCES_MAX_ENCODED_LENGTH = 512;
export const UI_PREFERENCES_MAX_AGE_SECONDS = 60 * 60 * 24 * 180;

export type ThemePreference = "system" | "light" | "dark";
export type ContrastPreference = "standard" | "high";
export type MotionPreference = "system" | "reduced";

export interface UiPreferences {
  version: 1;
  theme: ThemePreference;
  contrast: ContrastPreference;
  motion: MotionPreference;
  inventoryView: InventoryView;
}

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  version: UI_PREFERENCES_VERSION,
  theme: "system",
  contrast: "standard",
  motion: "system",
  inventoryView: "graph",
};

function hasExactKeys(value: Record<string, unknown>): boolean {
  const keys = Object.keys(value).sort();
  return keys.join("|") === "contrast|inventoryView|motion|theme|version";
}

export function decodeUiPreferences(encoded: string | undefined): UiPreferences {
  if (!encoded || encoded.length > UI_PREFERENCES_MAX_ENCODED_LENGTH) return DEFAULT_UI_PREFERENCES;
  try {
    const value: unknown = JSON.parse(decodeURIComponent(encoded));
    if (!value || typeof value !== "object" || Array.isArray(value)) return DEFAULT_UI_PREFERENCES;
    const candidate = value as Record<string, unknown>;
    if (!hasExactKeys(candidate) || candidate.version !== UI_PREFERENCES_VERSION) return DEFAULT_UI_PREFERENCES;
    if (!(["system", "light", "dark"] as unknown[]).includes(candidate.theme)) return DEFAULT_UI_PREFERENCES;
    if (!(["standard", "high"] as unknown[]).includes(candidate.contrast)) return DEFAULT_UI_PREFERENCES;
    if (!(["system", "reduced"] as unknown[]).includes(candidate.motion)) return DEFAULT_UI_PREFERENCES;
    if (!(["graph", "list"] as unknown[]).includes(candidate.inventoryView)) return DEFAULT_UI_PREFERENCES;
    return candidate as unknown as UiPreferences;
  } catch {
    return DEFAULT_UI_PREFERENCES;
  }
}

export function encodeUiPreferences(preferences: UiPreferences): string {
  return encodeURIComponent(JSON.stringify(preferences));
}

export function readUiPreferencesCookie(cookieHeader: string): UiPreferences {
  const prefix = `${UI_PREFERENCES_COOKIE}=`;
  const encoded = cookieHeader.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix))?.slice(prefix.length);
  return decodeUiPreferences(encoded);
}

export function writeUiPreferencesCookie(preferences: UiPreferences): string {
  return `${UI_PREFERENCES_COOKIE}=${encodeUiPreferences(preferences)}; Path=/; Max-Age=${UI_PREFERENCES_MAX_AGE_SECONDS}; SameSite=Lax`;
}
