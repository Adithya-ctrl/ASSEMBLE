import assert from "node:assert/strict";
import test from "node:test";

import {
  COMMUNITY_PERMISSIONS,
  ROLE_PERMISSIONS,
  type AuthSession,
  type CommunityRole,
} from "../../../frontend/lib/auth-types";
import {
  beginProjectSubmit,
  completeProjectSubmit,
  emptyInvitationToken,
  initialProjectSubmitState,
  invalidateProjectSubmit,
  projectProofGate,
  reduceIdentityModel,
  reduceInvitationToken,
  roleCan,
  type IdentityModelState,
  type ProjectProofSnapshot,
} from "../../../frontend/lib/adversarial/state-machines";

const baseSnapshot: ProjectProofSnapshot = {
  authoritativeBase: true,
  journeyStep: 2,
  selectedInitiativeId: "BASIC_WORKSHOP",
  baseResultStatus: "OPTIMAL",
  transitionPath: [],
  appliedPath: [],
  transitionStateId: null,
  communityStateId: "S0",
  verifiedInitiativeId: null,
  verifiedStateId: null,
  verifiedStatus: null,
};

const successorSnapshot: ProjectProofSnapshot = {
  ...baseSnapshot,
  authoritativeBase: false,
  baseResultStatus: null,
  transitionPath: ["TRAIN_DIGITAL_HELPERS"],
  appliedPath: ["TRAIN_DIGITAL_HELPERS"],
  transitionStateId: "S_TRAINED",
  communityStateId: "S_TRAINED",
  verifiedInitiativeId: "MULTILINGUAL_CLINIC",
  verifiedStateId: "S_TRAINED",
  verifiedStatus: "FEASIBLE",
  selectedInitiativeId: "MULTILINGUAL_CLINIC",
};

test("Project proof gate admits only a fresh feasible base or fully verified successor", () => {
  const base = projectProofGate(baseSnapshot);
  assert.deepEqual(base, {
    allowed: true,
    source: "base",
    catalystPath: [],
    reason: "base-proof",
  });

  const successor = projectProofGate(successorSnapshot);
  assert.deepEqual(successor, {
    allowed: true,
    source: "successor",
    catalystPath: ["TRAIN_DIGITAL_HELPERS"],
    reason: "successor-proof",
  });
  successor.catalystPath.push("MUTATION");
  assert.deepEqual(projectProofGate(successorSnapshot).catalystPath, ["TRAIN_DIGITAL_HELPERS"]);
});

test("Project proof gate withholds pre-proof, infeasible, UNKNOWN and stale successor states", () => {
  const cases: Array<[string, Partial<ProjectProofSnapshot>, "pending-verification" | "no-feasible-proof"]> = [
    ["before analysis", { journeyStep: 1, baseResultStatus: null }, "no-feasible-proof"],
    ["infeasible base", { baseResultStatus: "INFEASIBLE" }, "no-feasible-proof"],
    ["unknown base", { baseResultStatus: "UNKNOWN" }, "no-feasible-proof"],
    ["foreign base", { authoritativeBase: false }, "no-feasible-proof"],
    ["pending transition", { ...successorSnapshot, appliedPath: [], verifiedStatus: null }, "pending-verification"],
    ["partial path", { ...successorSnapshot, appliedPath: ["TRAIN_DIGITAL_HELPERS", "SECOND"] }, "pending-verification"],
    ["wrong successor state", { ...successorSnapshot, communityStateId: "S_OTHER" }, "pending-verification"],
    ["wrong verified initiative", { ...successorSnapshot, verifiedInitiativeId: "BASIC_WORKSHOP" }, "pending-verification"],
    ["unknown verification", { ...successorSnapshot, verifiedStatus: "UNKNOWN" }, "pending-verification"],
    ["extra applied path on base", { appliedPath: ["TRAIN_DIGITAL_HELPERS"] }, "no-feasible-proof"],
  ];

  for (const [label, patch, reason] of cases) {
    const result = projectProofGate({ ...baseSnapshot, ...patch });
    assert.equal(result.allowed, false, label);
    assert.equal(result.reason, reason, label);
    assert.equal(result.source, null, label);
    assert.deepEqual(result.catalystPath, [], label);
  }
});

