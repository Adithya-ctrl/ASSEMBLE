import type {
  CommunityPermission,
  CommunityRole,
  AuthSession,
} from "../auth-types";
import { ROLE_PERMISSIONS } from "../auth-types";

export type ProofStatus = "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | null;

export interface ProjectProofSnapshot {
  authoritativeBase: boolean;
  journeyStep: number;
  selectedInitiativeId: string;
  baseResultStatus: ProofStatus;
  transitionPath: readonly string[];
  appliedPath: readonly string[];
  transitionStateId: string | null;
  communityStateId: string;
  verifiedInitiativeId: string | null;
  verifiedStateId: string | null;
  verifiedStatus: ProofStatus;
}

export interface ProjectProofGate {
  allowed: boolean;
  source: "base" | "successor" | null;
  catalystPath: string[];
  reason: "base-proof" | "successor-proof" | "pending-verification" | "no-feasible-proof";
}

function feasible(status: ProofStatus): boolean {
  return status === "OPTIMAL" || status === "FEASIBLE";
}

function sameOrdered(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

/**
 * A small, dependency-free model of the Project form boundary.
 *
 * It intentionally receives facts rather than React state. Tests can use it
 * to replay proof transitions and assert that a late/partial proof cannot
 * become an operational Project claim.
 */
export function projectProofGate(snapshot: ProjectProofSnapshot): ProjectProofGate {
  const hasTransition = snapshot.transitionPath.length > 0;
  const fullPathApplied = hasTransition &&
    sameOrdered(snapshot.transitionPath, snapshot.appliedPath) &&
    snapshot.transitionStateId !== null &&
    snapshot.communityStateId === snapshot.transitionStateId;
  const successorProof = fullPathApplied &&
    snapshot.verifiedInitiativeId === snapshot.selectedInitiativeId &&
    snapshot.verifiedStateId === snapshot.communityStateId &&
    feasible(snapshot.verifiedStatus);

  if (successorProof) {
    return {
      allowed: true,
      source: "successor",
      catalystPath: [...snapshot.transitionPath],
      reason: "successor-proof",
    };
  }

  const baseProof = snapshot.authoritativeBase &&
    !hasTransition &&
    snapshot.appliedPath.length === 0 &&
    snapshot.journeyStep >= 2 &&
    feasible(snapshot.baseResultStatus);
  if (baseProof) {
    return {
      allowed: true,
      source: "base",
      catalystPath: [],
      reason: "base-proof",
    };
  }

  const pending = hasTransition;
  return {
    allowed: false,
    source: null,
    catalystPath: [],
    reason: pending ? "pending-verification" : "no-feasible-proof",
  };
}

export interface ProjectSubmitState {
  nonce: number;
  inFlight: boolean;
  responseKey: string | null;
}

export const initialProjectSubmitState: ProjectSubmitState = {
  nonce: 0,
  inFlight: false,
  responseKey: null,
};

export function beginProjectSubmit(state: ProjectSubmitState): {
  state: ProjectSubmitState;
  accepted: boolean;
  nonce: number;
} {
  if (state.inFlight) return { state, accepted: false, nonce: state.nonce };
  const nonce = state.nonce + 1;
  return {
    state: { nonce, inFlight: true, responseKey: null },
    accepted: true,
    nonce,
  };
}

export function completeProjectSubmit(
  state: ProjectSubmitState,
  nonce: number,
  responseKey: string,
): ProjectSubmitState {
  if (!state.inFlight || state.nonce !== nonce) return state;
  return { ...state, inFlight: false, responseKey };
}

export function invalidateProjectSubmit(state: ProjectSubmitState): ProjectSubmitState {
  return { nonce: state.nonce + 1, inFlight: false, responseKey: null };
}

export type IdentityModelStatus = "bootstrapping" | "guest" | "authenticated" | "working" | "error";

export interface IdentityModelError {
  code: string;
  status: number;
}

export interface IdentityModelState {
  status: IdentityModelStatus;
  session: AuthSession | null;
  error: IdentityModelError | null;
}

export type IdentityModelEvent =
  | { type: "SESSION_ACCEPTED"; session: AuthSession }
  | { type: "AUTHENTICATION_REQUIRED"; message?: string }
  | { type: "SESSION_EXPIRED" }
  | { type: "BOOTSTRAP_FAILED"; error: IdentityModelError }
  | { type: "REQUEST_FAILED"; error: IdentityModelError }
  | { type: "BEGIN_ACTION" };

/** Model the client-side distinction between an inactive session and bad credentials. */
export function reduceIdentityModel(
  state: IdentityModelState,
  event: IdentityModelEvent,
): IdentityModelState {
  switch (event.type) {
    case "BEGIN_ACTION":
      return { ...state, status: "working", error: null };
    case "SESSION_ACCEPTED":
      return { status: "authenticated", session: event.session, error: null };
    case "AUTHENTICATION_REQUIRED":
    case "SESSION_EXPIRED":
      return { status: "guest", session: null, error: null };
    case "BOOTSTRAP_FAILED":
      return { status: "error", session: null, error: event.error };
    case "REQUEST_FAILED":
      if (event.error.code === "AUTHENTICATION_REQUIRED" && event.error.status === 401) {
        return { status: "guest", session: null, error: event.error };
      }
      return {
        status: state.session ? "authenticated" : "guest",
        session: state.session,
        error: event.error,
      };
  }
}

export function roleCan(role: CommunityRole, permission: CommunityPermission): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}

export type InvitationTokenEvent =
  | { type: "DELIVER"; token: string }
  | { type: "COPY" }
  | { type: "DISMISS" }
  | { type: "SUBMIT" }
  | { type: "INVALIDATE" }
  | { type: "UNMOUNT" };

export interface InvitationTokenState {
  token: string | null;
  visible: boolean;
}

export const emptyInvitationToken: InvitationTokenState = { token: null, visible: false };

/** Raw invitation tokens are a one-shot UI delivery value, never a list-state value. */
export function reduceInvitationToken(
  state: InvitationTokenState,
  event: InvitationTokenEvent,
): InvitationTokenState {
  if (event.type === "DELIVER") return { token: event.token, visible: true };
  if (event.type === "COPY" || event.type === "DISMISS" || event.type === "SUBMIT" || event.type === "INVALIDATE" || event.type === "UNMOUNT") {
    return emptyInvitationToken;
  }
  return state;
}
