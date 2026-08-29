export const COMMUNITY_ROLES = ["ADMINISTRATOR", "COORDINATOR", "MEMBER", "VIEWER"] as const;

export type CommunityRole = (typeof COMMUNITY_ROLES)[number];

export const COMMUNITY_PERMISSIONS = [
  "community:read",
  "planning:use",
  "project:participate",
  "members:list",
  "members:role-change",
  "invitations:manage",
  "audit:read",
] as const;

export type CommunityPermission = (typeof COMMUNITY_PERMISSIONS)[number];

export const ROLE_PERMISSIONS: Readonly<Record<CommunityRole, readonly CommunityPermission[]>> = {
  ADMINISTRATOR: COMMUNITY_PERMISSIONS,
  COORDINATOR: ["community:read", "planning:use", "project:participate"],
  MEMBER: ["community:read", "project:participate"],
  VIEWER: ["community:read"],
};

export const INVITATION_STATES = ["PENDING", "ACCEPTED", "REVOKED", "EXPIRED"] as const;

export type InvitationState = (typeof INVITATION_STATES)[number];

export interface AuthUser {
  id: string;
  username: string;
  email: string | null;
  display_name: string | null;
  avatar_url: string | null;
}

export interface CommunityMembership {
  community_id: string;
  community_name: string;
  community_slug: string;
  user_id: string;
  username: string;
  role: CommunityRole;
  created_at: number;
  updated_at: number;
}

export interface AuthSession {
  user: AuthUser;
  memberships: CommunityMembership[];
  session_expires_at: number;
}

export interface CommunitySummary {
  id: string;
  name: string;
  slug: string;
  role: CommunityRole;
  created_at: number;
}

export interface InvitationSummary {
  id: string;
  community_id: string;
  role: CommunityRole;
  inviter_user_id: string;
  recipient_kind: string;
  recipient: string;
  state: InvitationState;
  created_at: number;
  expires_at: number;
  accepted_by_user_id: string | null;
  accepted_at: number | null;
  revoked_at: number | null;
}

/**
 * The only response type that may carry a raw invitation token. Callers must
 * display or copy it once and must not retain it in application state.
 */
export interface InvitationCreated extends InvitationSummary {
  token: string;
  delivery: "local_copy";
}

export interface AuditEvent {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  subject_user_id: string | null;
  community_id: string | null;
  invitation_id: string | null;
  occurred_at: number;
  metadata: Record<string, unknown>;
}

export interface SignupInput {
  username: string;
  email?: string | null;
  password: string;
  display_name?: string | null;
}

export interface LoginInput {
  identity: string;
  password: string;
}

export interface ProfileInput {
  display_name?: string | null;
  avatar_url?: string | null;
}

export interface PasswordChangeInput {
  current_password: string;
  new_password: string;
}

export interface CommunityCreateInput {
  name: string;
  slug: string;
}

export interface InvitationCreateInput {
  recipient: string;
  role: CommunityRole;
  expires_in_seconds?: number;
}

export interface RoleChangeInput {
  role: CommunityRole;
}
