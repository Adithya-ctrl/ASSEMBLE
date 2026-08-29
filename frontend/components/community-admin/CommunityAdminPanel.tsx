"use client";

import { ArrowLeft, Clipboard, ClockCounterClockwise, EnvelopeSimple, ShieldCheck, Trash, UsersThree, WarningCircle, X } from "@phosphor-icons/react";
import { Button, Tabs } from "@radix-ui/themes";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiRequestError } from "../../lib/api";
import { authApi } from "../../lib/auth-api";
import { COMMUNITY_ROLES, type AuditEvent, type CommunityMembership, type CommunityRole, type InvitationCreated, type InvitationSummary } from "../../lib/auth-types";
import { useIdentity } from "../../lib/identity-context";
import { humanize, isAbortError } from "../../lib/ui";

type AdminTab = "members" | "invitations" | "audit";
interface AdminError { code: string; message: string; status: number }

function adminError(error: unknown): AdminError {
  if (error instanceof ApiRequestError) return { code: error.code, message: error.message, status: error.status };
  return { code: "REQUEST_FAILED", message: "The administration request could not be completed.", status: 0 };
}

function ErrorMessage({ error, onRetry }: { error: AdminError; onRetry?: () => void }) {
  return <div className="collab-error" role="alert"><WarningCircle aria-hidden="true" size={20} weight="duotone" /><div><strong>{error.code}</strong><span>{error.message}</span></div>{onRetry ? <Button onClick={onRetry} size="2" variant="outline">Try again</Button> : null}</div>;
}

function formatTime(timestamp: number): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(timestamp * 1000));
}

function roleLabel(role: CommunityRole): string {
  return role.charAt(0) + role.slice(1).toLowerCase();
}

function withoutToken(created: InvitationCreated): InvitationSummary {
  return {
    id: created.id,
    community_id: created.community_id,
    role: created.role,
    inviter_user_id: created.inviter_user_id,
    recipient_kind: created.recipient_kind,
    recipient: created.recipient,
    state: created.state,
    created_at: created.created_at,
    expires_at: created.expires_at,
    accepted_by_user_id: created.accepted_by_user_id,
    accepted_at: created.accepted_at,
    revoked_at: created.revoked_at,
  };
}