test("duplicate Project submit is suppressed and stale completion cannot repopulate state", () => {
  const first = beginProjectSubmit(initialProjectSubmitState);
  assert.equal(first.accepted, true);
  assert.equal(first.nonce, 1);
  const duplicate = beginProjectSubmit(first.state);
  assert.equal(duplicate.accepted, false);
  assert.equal(duplicate.nonce, 1);
  assert.deepEqual(duplicate.state, first.state);

  const invalidated = invalidateProjectSubmit(first.state);
  assert.equal(invalidated.inFlight, false);
  assert.equal(invalidated.responseKey, null);
  assert.deepEqual(completeProjectSubmit(invalidated, first.nonce, "stale-project"), invalidated);

  const retry = beginProjectSubmit(invalidated);
  assert.equal(retry.accepted, true);
  assert.equal(retry.nonce, 3);
  assert.deepEqual(completeProjectSubmit(retry.state, retry.nonce, "fresh-project"), {
    nonce: 3,
    inFlight: false,
    responseKey: "fresh-project",
  });
});

const session: AuthSession = {
  user: {
    id: "0123456789abcdef0123456789abcdef",
    username: "alex",
    email: "alex@example.test",
    display_name: "Alex",
    avatar_url: null,
  },
  memberships: [],
  session_expires_at: 2_000_604_800,
};

test("identity state model distinguishes bootstrap failure, invalid credentials, expired sessions and auth-required invalidation", () => {
  const guest: IdentityModelState = { status: "guest", session: null, error: null };
  assert.equal(reduceIdentityModel({ status: "bootstrapping", session: null, error: null }, { type: "SESSION_ACCEPTED", session }).status, "authenticated");
  assert.equal(reduceIdentityModel({ status: "bootstrapping", session: null, error: null }, { type: "BOOTSTRAP_FAILED", error: { code: "SERVICE_UNAVAILABLE", status: 0 } }).status, "error");

  const invalidCredentials = reduceIdentityModel(guest, { type: "REQUEST_FAILED", error: { code: "AUTHENTICATION_FAILED", status: 401 } });
  assert.equal(invalidCredentials.status, "guest");
  assert.equal(invalidCredentials.session, null);
  assert.equal(invalidCredentials.error?.code, "AUTHENTICATION_FAILED");

  const signedIn: IdentityModelState = { status: "authenticated", session, error: null };
  const required = reduceIdentityModel(signedIn, { type: "REQUEST_FAILED", error: { code: "AUTHENTICATION_REQUIRED", status: 401 } });
  assert.equal(required.status, "guest");
  assert.equal(required.session, null);
  assert.equal(required.error?.code, "AUTHENTICATION_REQUIRED");
  assert.deepEqual(reduceIdentityModel(signedIn, { type: "SESSION_EXPIRED" }), { status: "guest", session: null, error: null });
  assert.deepEqual(reduceIdentityModel(signedIn, { type: "BEGIN_ACTION" }), { status: "working", session, error: null });
});

test("role permission model exposes only the frozen RBAC matrix", () => {
  const roles = Object.keys(ROLE_PERMISSIONS) as CommunityRole[];
  for (const role of roles) {
    for (const permission of COMMUNITY_PERMISSIONS) {
      assert.equal(roleCan(role, permission), ROLE_PERMISSIONS[role].includes(permission), `${role}:${permission}`);
    }
  }
  assert.deepEqual(ROLE_PERMISSIONS.ADMINISTRATOR, COMMUNITY_PERMISSIONS);
  assert.equal(roleCan("COORDINATOR", "members:list"), false);
  assert.equal(roleCan("MEMBER", "invitations:manage"), false);
  assert.equal(roleCan("VIEWER", "community:read"), true);
});

test("invitation token state is one-shot and clears on every lifecycle invalidation", () => {
  const delivered = reduceInvitationToken(emptyInvitationToken, { type: "DELIVER", token: "one-time-secret" });
  assert.deepEqual(delivered, { token: "one-time-secret", visible: true });
  for (const type of ["COPY", "DISMISS", "SUBMIT", "INVALIDATE", "UNMOUNT"] as const) {
    const cleared = reduceInvitationToken(delivered, { type });
    assert.deepEqual(cleared, emptyInvitationToken, type);
  }
  assert.deepEqual(reduceInvitationToken(emptyInvitationToken, { type: "COPY" }), emptyInvitationToken);
});
