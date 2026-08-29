import { requestJson, requestNoContent } from "./api";
import {
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
import type {
  AuditEvent,
  AuthSession,
  AuthUser,
  CommunityCreateInput,
  CommunityMembership,
  CommunitySummary,
  InvitationCreateInput,
  InvitationCreated,
  InvitationSummary,
  LoginInput,
  PasswordChangeInput,
  ProfileInput,
  RoleChangeInput,
  SignupInput,
} from "./auth-types";

function jsonRequest(method: "POST" | "PATCH", body: unknown, signal?: AbortSignal): RequestInit {
  return { method, body: JSON.stringify(body), signal };
}

function emptyJsonRequest(signal?: AbortSignal): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, signal };
}

function communityPath(communityId: string, suffix = ""): string {
  return `/api/communities/${encodeURIComponent(communityId)}${suffix}`;
}

export const authApi = {
  getSession: (signal?: AbortSignal): Promise<AuthSession> =>
    requestJson<AuthSession>("/api/auth/session", { signal }, parseAuthSession),

  signup: (input: SignupInput, signal?: AbortSignal): Promise<AuthSession> =>
    requestJson<AuthSession>("/api/auth/signup", jsonRequest("POST", input, signal), parseAuthSession),

  login: (input: LoginInput, signal?: AbortSignal): Promise<AuthSession> =>
    requestJson<AuthSession>("/api/auth/login", jsonRequest("POST", input, signal), parseAuthSession),

  logout: (signal?: AbortSignal): Promise<void> =>
    requestNoContent("/api/auth/logout", emptyJsonRequest(signal)),

  changePassword: (input: PasswordChangeInput, signal?: AbortSignal): Promise<AuthSession> =>
    requestJson<AuthSession>("/api/auth/password", jsonRequest("POST", input, signal), parseAuthSession),

  updateProfile: (input: ProfileInput, signal?: AbortSignal): Promise<AuthUser> =>
    requestJson<AuthUser>("/api/auth/profile", jsonRequest("PATCH", input, signal), parseAuthUser),

  listCommunities: (signal?: AbortSignal): Promise<CommunitySummary[]> =>
    requestJson<CommunitySummary[]>("/api/communities", { signal }, parseCommunitySummaries),

  createCommunity: (input: CommunityCreateInput, signal?: AbortSignal): Promise<CommunitySummary> =>
    requestJson<CommunitySummary>("/api/communities", jsonRequest("POST", input, signal), parseCommunitySummary),

  listMembers: (communityId: string, signal?: AbortSignal): Promise<CommunityMembership[]> =>
    requestJson<CommunityMembership[]>(
      communityPath(communityId, "/members"),
      { signal },
      parseCommunityMemberships,
    ),

  changeMemberRole: (
    communityId: string,
    userId: string,
    input: RoleChangeInput,
    signal?: AbortSignal,
  ): Promise<CommunityMembership> =>
    requestJson<CommunityMembership>(
      communityPath(communityId, `/members/${encodeURIComponent(userId)}`),
      jsonRequest("PATCH", input, signal),
      parseCommunityMembership,
    ),

  listInvitations: (communityId: string, signal?: AbortSignal): Promise<InvitationSummary[]> =>
    requestJson<InvitationSummary[]>(
      communityPath(communityId, "/invitations"),
      { signal },
      parseInvitationSummaries,
    ),

  createInvitation: (
    communityId: string,
    input: InvitationCreateInput,
    signal?: AbortSignal,
  ): Promise<InvitationCreated> =>
    requestJson<InvitationCreated>(
      communityPath(communityId, "/invitations"),
      jsonRequest("POST", input, signal),
      parseInvitationCreated,
    ),

  revokeInvitation: (
    communityId: string,
    invitationId: string,
    signal?: AbortSignal,
  ): Promise<InvitationSummary> =>
    requestJson<InvitationSummary>(
      communityPath(communityId, `/invitations/${encodeURIComponent(invitationId)}/revoke`),
      emptyJsonRequest(signal),
      parseInvitationSummary,
    ),

  acceptInvitation: (token: string, signal?: AbortSignal): Promise<CommunityMembership> =>
    requestJson<CommunityMembership>(
      "/api/invitations/accept",
      jsonRequest("POST", { token }, signal),
      parseCommunityMembership,
    ),

  listAuditEvents: (
    communityId: string,
    limit = 100,
    signal?: AbortSignal,
  ): Promise<AuditEvent[]> => {
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 200) {
      throw new RangeError("Audit event limit must be a safe integer between 1 and 200.");
    }
    return requestJson<AuditEvent[]>(
      `${communityPath(communityId, "/audit-events")}?limit=${limit}`,
      { signal },
      parseAuditEvents,
    );
  },
};
