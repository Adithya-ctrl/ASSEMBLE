export const ADVERSARIAL_SEED = 20260830;

export interface MatrixCase {
  id: string;
  set: "F" | "Q" | "R" | "X" | "Y";
  description: string;
}

export function clone<T>(value: T): T {
  return structuredClone(value);
}

export function without<T extends Record<string, unknown>>(value: T, key: string): T {
  const copy = { ...value };
  delete copy[key];
  return copy;
}

export function withField<T extends Record<string, unknown>>(value: T, key: string, next: unknown): T {
  return { ...value, [key]: next };
}

export function expectReject(run: () => unknown, expected: RegExp): void {
  let thrown: unknown;
  try {
    run();
  } catch (error) {
    thrown = error;
  }
  if (!(thrown instanceof Error)) throw new Error(`Expected rejection matching ${expected}, but no Error was thrown.`);
  if (!expected.test(thrown.message)) throw new Error(`Expected rejection matching ${expected}, received: ${thrown.message}`);
}

export function countMatrixCases(cases: readonly MatrixCase[]): number {
  return cases.length;
}
