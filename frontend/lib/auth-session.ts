import type { AuthSession } from "./auth-types";

const MAX_BROWSER_TIMEOUT_MS = 2_147_000_000;

interface AuthenticationProblem {
  code: string;
  status: number;
}

export function isAuthenticationRequired(problem: AuthenticationProblem): boolean {
  return problem.status === 401 && problem.code === "AUTHENTICATION_REQUIRED";
}

export function sessionHasExpired(session: AuthSession, nowMilliseconds = Date.now()): boolean {
  return session.session_expires_at * 1000 <= nowMilliseconds;
}

export function sessionExpiryDelay(session: AuthSession, nowMilliseconds = Date.now()): number {
  const remaining = session.session_expires_at * 1000 - nowMilliseconds;
  return Math.max(0, Math.min(remaining, MAX_BROWSER_TIMEOUT_MS));
}
