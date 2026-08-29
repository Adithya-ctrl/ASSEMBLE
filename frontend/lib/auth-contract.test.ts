import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError } from "./api";
import { authApi } from "./auth-api";
import {
  AuthContractError,
  parseAuditEvent,
  parseAuditEvents,
  parseAuthSession,
  parseAuthUser,
  parseCommunityMembership,
  parseCommunityMemberships,
  parseCommunitySummaries,
  parseCommunitySummary,
  parseInvitationCreated,
  parseInvitationSummaries,
  parseInvitationSummary,
} from "./auth-contract";
import { isAuthenticationRequired, sessionExpiryDelay, sessionHasExpired } from "./auth-session";
import { ROLE_PERMISSIONS } from "./auth-types";

const user = {
  id: "0123456789abcdef0123456789abcdef",
  username: "alex",
  email: "alex@example.test",
  display_name: "Alex",
  avatar_url: "https://example.test/alex.png",
};

const membership = {
  community_id: "11111111111111111111111111111111",
  community_name: "Neighbourhood Assembly",
  community_slug: "neighbourhood",
  user_id: user.id,
  username: user.username,
  role: "ADMINISTRATOR",
  created_at: 2_000_000_000,
  updated_at: 2_000_000_001,
};

const session = {
  user,
  memberships: [membership],
  session_expires_at: 2_000_604_800,
};

const community = {
  id: membership.community_id,
  name: membership.community_name,
  slug: membership.community_slug,
  role: membership.role,
  created_at: membership.created_at,
};

const invitation = {
  id: "22222222222222222222222222222222",
  community_id: membership.community_id,
  role: "COORDINATOR",
  inviter_user_id: user.id,
  recipient_kind: "email",
  recipient: "recipient@example.test",
  state: "PENDING",
  created_at: 2_000_000_002,
  expires_at: 2_000_086_402,
  accepted_by_user_id: null,
  accepted_at: null,
  revoked_at: null,
};

const auditEvent = {
  id: "33333333333333333333333333333333",
  event_type: "INVITATION_CREATED",
  actor_user_id: user.id,
  subject_user_id: null,
  community_id: membership.community_id,
  invitation_id: invitation.id,
  occurred_at: 2_000_000_002,
  metadata: { role: "COORDINATOR", recipient_kind: "email" },
};

test("runtime parsers accept every frozen auth and community response shape", () => {
  assert.deepEqual(parseAuthUser(user), user);
  assert.deepEqual(parseCommunityMembership(membership), membership);
  assert.deepEqual(parseCommunityMemberships([membership]), [membership]);
  assert.deepEqual(parseAuthSession(session), session);
  assert.deepEqual(parseCommunitySummary(community), community);
  assert.deepEqual(parseCommunitySummaries([community]), [community]);
  assert.deepEqual(parseInvitationSummary(invitation), invitation);
  assert.deepEqual(parseInvitationSummaries([invitation]), [invitation]);
  assert.deepEqual(parseInvitationCreated({
    ...invitation,
    token: "one-time-token-abcdefghijklmnopqrstuvwxyz-0123456789",
    delivery: "local_copy",
  }), {
    ...invitation,
    token: "one-time-token-abcdefghijklmnopqrstuvwxyz-0123456789",
    delivery: "local_copy",
  });
  assert.deepEqual(parseAuditEvent(auditEvent), auditEvent);
  assert.deepEqual(parseAuditEvents([auditEvent]), [auditEvent]);
});

test("permission bindings match the backend role matrix exactly", () => {
  assert.deepEqual(ROLE_PERMISSIONS, {
    ADMINISTRATOR: [
      "community:read",
      "planning:use",
      "project:participate",
      "members:list",
      "members:role-change",
      "invitations:manage",
      "audit:read",
    ],
    COORDINATOR: ["community:read", "planning:use", "project:participate"],
    MEMBER: ["community:read", "project:participate"],
    VIEWER: ["community:read"],
  });
});

