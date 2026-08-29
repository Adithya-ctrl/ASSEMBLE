import assert from "node:assert/strict";
import test from "node:test";

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
} from "../../../frontend/lib/auth-contract";
import { parseFrontierResponse, parseRecompileResponse, parseStressResponse, ResilienceContractError } from "../../../frontend/lib/resilience-contract";
import {
  allCriticalStressFixture,
  FRONTIER_ACTION_IDS,
  FRONTIER_INITIATIVE_IDS,
  s0FrontierFixture,
  SOURCE_HASH,
  trainedBasicRecoveryFixture,
} from "../../../frontend/lib/resilience-test-fixtures";
import type {
  FrontierRunRequest,
  RecoveryRunRequest,
  StressRunRequest,
} from "../../../frontend/lib/resilience-types";
import { ADVERSARIAL_SEED, clone, type MatrixCase } from "../../../frontend/lib/adversarial/test-support";

type Case = MatrixCase & { run: () => unknown };

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

const stressRequest: StressRunRequest = {
  sourceStateId: "S0",
  sourceContentHash: SOURCE_HASH,
  catalystPath: [],
  initiativeId: "BASIC_WORKSHOP",
};

const recoveryRequest: RecoveryRunRequest = {
  sourceStateId: "S_TRAINED",
  sourceContentHash: SOURCE_HASH,
  catalystPath: ["TRAIN_DIGITAL_HELPERS"],
  initiativeId: "BASIC_WORKSHOP",
  perturbationId: "PERTURBATION_1",
  perturbationBinding: trainedBasicRecoveryFixture().perturbation,
};

const frontierRequest: FrontierRunRequest = {
  sourceStateId: "S0",
  sourceContentHash: SOURCE_HASH,
  catalystPath: [],
  expectedInitiativeIds: FRONTIER_INITIATIVE_IDS,
  expectedActionIds: FRONTIER_ACTION_IDS,
};

function drop<T>(value: T, key: string): T {
  const copy = clone(value) as Record<string, unknown>;
  delete copy[key];
  return copy as T;
}

function setField<T>(value: T, key: string, next: unknown): T {
  const copy = clone(value) as Record<string, unknown>;
  copy[key] = next;
  return copy as T;
}

function edit<T>(value: T, editValue: (copy: T) => void): T {
  const copy = clone(value);
  editValue(copy);
  return copy;
}

function rejectMatrix(cases: readonly Case[], expected: RegExp): void {
  for (const item of cases) {
    let thrown: unknown;
    try {
      item.run();
    } catch (error) {
      thrown = error;
    }
    assert.ok(thrown instanceof Error, `${item.id}: expected a parser rejection`);
    assert.match(thrown.message, expected, item.id);
  }
}

