export type FocusTarget = Pick<HTMLElement, "focus" | "isConnected">;

export function focusIfConnected(target: FocusTarget | null | undefined): boolean {
  if (!target?.isConnected) return false;
  target.focus();
  return true;
}