test("runtime parsers fail closed on missing, extra, mistyped, or unknown data", () => {
  const malformedValues: Array<() => unknown> = [
    () => parseAuthUser({ ...user, unexpected: true }),
    () => parseAuthUser({ ...user, email: undefined }),
    () => parseAuthSession({ ...session, user: { ...user, username: 42 } }),
    () => parseAuthSession({ ...session, memberships: {} }),
    () => parseAuthSession({ ...session, session_expires_at: 2.5 }),
    () => parseCommunityMembership({ ...membership, role: "OWNER" }),
    () => parseCommunityMemberships([membership, { ...membership, updated_at: "now" }]),
    () => parseCommunitySummary({ ...community, created_at: Number.MAX_SAFE_INTEGER + 1 }),
    () => parseCommunitySummaries({ 0: community }),
    () => parseInvitationSummary({ ...invitation, token: "must-not-appear" }),
    () => parseInvitationSummary({ ...invitation, state: "CANCELLED" }),
    () => parseInvitationSummaries([{ ...invitation, accepted_at: "later" }]),
    () => parseInvitationCreated({ ...invitation, delivery: "local_copy" }),
    () => parseInvitationCreated({ ...invitation, token: "secret", delivery: "email" }),
    () => parseAuditEvent({ ...auditEvent, actor_user_id: 12 }),
    () => parseAuditEvent({ ...auditEvent, metadata: [] }),
    () => parseAuditEvents([auditEvent, null]),
  ];

  for (const parseMalformed of malformedValues) {
    assert.throws(parseMalformed, AuthContractError);
  }
});

test("nullable response fields must be present and may be null", () => {
  assert.deepEqual(parseAuthUser({ ...user, email: null, display_name: null, avatar_url: null }), {
    ...user,
    email: null,
    display_name: null,
    avatar_url: null,
  });
  assert.throws(
    () => parseInvitationSummary({
      id: invitation.id,
      community_id: invitation.community_id,
      role: invitation.role,
      inviter_user_id: invitation.inviter_user_id,
      recipient_kind: invitation.recipient_kind,
      recipient: invitation.recipient,
      state: invitation.state,
      created_at: invitation.created_at,
      expires_at: invitation.expires_at,
    }),
    AuthContractError,
  );
});