const authCases: Case[] = [
  { id: "Q-AUTH-USER-MISSING-ID", set: "Q", description: "missing required user identity", run: () => parseAuthUser(drop(user, "id")) },
  { id: "Q-AUTH-USER-UNDEFINED-EMAIL", set: "Q", description: "nullable user field is omitted as undefined", run: () => parseAuthUser({ ...user, email: undefined }) },
  { id: "Q-AUTH-USER-EXTRA", set: "Q", description: "undocumented user field", run: () => parseAuthUser({ ...user, role: "ADMINISTRATOR" }) },
  { id: "Q-AUTH-USER-TYPE", set: "Q", description: "user ID has the wrong type", run: () => parseAuthUser({ ...user, id: 1 }) },
  { id: "Q-AUTH-SESSION-USER", set: "Q", description: "session user is not an object", run: () => parseAuthSession({ ...session, user: null }) },
  { id: "Q-AUTH-SESSION-MEMBERSHIPS", set: "Q", description: "session memberships are not an array", run: () => parseAuthSession({ ...session, memberships: {} }) },
  { id: "Q-AUTH-SESSION-EXPIRY", set: "Q", description: "session expiry is not a safe integer", run: () => parseAuthSession({ ...session, session_expires_at: 2.5 }) },
  { id: "Q-AUTH-SESSION-EXTRA", set: "Q", description: "undocumented session field", run: () => parseAuthSession({ ...session, token: "never-accepted" }) },
  { id: "Q-AUTH-MEMBERSHIP-ROLE", set: "Q", description: "unknown persisted role", run: () => parseCommunityMembership({ ...membership, role: "OWNER" }) },
  { id: "Q-AUTH-MEMBERSHIP-TIMESTAMP", set: "Q", description: "membership timestamp is not an integer", run: () => parseCommunityMembership({ ...membership, updated_at: "later" }) },
  { id: "Q-AUTH-MEMBERSHIP-EXTRA", set: "Q", description: "undocumented membership field", run: () => parseCommunityMembership({ ...membership, permissions: ["audit:read"] }) },
  { id: "Q-AUTH-MEMBERSHIPS-NULL", set: "Q", description: "membership list contains null", run: () => parseCommunityMemberships([membership, null]) },
  { id: "Q-AUTH-COMMUNITY-ROLE", set: "Q", description: "community summary role is unknown", run: () => parseCommunitySummary({ ...community, role: "OWNER" }) },
  { id: "Q-AUTH-COMMUNITY-EXTRA", set: "Q", description: "undocumented community field", run: () => parseCommunitySummary({ ...community, members: 3 }) },
  { id: "Q-AUTH-COMMUNITIES-OBJECT", set: "Q", description: "community list is not an array", run: () => parseCommunitySummaries({ 0: community }) },
  { id: "Q-AUTH-INVITATION-STATE", set: "Q", description: "unknown invitation lifecycle state", run: () => parseInvitationSummary({ ...invitation, state: "CANCELLED" }) },
  { id: "Q-AUTH-INVITATION-TOKEN-LEAK", set: "Q", description: "raw token is not allowed in redacted summary", run: () => parseInvitationSummary({ ...invitation, token: "secret" }) },
  { id: "Q-AUTH-INVITATION-NULLABLE-MISSING", set: "Q", description: "nullable invitation field omitted", run: () => parseInvitationSummary(drop(invitation, "accepted_at")) },
  { id: "Q-AUTH-INVITATION-LIST-FIELD", set: "Q", description: "invitation list item has wrong timestamp type", run: () => parseInvitationSummaries([{ ...invitation, expires_at: "later" }]) },
  { id: "Q-AUTH-INVITATION-CREATED-TOKEN", set: "Q", description: "one-time creation response omits token", run: () => parseInvitationCreated({ ...invitation, delivery: "local_copy" }) },
  { id: "Q-AUTH-INVITATION-CREATED-DELIVERY", set: "Q", description: "one-time creation response changes delivery mode", run: () => parseInvitationCreated({ ...invitation, token: "secret", delivery: "email" }) },
  { id: "Q-AUTH-AUDIT-ACTOR", set: "Q", description: "audit actor has wrong nullable type", run: () => parseAuditEvent({ ...auditEvent, actor_user_id: 12 }) },
  { id: "Q-AUTH-AUDIT-METADATA", set: "Q", description: "audit metadata is not an object", run: () => parseAuditEvent({ ...auditEvent, metadata: [] }) },
  { id: "Q-AUTH-AUDIT-EXTRA", set: "Q", description: "undocumented audit field", run: () => parseAuditEvent({ ...auditEvent, token: "never-recorded" }) },
  { id: "Q-AUTH-AUDIT-LIST", set: "Q", description: "audit list contains a malformed item", run: () => parseAuditEvents([auditEvent, null]) },
];

