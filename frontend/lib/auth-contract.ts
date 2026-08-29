import {
  COMMUNITY_ROLES,
  INVITATION_STATES,
  type AuditEvent,
  type AuthSession,
  type AuthUser,
  type CommunityMembership,
  type CommunityRole,
  type CommunitySummary,
  type InvitationCreated,
  type InvitationState,
  type InvitationSummary,
} from "./auth-types";

type UnknownRecord = Record<string, unknown>;

export class AuthContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthContractError";
  }
}

function fail(path: string, expectation: string): never {
  throw new AuthContractError(`Invalid auth response at ${path}: expected ${expectation}.`);
}

function objectAt(
  value: unknown,
  path: string,
  requiredKeys: readonly string[],
  optionalKeys: readonly string[] = [],
): UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return fail(path, "an object");
  }

  const record = value as UnknownRecord;
  const allowedKeys = new Set([...requiredKeys, ...optionalKeys]);
  for (const key of Object.keys(record)) {
    if (!allowedKeys.has(key)) fail(`${path}.${key}`, "no undocumented field");
  }
  for (const key of requiredKeys) {
    if (!Object.prototype.hasOwnProperty.call(record, key)) fail(`${path}.${key}`, "a required field");
  }
  return record;
}

function arbitraryObjectAt(value: unknown, path: string): UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return fail(path, "an object");
  }
  return value as UnknownRecord;
}

function stringAt(value: unknown, path: string): string {
  if (typeof value !== "string") return fail(path, "a string");
  return value;
}

function nullableStringAt(value: unknown, path: string): string | null {
  if (value === null) return null;
  return stringAt(value, path);
}

function integerAt(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) return fail(path, "a safe integer");
  return value;
}

function nullableIntegerAt(value: unknown, path: string): number | null {
  if (value === null) return null;
  return integerAt(value, path);
}

function enumAt<const T extends readonly string[]>(value: unknown, path: string, values: T): T[number] {
  if (typeof value !== "string" || !(values as readonly string[]).includes(value)) {
    return fail(path, values.map((item) => JSON.stringify(item)).join(" or "));
  }
  return value as T[number];
}

function roleAt(value: unknown, path: string): CommunityRole {
  return enumAt(value, path, COMMUNITY_ROLES);
}

function invitationStateAt(value: unknown, path: string): InvitationState {
  return enumAt(value, path, INVITATION_STATES);
}

function arrayAt<T>(value: unknown, path: string, parseItem: (item: unknown, itemPath: string) => T): T[] {
  if (!Array.isArray(value)) return fail(path, "an array");
  return value.map((item, index) => parseItem(item, `${path}[${index}]`));
}

function parseUserAt(value: unknown, path: string): AuthUser {
  const record = objectAt(value, path, ["id", "username", "email", "display_name", "avatar_url"]);
  return {
    id: stringAt(record.id, `${path}.id`),
    username: stringAt(record.username, `${path}.username`),
    email: nullableStringAt(record.email, `${path}.email`),
    display_name: nullableStringAt(record.display_name, `${path}.display_name`),
    avatar_url: nullableStringAt(record.avatar_url, `${path}.avatar_url`),
  };
}

function parseMembershipAt(value: unknown, path: string): CommunityMembership {
  const record = objectAt(value, path, [
    "community_id",
    "community_name",
    "community_slug",
    "user_id",
    "username",
    "role",
    "created_at",
    "updated_at",
  ]);
  return {
    community_id: stringAt(record.community_id, `${path}.community_id`),
    community_name: stringAt(record.community_name, `${path}.community_name`),
    community_slug: stringAt(record.community_slug, `${path}.community_slug`),
    user_id: stringAt(record.user_id, `${path}.user_id`),
    username: stringAt(record.username, `${path}.username`),
    role: roleAt(record.role, `${path}.role`),
    created_at: integerAt(record.created_at, `${path}.created_at`),
    updated_at: integerAt(record.updated_at, `${path}.updated_at`),
  };
}

function parseCommunityAt(value: unknown, path: string): CommunitySummary {
  const record = objectAt(value, path, ["id", "name", "slug", "role", "created_at"]);
  return {
    id: stringAt(record.id, `${path}.id`),
    name: stringAt(record.name, `${path}.name`),
    slug: stringAt(record.slug, `${path}.slug`),
    role: roleAt(record.role, `${path}.role`),
    created_at: integerAt(record.created_at, `${path}.created_at`),
  };
}