export default function CommunityAdminPanel({ communityId }: { communityId: string }) {
  const identity = useIdentity();
  const { announce, invalidateCommunityAccess, invalidateSession, refreshSession, session } = identity;
  const membership = session?.memberships.find((item) => item.community_id === communityId);
  const [tab, setTab] = useState<AdminTab>("members");
  const [members, setMembers] = useState<CommunityMembership[]>([]);
  const [invitations, setInvitations] = useState<InvitationSummary[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [requestError, setRequestError] = useState<AdminError | null>(null);
  const [working, setWorking] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [inviteRole, setInviteRole] = useState<CommunityRole>("MEMBER");
  const [expiry, setExpiry] = useState(24 * 60 * 60);
  const [deliveredToken, setDeliveredToken] = useState<string | null>(null);
  const tokenRef = useRef<HTMLDivElement>(null);
  const invitationSubmitRef = useRef<HTMLButtonElement>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef(0);

  const begin = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    generationRef.current += 1;
    setRequestError(null);
    return { controller, generation: generationRef.current };
  }, []);
  const isCurrent = useCallback((generation: number, controller: AbortController) => generationRef.current === generation && controllerRef.current === controller && !controller.signal.aborted, []);
  const handleFailure = useCallback((error: unknown, generation: number, controller: AbortController) => {
    if (!isCurrent(generation, controller) || isAbortError(error)) return;
    const next = adminError(error);
    setRequestError(next);
    announce(next.message);
    if (next.status === 401 && next.code === "AUTHENTICATION_REQUIRED") invalidateSession(next.message);
    if (next.status === 403) {
      setMembers([]);
      setInvitations([]);
      setEvents([]);
      setDeliveredToken(null);
      invalidateCommunityAccess(communityId);
      void refreshSession();
    }
  }, [announce, communityId, invalidateCommunityAccess, invalidateSession, isCurrent, refreshSession]);

  const loadTab = useCallback(async (target: AdminTab = tab) => {
    if (!membership || membership.role !== "ADMINISTRATOR") return;
    const { controller, generation } = begin();
    setWorking(true);
    try {
      if (target === "members") {
        const next = await authApi.listMembers(communityId, controller.signal);
        if (isCurrent(generation, controller)) setMembers(next);
      }
      if (target === "invitations") {
        const next = await authApi.listInvitations(communityId, controller.signal);
        if (isCurrent(generation, controller)) setInvitations(next);
      }
      if (target === "audit") {
        const next = await authApi.listAuditEvents(communityId, 100, controller.signal);
        if (isCurrent(generation, controller)) setEvents(next);
      }
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  }, [begin, communityId, handleFailure, isCurrent, membership, tab]);

  useEffect(() => {
    const timer = membership?.role === "ADMINISTRATOR" ? window.setTimeout(() => void loadTab(tab), 0) : undefined;
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      setDeliveredToken(null);
    };
  }, [loadTab, membership?.role, tab]);

  const changeRole = async (event: FormEvent<HTMLFormElement>, member: CommunityMembership) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const nextRole = form.get("role");
    if (typeof nextRole !== "string" || !COMMUNITY_ROLES.includes(nextRole as CommunityRole) || nextRole === member.role) return;
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const updated = await authApi.changeMemberRole(communityId, member.user_id, { role: nextRole as CommunityRole }, controller.signal);
      if (!isCurrent(generation, controller)) return;
      setMembers((current) => current.map((item) => item.user_id === updated.user_id ? updated : item));
      announce(`${updated.username} is now ${roleLabel(updated.role)}.`);
      if (updated.user_id === session?.user.id) void refreshSession();
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  };

  const createInvitation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setDeliveredToken(null);
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const created = await authApi.createInvitation(communityId, { recipient: recipient.trim(), role: inviteRole, expires_in_seconds: expiry }, controller.signal);
      if (!isCurrent(generation, controller)) return;
      const token = created.token;
      const summary = withoutToken(created);
      setInvitations((current) => [summary, ...current.filter((item) => item.id !== summary.id)]);
      setDeliveredToken(token);
      setRecipient("");
      announce("Invitation created. Copy the one-time token now.");
      requestAnimationFrame(() => tokenRef.current?.focus());
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  };

  const revokeInvitation = async (invitation: InvitationSummary) => {
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const updated = await authApi.revokeInvitation(communityId, invitation.id, controller.signal);
      if (!isCurrent(generation, controller)) return;
      setInvitations((current) => current.map((item) => item.id === updated.id ? updated : item));
      announce(`Invitation for ${updated.recipient} revoked.`);
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  };

  const copyAndClearToken = async () => {
    if (!deliveredToken) return;
    try {
      await navigator.clipboard.writeText(deliveredToken);
      setDeliveredToken(null);
      announce("Invitation token copied and removed from the screen.");
      requestAnimationFrame(() => invitationSubmitRef.current?.focus());
    } catch {
      announce("The token could not be copied. Select it manually before dismissing it.");
    }
  };

  if (identity.status === "bootstrapping") return <section aria-busy="true" className="collab-admin"><h1>Collaboration space</h1><p>Checking account access.</p></section>;
  if (!session) return <section className="collab-admin collab-signin-state"><ShieldCheck aria-hidden="true" size={29} weight="duotone" /><h1>Administration requires sign in</h1><p>Sign in with an account that belongs to this collaboration space.</p><Button asChild size="3"><Link href="/login">Sign in</Link></Button></section>;
  if (!membership) return <section className="collab-admin collab-access-state"><WarningCircle aria-hidden="true" size={29} weight="duotone" /><h1>Collaboration space not found</h1><p>This space is unknown or the current account has no membership.</p><Button asChild size="3" variant="outline"><Link href="/communities"><ArrowLeft aria-hidden="true" size={17} /> Back to spaces</Link></Button></section>;

  if (membership.role !== "ADMINISTRATOR") {
    return (
      <section aria-labelledby="collab-admin-title" className="collab-admin collab-access-state">
        <UsersThree aria-hidden="true" size={30} weight="duotone" />
        <h1 id="collab-admin-title">{membership.community_name}</h1>
        <p>Your persisted role is <strong>{roleLabel(membership.role)}</strong>. Only Administrators can list members, change roles, manage invitations or read audit events.</p>
        <div className="collab-truth-note"><WarningCircle aria-hidden="true" size={20} weight="duotone" /><p>This role does not gate the separate planning demo, solver, Project or resilience routes.</p></div>
        <Button asChild size="3" variant="outline"><Link href="/communities"><ArrowLeft aria-hidden="true" size={17} /> Back to spaces</Link></Button>
      </section>
    );
  }

  const administratorCount = members.filter((member) => member.role === "ADMINISTRATOR").length;

  return (
    <section aria-labelledby="collab-admin-title" className="collab-admin">
      <Link className="collab-back-link" href="/communities"><ArrowLeft aria-hidden="true" size={17} /> Collaboration spaces</Link>
      <div className="collab-heading"><div><h1 id="collab-admin-title">{membership.community_name}</h1><p>Administrator controls for persisted membership and invitation evidence.</p></div><span className="collab-role">Administrator</span></div>
      <div className="collab-truth-note"><WarningCircle aria-hidden="true" size={20} weight="duotone" /><p>Administration affects this SQLite collaboration space only. It does not change or role-gate planning data.</p></div>

      <Tabs.Root className="collab-tabs" onValueChange={(value) => { setTab(value as AdminTab); setRequestError(null); announce(`${humanize(value)} administration selected.`); }} value={tab}>
        <Tabs.List aria-label="Administration tasks" className="collab-tab-list">
          <Tabs.Trigger value="members"><UsersThree aria-hidden="true" size={17} /> Members</Tabs.Trigger>
          <Tabs.Trigger value="invitations"><EnvelopeSimple aria-hidden="true" size={17} /> Invitations</Tabs.Trigger>
          <Tabs.Trigger value="audit"><ClockCounterClockwise aria-hidden="true" size={17} /> Audit events</Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content className="collab-tab-content" value="members">
          <div className="collab-section-heading"><div><h2>Members and roles</h2><p>Changing a role takes effect from persisted membership on the next request.</p></div></div>
          {requestError ? <ErrorMessage error={requestError} onRetry={() => void loadTab("members")} /> : null}
          {working && members.length === 0 ? <p className="collab-loading">Loading members.</p> : null}
          {members.length > 0 ? <ul className="collab-member-list">{members.map((member) => { const lastAdministrator = member.role === "ADMINISTRATOR" && administratorCount === 1; return <li key={member.user_id}><div><strong>{member.username}</strong><span>{member.user_id === session?.user.id ? "Current account" : "Community member"}</span></div><form onSubmit={(event) => void changeRole(event, member)}><label className="collab-sr-only" htmlFor={`collab-role-${member.user_id}`}>Role for {member.username}</label><select defaultValue={member.role} disabled={working || lastAdministrator} id={`collab-role-${member.user_id}`} name="role">{COMMUNITY_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}</select><Button disabled={working || lastAdministrator} size="2" type="submit">Save role</Button></form>{lastAdministrator ? <small>Keep at least one Administrator.</small> : null}</li>; })}</ul> : null}
        </Tabs.Content>

        <Tabs.Content className="collab-tab-content" value="invitations">
          <form className="collab-form collab-invitation-form" onSubmit={createInvitation}>
            <div className="collab-form-heading"><h2>Create a recipient-bound invitation</h2><p>The raw token is delivered once and never appears in the invitation list.</p></div>
            <div className="collab-field"><label htmlFor="collab-recipient">Username or email</label><input id="collab-recipient" maxLength={254} minLength={3} onChange={(event) => setRecipient(event.target.value)} required type="text" value={recipient} /></div>
            <div className="collab-field-row"><div className="collab-field"><label htmlFor="collab-invite-role">Role</label><select id="collab-invite-role" onChange={(event) => setInviteRole(event.target.value as CommunityRole)} value={inviteRole}>{COMMUNITY_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}</select></div><div className="collab-field"><label htmlFor="collab-invite-expiry">Expires</label><select id="collab-invite-expiry" onChange={(event) => setExpiry(Number(event.target.value))} value={expiry}><option value={3600}>In 1 hour</option><option value={86400}>In 24 hours</option><option value={604800}>In 7 days</option></select></div></div>
            {requestError ? <ErrorMessage error={requestError} /> : null}
            <Button className="collab-submit" disabled={working} ref={invitationSubmitRef} size="3" type="submit">{working ? "Creating" : "Create invitation"}</Button>
          </form>
          {deliveredToken ? <div aria-labelledby="collab-token-title" className="collab-token-delivery" ref={tokenRef} tabIndex={-1}><div><strong id="collab-token-title">Copy this token now</strong><p>It will not be shown again. Deliver it locally to the named recipient. Do not put it in a URL or log.</p></div><code>{deliveredToken}</code><div className="collab-token-actions"><Button onClick={() => void copyAndClearToken()} size="3"><Clipboard aria-hidden="true" size={17} /> Copy and hide</Button><Button onClick={() => { setDeliveredToken(null); announce("Invitation token dismissed and removed from the screen."); requestAnimationFrame(() => invitationSubmitRef.current?.focus()); }} size="3" variant="outline"><X aria-hidden="true" size={17} /> Dismiss</Button></div></div> : null}
          <div className="collab-section-heading"><div><h2>Invitation lifecycle</h2><p>Only redacted persisted state is listed here.</p></div></div>
          {working && invitations.length === 0 ? <p className="collab-loading">Loading invitations.</p> : null}
          {!working && invitations.length === 0 && !requestError ? <p className="collab-empty-line">No invitations have been created.</p> : null}
          {invitations.length > 0 ? <ul className="collab-invitation-list">{invitations.map((invitation) => <li key={invitation.id}><div><strong>{invitation.recipient}</strong><span>{roleLabel(invitation.role)}. {humanize(invitation.state)}. Expires {formatTime(invitation.expires_at)}.</span></div>{invitation.state === "PENDING" ? <Button color="red" disabled={working} onClick={() => void revokeInvitation(invitation)} size="2" variant="outline"><Trash aria-hidden="true" size={16} /> Revoke</Button> : null}</li>)}</ul> : null}
        </Tabs.Content>

        <Tabs.Content className="collab-tab-content" value="audit">
          <div className="collab-section-heading"><div><h2>Audit events</h2><p>Newest events first. Secret values are excluded by the backend contract.</p></div></div>
          {requestError ? <ErrorMessage error={requestError} onRetry={() => void loadTab("audit")} /> : null}
          {working && events.length === 0 ? <p className="collab-loading">Loading audit events.</p> : null}
          {!working && events.length === 0 && !requestError ? <p className="collab-empty-line">No audit events are available.</p> : null}
          {events.length > 0 ? <ol className="collab-audit-list">{events.map((event) => <li key={event.id}><div><strong>{humanize(event.event_type)}</strong><time dateTime={new Date(event.occurred_at * 1000).toISOString()}>{formatTime(event.occurred_at)}</time></div><details><summary>Event details</summary><dl><div><dt>Actor</dt><dd>{event.actor_user_id ?? "System"}</dd></div><div><dt>Subject</dt><dd>{event.subject_user_id ?? "Not applicable"}</dd></div><div><dt>Invitation</dt><dd>{event.invitation_id ?? "Not applicable"}</dd></div></dl>{Object.keys(event.metadata).length > 0 ? <pre>{JSON.stringify(event.metadata, null, 2)}</pre> : null}</details></li>)}</ol> : null}
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}