const stressCases: Case[] = [
  { id: "R-STRESS-INITIATIVE-MISSING", set: "R", description: "stress response omits bound initiative", run: () => parseStressResponse(drop(allCriticalStressFixture(), "initiative_id"), stressRequest) },
  { id: "R-STRESS-INITIATIVE-TYPE", set: "R", description: "stress initiative has wrong type", run: () => parseStressResponse(setField(allCriticalStressFixture(), "initiative_id", 4), stressRequest) },
  { id: "R-STRESS-SOURCE", set: "R", description: "stress response changes source state", run: () => parseStressResponse(setField(allCriticalStressFixture(), "source_state_id", "S_OTHER"), stressRequest) },
  { id: "R-STRESS-HASH", set: "R", description: "stress response uses malformed content hash", run: () => parseStressResponse(setField(allCriticalStressFixture(), "source_content_hash", SOURCE_HASH.toUpperCase()), stressRequest) },
  { id: "R-STRESS-BASELINE-MISSING", set: "R", description: "stress response omits baseline proof", run: () => parseStressResponse(drop(allCriticalStressFixture(), "baseline_result"), stressRequest) },
  { id: "R-STRESS-BASELINE-STATUS", set: "R", description: "stress baseline is not feasible", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.baseline_result.status = "INFEASIBLE"; }), stressRequest) },
  { id: "R-STRESS-BASELINE-OBJECTIVE", set: "R", description: "stress baseline omits objective", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.baseline_result.objective_value = null; }), stressRequest) },
  { id: "R-STRESS-BASELINE-WITNESS", set: "R", description: "stress baseline omits assignments", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.baseline_result.assignments = []; }), stressRequest) },
  { id: "R-STRESS-OUTCOMES-TYPE", set: "R", description: "stress outcomes are not an array", run: () => parseStressResponse(setField(allCriticalStressFixture(), "outcomes", {}), stressRequest) },
  { id: "R-STRESS-OUTCOME-SOURCE", set: "R", description: "outcome source differs from response source", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.outcomes[0].source_state_id = "S_OTHER"; }), stressRequest) },
  { id: "R-STRESS-RECEIPT-NAMESPACE", set: "R", description: "stress receipt uses an operational namespace", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.outcomes[0].scenario_state_id = "S_OPERATIONAL"; }), stressRequest) },
  { id: "R-STRESS-PERTURBATION-TYPE", set: "R", description: "perturbation type is unsupported", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { const perturbation = copy.outcomes[0].perturbation as unknown as Record<string, unknown>; perturbation.type = "UNKNOWN"; }), stressRequest) },
  { id: "R-STRESS-PERTURBATION-AVAILABILITY", set: "R", description: "person perturbation does not clear availability", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { const perturbation = copy.outcomes[0].perturbation as unknown as Record<string, unknown>; perturbation.before_available_slots = []; }), stressRequest) },
  { id: "R-STRESS-SURVIVAL", set: "R", description: "infeasible outcome claims survival", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.outcomes[0].survived = true; }), stressRequest) },
  { id: "R-STRESS-COUNTS", set: "R", description: "catalogue count does not reconcile", run: () => parseStressResponse(setField(allCriticalStressFixture(), "failed_count", 3), stressRequest) },
  { id: "R-STRESS-RATIO", set: "R", description: "resilience ratio does not reconcile", run: () => parseStressResponse(setField(allCriticalStressFixture(), "resilience_ratio", 0.5), stressRequest) },
  { id: "R-STRESS-CRITICAL-IDS", set: "R", description: "critical IDs do not match outcomes", run: () => parseStressResponse(setField(allCriticalStressFixture(), "critical_perturbation_ids", []), stressRequest) },
  { id: "R-STRESS-DUPLICATE-RECEIPT", set: "R", description: "stress outcomes reuse a receipt", run: () => parseStressResponse(edit(allCriticalStressFixture(), (copy) => { copy.outcomes[1].perturbation_id = copy.outcomes[0].perturbation_id; }), stressRequest) },
  { id: "R-STRESS-OPERATIONAL-FIELD", set: "R", description: "stress payload maps analytical evidence to operations", run: () => parseStressResponse(setField(allCriticalStressFixture(), "successor_state_id", "S1"), stressRequest) },
  { id: "R-STRESS-REQUEST-PATH", set: "R", description: "stress request has duplicate catalyst IDs", run: () => parseStressResponse(allCriticalStressFixture(), { ...stressRequest, catalystPath: ["A", "A"] }) },
  { id: "R-STRESS-REQUEST-LENGTH", set: "R", description: "stress request exceeds depth two", run: () => parseStressResponse(allCriticalStressFixture(), { ...stressRequest, catalystPath: ["A", "B", "C"] }) },
  { id: "R-STRESS-REQUEST-HASH", set: "R", description: "stress request has malformed content hash", run: () => parseStressResponse(allCriticalStressFixture(), { ...stressRequest, sourceContentHash: "not-a-hash" }) },
];