test("auth API methods bind exact routes, verbs, JSON bodies, validators, and 204 logout", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let nextResponse: Response;

  globalThis.fetch = async (input, init) => {
    calls.push({ url: String(input), init });
    return nextResponse;
  };

  const respondJson = (payload: unknown, status = 200) => {
    nextResponse = new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    respondJson(session);
    await authApi.getSession();
    respondJson(session, 201);
    await authApi.signup({ username: "alex", password: "ValidPassword1!" });
    respondJson(session);
    await authApi.login({ identity: "alex", password: "ValidPassword1!" });
    respondJson(session);
    await authApi.changePassword({ current_password: "ValidPassword1!", new_password: "NewPassword2@" });
    respondJson(user);
    await authApi.updateProfile({ display_name: "Alex" });
    respondJson([community]);
    await authApi.listCommunities();
    respondJson(community, 201);
    await authApi.createCommunity({ name: community.name, slug: community.slug });
    respondJson([membership]);
    await authApi.listMembers("community/unsafe");
    respondJson(membership);
    await authApi.changeMemberRole("community/unsafe", "user/unsafe", { role: "MEMBER" });
    respondJson([invitation]);
    await authApi.listInvitations(community.id);
    respondJson({ ...invitation, token: "one-time-token", delivery: "local_copy" }, 201);
    await authApi.createInvitation(community.id, { recipient: invitation.recipient, role: "COORDINATOR" });
    respondJson({ ...invitation, state: "REVOKED", revoked_at: 2_000_000_003 });
    await authApi.revokeInvitation(community.id, "invite/unsafe");
    respondJson(membership);
    await authApi.acceptInvitation("one-time-token");
    respondJson([auditEvent]);
    await authApi.listAuditEvents(community.id, 25);
    nextResponse = new Response(null, { status: 204 });
    await authApi.logout();

    assert.deepEqual(calls.map(({ url, init }) => [url, init?.method ?? "GET"]), [
      ["/api/auth/session", "GET"],
      ["/api/auth/signup", "POST"],
      ["/api/auth/login", "POST"],
      ["/api/auth/password", "POST"],
      ["/api/auth/profile", "PATCH"],
      ["/api/communities", "GET"],
      ["/api/communities", "POST"],
      ["/api/communities/community%2Funsafe/members", "GET"],
      ["/api/communities/community%2Funsafe/members/user%2Funsafe", "PATCH"],
      [`/api/communities/${community.id}/invitations`, "GET"],
      [`/api/communities/${community.id}/invitations`, "POST"],
      [`/api/communities/${community.id}/invitations/invite%2Funsafe/revoke`, "POST"],
      ["/api/invitations/accept", "POST"],
      [`/api/communities/${community.id}/audit-events?limit=25`, "GET"],
      ["/api/auth/logout", "POST"],
    ]);
    assert.equal(calls.every(({ init }) => init?.credentials === "same-origin"), true);
    assert.equal(calls.filter(({ init }) => init?.method && init.method !== "GET").every(({ init }) => new Headers(init?.headers).get("Content-Type") === "application/json"), true);
    assert.deepEqual(JSON.parse(String(calls[1].init?.body)), {
      username: "alex",
      password: "ValidPassword1!",
    });
    assert.deepEqual(JSON.parse(String(calls[8].init?.body)), { role: "MEMBER" });
    assert.deepEqual(JSON.parse(String(calls[12].init?.body)), { token: "one-time-token" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("auth API propagates contract failures and rejects invalid audit limits before fetch", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCount = 0;
  globalThis.fetch = async () => {
    fetchCount += 1;
    return new Response(JSON.stringify({ ...session, user: { ...user, role: "ADMINISTRATOR" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await assert.rejects(authApi.getSession(), AuthContractError);
    assert.throws(() => authApi.listAuditEvents(community.id, 0), RangeError);
    assert.throws(() => authApi.listAuditEvents(community.id, 201), RangeError);
    assert.throws(() => authApi.listAuditEvents(community.id, 1.5), RangeError);
    assert.equal(fetchCount, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("auth API preserves the stable backend error envelope after reading its JSON body", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    error: {
      code: "AUTHENTICATION_REQUIRED",
      message: "A current authenticated session is required.",
      details: {},
    },
  }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });

  try {
    await assert.rejects(authApi.getSession(), (error: unknown) => {
      assert.equal(error instanceof ApiRequestError, true);
      if (!(error instanceof ApiRequestError)) return false;
      assert.equal(error.status, 401);
      assert.equal(error.code, "AUTHENTICATION_REQUIRED");
      assert.equal(error.message, "A current authenticated session is required.");
      return true;
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("session expiry and authentication-required invalidation are fail-closed", () => {
  const active = parseAuthSession({
    user,
    memberships: [],
    session_expires_at: 1_800_000_000,
  });
  assert.equal(sessionHasExpired(active, 1_799_999_999_999), false);
  assert.equal(sessionHasExpired(active, 1_800_000_000_000), true);
  assert.equal(sessionExpiryDelay(active, 1_799_999_999_000), 1_000);
  assert.equal(isAuthenticationRequired({ status: 401, code: "AUTHENTICATION_REQUIRED" }), true);
  assert.equal(isAuthenticationRequired({ status: 401, code: "AUTHENTICATION_FAILED" }), false);
  assert.equal(isAuthenticationRequired({ status: 403, code: "PERMISSION_DENIED" }), false);
});
