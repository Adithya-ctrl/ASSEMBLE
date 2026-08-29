const DAY_ORDER: Record<string, number> = {
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
  SUN: 7,
};

function availabilitySortKey(slot: string): readonly [number, number, string] {
  const normalized = slot.trim().toUpperCase();
  const match = /^([A-Z]{3})_(\d+)$/.exec(normalized);
  if (!match) return [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER, normalized];
  return [DAY_ORDER[match[1]] ?? Number.MAX_SAFE_INTEGER, Number(match[2]), normalized];
}

export function sortAvailabilitySlots(slots: readonly string[]): string[] {
  return [...slots].sort((left, right) => {
    const leftKey = availabilitySortKey(left);
    const rightKey = availabilitySortKey(right);
    return leftKey[0] - rightKey[0] || leftKey[1] - rightKey[1] || leftKey[2].localeCompare(rightKey[2]);
  });
}