const recoveryCases: Case[] = [
  { id: "R-RECOVERY-INITIATIVE", set: "R", description: "recovery response changes initiative", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "initiative_id", "OTHER"), recoveryRequest) },
  { id: "R-RECOVERY-SOURCE", set: "R", description: "recovery response changes source state", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "source_state_id", "S_OTHER"), recoveryRequest) },
  { id: "R-RECOVERY-PERTURBATION-ID", set: "R", description: "recovery response changes selected perturbation", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "perturbation_id", "OTHER"), recoveryRequest) },
  { id: "R-RECOVERY-RECEIPT-NAMESPACE", set: "R", description: "recovery receipt uses an invalid namespace", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "scenario_state_id", "S_OPERATIONAL"), recoveryRequest) },
  { id: "R-RECOVERY-BINDING", set: "R", description: "recovery response mutates returned perturbation binding", run: () => parseRecompileResponse(edit(trainedBasicRecoveryFixture(), (copy) => { copy.perturbation.target_id = "OTHER"; }), recoveryRequest) },
  { id: "R-RECOVERY-STAGE1", set: "R", description: "recovery exposes Stage 2 after non-optimal Stage 1", run: () => parseRecompileResponse(edit(trainedBasicRecoveryFixture(), (copy) => { copy.stage1_status = "FEASIBLE"; }), recoveryRequest) },
  { id: "R-RECOVERY-STAGE2-STATS", set: "R", description: "recovery Stage 2 status and stats disagree", run: () => parseRecompileResponse(edit(trainedBasicRecoveryFixture(), (copy) => { copy.stage2_status = null; }), recoveryRequest) },
  { id: "R-RECOVERY-MINIMUM", set: "R", description: "recovery claims minimum without Stage 1 proof", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "minimum_proven", false), recoveryRequest) },
  { id: "R-RECOVERY-DIFF-FLAG", set: "R", description: "recovery changed flag disagrees with people", run: () => parseRecompileResponse(edit(trainedBasicRecoveryFixture(), (copy) => { copy.role_diffs[0].changed = false; }), recoveryRequest) },
  { id: "R-RECOVERY-WITNESS-STATUS", set: "R", description: "recovery witness status disagrees with enclosing status", run: () => parseRecompileResponse(edit(trainedBasicRecoveryFixture(), (copy) => { if (copy.new_result) copy.new_result.status = "INFEASIBLE"; }), recoveryRequest) },
  { id: "R-RECOVERY-COUNTS", set: "R", description: "recovery changed count does not match role diffs", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "changed_assignments", 2), recoveryRequest) },
  { id: "R-RECOVERY-EXPLANATION", set: "R", description: "recovery explanation exceeds its bound", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "explanation", "x".repeat(321)), recoveryRequest) },
  { id: "R-RECOVERY-OPERATIONAL-FIELD", set: "R", description: "recovery maps analytical evidence to operations", run: () => parseRecompileResponse(setField(trainedBasicRecoveryFixture(), "project_id", "P1"), recoveryRequest) },
  { id: "R-RECOVERY-REQUEST-PATH", set: "R", description: "recovery request has duplicate catalyst IDs", run: () => parseRecompileResponse(trainedBasicRecoveryFixture(), { ...recoveryRequest, catalystPath: ["A", "A"] }) },
  { id: "R-RECOVERY-REQUEST-HASH", set: "R", description: "recovery request has malformed content hash", run: () => parseRecompileResponse(trainedBasicRecoveryFixture(), { ...recoveryRequest, sourceContentHash: "bad" }) },
  { id: "R-RECOVERY-REQUEST-ID", set: "R", description: "recovery request omits selected perturbation ID", run: () => parseRecompileResponse(trainedBasicRecoveryFixture(), { ...recoveryRequest, perturbationId: "" }) },
];