const INVITATION_KEYS = [
  "id",
  "community_id",
  "role",
  "inviter_user_id",
  "recipient_kind",
  "recipient",
  "state",
  "created_at",
  "expires_at",
  "accepted_by_user_id",
  "accepted_at",
  "revoked_at",
] as const;

function invitationFromRecord(record: UnknownRecord, path: string): InvitationSummary {
  return {
    id: stringAt(record.id, `${path}.id`),
    community_id: stringAt(record.community_id, `${path}.community_id`),
    role: roleAt(record.role, `${path}.role`),
    inviter_user_id: stringAt(record.inviter_user_id, `${path}.inviter_user_id`),
    recipient_kind: stringAt(record.recipient_kind, `${path}.recipient_kind`),
    recipient: stringAt(record.recipient, `${path}.recipient`),
    state: invitationStateAt(record.state, `${path}.state`),
    created_at: integerAt(record.created_at, `${path}.created_at`),
    expires_at: integerAt(record.expires_at, `${path}.expires_at`),
    accepted_by_user_id: nullableStringAt(record.accepted_by_user_id, `${path}.accepted_by_user_id`),
    accepted_at: nullableIntegerAt(record.accepted_at, `${path}.accepted_at`),
    revoked_at: nullableIntegerAt(record.revoked_at, `${path}.revoked_at`),
  };
}

export function parseAuthUser(value: unknown): AuthUser {
  return parseUserAt(value, "user");
}

export function parseCommunityMembership(value: unknown): CommunityMembership {
  return parseMembershipAt(value, "membership");
}

export function parseCommunityMemberships(value: unknown): CommunityMembership[] {
  return arrayAt(value, "memberships", parseMembershipAt);
}

export function parseAuthSession(value: unknown): AuthSession {
  const record = objectAt(value, "session", ["user", "memberships", "session_expires_at"]);
  return {
    user: parseUserAt(record.user, "session.user"),
    memberships: arrayAt(record.memberships, "session.memberships", parseMembershipAt),
    session_expires_at: integerAt(record.session_expires_at, "session.session_expires_at"),
  };
}

export function parseCommunitySummary(value: unknown): CommunitySummary {
  return parseCommunityAt(value, "community");
}

export function parseCommunitySummaries(value: unknown): CommunitySummary[] {
  return arrayAt(value, "communities", parseCommunityAt);
}

export function parseInvitationSummary(value: unknown): InvitationSummary {
  const record = objectAt(value, "invitation", INVITATION_KEYS);
  return invitationFromRecord(record, "invitation");
}

export function parseInvitationSummaries(value: unknown): InvitationSummary[] {
  return arrayAt(value, "invitations", (item, path) => {
    const record = objectAt(item, path, INVITATION_KEYS);
    return invitationFromRecord(record, path);
  });
}

export function parseInvitationCreated(value: unknown): InvitationCreated {
  const path = "invitation_created";
  const record = objectAt(value, path, [...INVITATION_KEYS, "token", "delivery"]);
  const invitation = invitationFromRecord(record, path);
  const delivery = stringAt(record.delivery, `${path}.delivery`);
  if (delivery !== "local_copy") fail(`${path}.delivery`, JSON.stringify("local_copy"));
  return {
    ...invitation,
    token: stringAt(record.token, `${path}.token`),
    delivery,
  };
}

function parseAuditEventAt(value: unknown, path: string): AuditEvent {
  const record = objectAt(value, path, [
    "id",
    "event_type",
    "actor_user_id",
    "subject_user_id",
    "community_id",
    "invitation_id",
    "occurred_at",
    "metadata",
  ]);
  const metadata = arbitraryObjectAt(record.metadata, `${path}.metadata`);
  return {
    id: stringAt(record.id, `${path}.id`),
    event_type: stringAt(record.event_type, `${path}.event_type`),
    actor_user_id: nullableStringAt(record.actor_user_id, `${path}.actor_user_id`),
    subject_user_id: nullableStringAt(record.subject_user_id, `${path}.subject_user_id`),
    community_id: nullableStringAt(record.community_id, `${path}.community_id`),
    invitation_id: nullableStringAt(record.invitation_id, `${path}.invitation_id`),
    occurred_at: integerAt(record.occurred_at, `${path}.occurred_at`),
    metadata: { ...metadata },
  };
}

export function parseAuditEvent(value: unknown): AuditEvent {
  return parseAuditEventAt(value, "audit_event");
}

export function parseAuditEvents(value: unknown): AuditEvent[] {
  return arrayAt(value, "audit_events", parseAuditEventAt);
}
