import { ApiRequestError } from "./api";

export function humanize(value: string): string {
  const normalized = value.trim();
  const slot = /^SAT_(\d+)$/i.exec(normalized);
  if (slot) return `Saturday ${slot[1]}`;
  if (normalized.toUpperCase() === "EN") return "English";
  if (normalized.toUpperCase() === "AR") return "Arabic";
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function compactId(value: string): string {
  return value.replaceAll("_", " ").toLowerCase();
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function requireResponse(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ApiRequestError(message, 502, "RESPONSE_CONTRACT_ERROR");
}

export function sameOrderedIds(actual: string[], expected: string[]): boolean {
  return actual.length === expected.length && actual.every((id, index) => id === expected[index]);
}