const frontierCases: Case[] = [
  { id: "R-FRONTIER-SOURCE", set: "R", description: "frontier response changes source state", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "source_state_id", "S_OTHER"), frontierRequest) },
  { id: "R-FRONTIER-BASELINE-MISSING", set: "R", description: "frontier omits one expected baseline initiative", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { delete copy.baseline_statuses.REPAIR_SHARE; }), frontierRequest) },
  { id: "R-FRONTIER-PARTITION", set: "R", description: "frontier baseline sets do not partition statuses", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "baseline_blocked_ids", []), frontierRequest) },
  { id: "R-FRONTIER-ACTIONS-TYPE", set: "R", description: "frontier actions are not an array", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "action_results", {}), frontierRequest) },
  { id: "R-FRONTIER-ACTION-SOURCE", set: "R", description: "frontier action source differs", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].source_state_id = "S_OTHER"; }), frontierRequest) },
  { id: "R-FRONTIER-ACTION-ID", set: "R", description: "frontier action catalogue is forged", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].action_id = "FORGED"; }), frontierRequest) },
  { id: "R-FRONTIER-INAPPLICABLE-RECEIPT", set: "R", description: "inapplicable action carries a receipt", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].applicable = false; }), frontierRequest) },
  { id: "R-FRONTIER-MISSING-RECEIPT", set: "R", description: "applicable action omits receipt", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].scenario_state_id = null; }), frontierRequest) },
  { id: "R-FRONTIER-AFTER-STATUSES", set: "R", description: "frontier after statuses omit an initiative", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { delete copy.action_results[0].statuses_after.REPAIR_SHARE; }), frontierRequest) },
  { id: "R-FRONTIER-NEWLY", set: "R", description: "newly feasible set launders UNKNOWN", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].newly_feasible_initiatives = ["REPAIR_SHARE"]; }), frontierRequest) },
  { id: "R-FRONTIER-UNKNOWN", set: "R", description: "UNKNOWN accounting is dishonest", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results[0].unknown_initiatives = ["MULTILINGUAL_CLINIC"]; }), frontierRequest) },
  { id: "R-FRONTIER-ACTION-ORDER", set: "R", description: "frontier action order differs from catalogue", run: () => parseFrontierResponse(edit(s0FrontierFixture(), (copy) => { copy.action_results.reverse(); }), frontierRequest) },
  { id: "R-FRONTIER-PARETO", set: "R", description: "frontier Pareto set is dishonest", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "pareto_action_ids", ["TRAIN_DIGITAL_HELPERS"]), frontierRequest) },
  { id: "R-FRONTIER-WINNER", set: "R", description: "frontier winner is dishonest", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "highest_leverage_action_id", "BORROW_TWO_LAPTOPS"), frontierRequest) },
  { id: "R-FRONTIER-OPERATIONAL-FIELD", set: "R", description: "frontier maps analytical evidence to operations", run: () => parseFrontierResponse(setField(s0FrontierFixture(), "successor_state_id", "S1"), frontierRequest) },
  { id: "R-FRONTIER-REQUEST-INITIATIVES", set: "R", description: "frontier request has duplicate initiative IDs", run: () => parseFrontierResponse(s0FrontierFixture(), { ...frontierRequest, expectedInitiativeIds: ["A", "A"] }) },
  { id: "R-FRONTIER-REQUEST-ACTIONS", set: "R", description: "frontier request has duplicate action IDs", run: () => parseFrontierResponse(s0FrontierFixture(), { ...frontierRequest, expectedActionIds: ["A", "A"] }) },
];

const allCases = [...authCases, ...stressCases, ...recoveryCases, ...frontierCases];

test("Q/R malformed payload matrix fails closed with deterministic case inventory", () => {
  assert.equal(ADVERSARIAL_SEED, 20260830);
  rejectMatrix(authCases, /Invalid auth response/);
  assert.equal(authCases.every((item) => item.set === "Q"), true);
  rejectMatrix([...stressCases, ...recoveryCases, ...frontierCases], /Resilience response was withheld/);
  assert.equal([...stressCases, ...recoveryCases, ...frontierCases].every((item) => item.set === "R"), true);
  assert.equal(allCases.length, 80);
});

test("Q/R parser controls accept the canonical fixtures and preserve parser error types", () => {
  assert.deepEqual(parseAuthUser(user), user);
  assert.deepEqual(parseAuthSession(session), session);
  assert.deepEqual(parseCommunityMembership(membership), membership);
  assert.deepEqual(parseCommunityMemberships([membership]), [membership]);
  assert.deepEqual(parseCommunitySummary(community), community);
  assert.deepEqual(parseCommunitySummaries([community]), [community]);
  assert.deepEqual(parseInvitationSummary(invitation), invitation);
  assert.deepEqual(parseInvitationSummaries([invitation]), [invitation]);
  assert.deepEqual(parseInvitationCreated({ ...invitation, token: "one-time-token", delivery: "local_copy" }), { ...invitation, token: "one-time-token", delivery: "local_copy" });
  assert.deepEqual(parseAuditEvent(auditEvent), auditEvent);
  assert.deepEqual(parseAuditEvents([auditEvent]), [auditEvent]);

  assert.equal(parseStressResponse(allCriticalStressFixture(), stressRequest).source_state_id, "S0");
  assert.equal(parseRecompileResponse(trainedBasicRecoveryFixture(), recoveryRequest).status, "OPTIMAL");
  assert.equal(parseFrontierResponse(s0FrontierFixture(), frontierRequest).action_results.length, FRONTIER_ACTION_IDS.length);

  assert.throws(() => parseAuthUser({ ...user, unexpected: true }), AuthContractError);
  assert.throws(() => parseStressResponse({ status: "OPTIMAL" }, stressRequest), ResilienceContractError);
});
