"use client";

import { ArrowRight, CheckCircle, Plus, Ticket, UsersThree, WarningCircle } from "@phosphor-icons/react";
import { Button, Tabs } from "@radix-ui/themes";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiRequestError } from "../../lib/api";
import { authApi } from "../../lib/auth-api";
import type { CommunitySummary } from "../../lib/auth-types";
import { useIdentity } from "../../lib/identity-context";
import { isAbortError } from "../../lib/ui";

interface PanelError { code: string; message: string; status: number }

function panelError(error: unknown): PanelError {
  if (error instanceof ApiRequestError) return { code: error.code, message: error.message, status: error.status };
  return { code: "REQUEST_FAILED", message: "The collaboration request could not be completed.", status: 0 };
}

function ErrorMessage({ error, onRetry }: { error: PanelError; onRetry?: () => void }) {
  return <div className="collab-error" role="alert"><WarningCircle aria-hidden="true" size={20} weight="duotone" /><div><strong>{error.code}</strong><span>{error.message}</span></div>{onRetry ? <Button onClick={onRetry} size="2" variant="outline">Try again</Button> : null}</div>;
}

export default function CommunitiesPanel() {
  const identity = useIdentity();
  const { announce, invalidateSession, refreshSession, session } = identity;
  const [communities, setCommunities] = useState<CommunitySummary[]>([]);
  const [requestError, setRequestError] = useState<PanelError | null>(null);
  const [working, setWorking] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [inviteToken, setInviteToken] = useState("");
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
    const next = panelError(error);
    setRequestError(next);
    announce(next.message);
    if (next.status === 401 && next.code === "AUTHENTICATION_REQUIRED") invalidateSession(next.message);
  }, [announce, invalidateSession, isCurrent]);

  const loadCommunities = useCallback(async () => {
    if (!session) return;
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const next = await authApi.listCommunities(controller.signal);
      if (!isCurrent(generation, controller)) return;
      setCommunities(next);
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  }, [begin, handleFailure, isCurrent, session]);

  useEffect(() => {
    let timer: number | undefined;
    if (session) timer = window.setTimeout(() => void loadCommunities(), 0);
    else {
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    }
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [loadCommunities, session]);

  const createCommunity = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const created = await authApi.createCommunity({ name: name.trim(), slug: slug.trim().toLowerCase() }, controller.signal);
      if (!isCurrent(generation, controller)) return;
      setCommunities((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setName("");
      setSlug("");
      announce(`${created.name} collaboration space created.`);
      void refreshSession();
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  };

  const acceptInvitation = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const token = inviteToken.trim();
    setInviteToken("");
    const { controller, generation } = begin();
    setWorking(true);
    try {
      const accepted = await authApi.acceptInvitation(token, controller.signal);
      const next = await authApi.listCommunities(controller.signal);
      if (!isCurrent(generation, controller)) return;
      setCommunities(next);
      announce(`Invitation accepted for ${accepted.community_name}.`);
      void refreshSession();
    } catch (error) {
      handleFailure(error, generation, controller);
    } finally {
      if (isCurrent(generation, controller)) setWorking(false);
    }
  };

  if (identity.status === "bootstrapping") return <section aria-busy="true" className="collab-panel"><h1>Collaboration spaces</h1><p>Checking account access.</p></section>;

  if (!session) {
    return <section aria-labelledby="collab-title" className="collab-panel collab-signin-state"><UsersThree aria-hidden="true" size={30} weight="duotone" /><h1 id="collab-title">Collaboration spaces</h1><p>Sign in to create spaces, accept an invitation and see your persisted roles.</p><Button asChild size="3"><Link href="/login">Sign in <ArrowRight aria-hidden="true" size={17} /></Link></Button><Link className="collab-guest-link" href="/">Continue to the separate planning demo</Link></section>;
  }

  return (
    <section aria-labelledby="collab-title" className="collab-panel">
      <div className="collab-heading"><div><h1 id="collab-title">Collaboration spaces</h1><p>Manage local membership spaces without changing the fictional planning fixture.</p></div></div>
      <div className="collab-truth-note"><WarningCircle aria-hidden="true" size={20} weight="duotone" /><p>These persisted spaces are separate from the demo planning model. Opening one does not change solver, Project or resilience data.</p></div>
      <Tabs.Root className="collab-tabs" defaultValue="spaces" onValueChange={(value) => announce(`${value === "spaces" ? "Your spaces" : value === "create" ? "Create a space" : "Accept an invite"} selected.`)}>
        <Tabs.List aria-label="Collaboration tasks" className="collab-tab-list">
          <Tabs.Trigger value="spaces"><UsersThree aria-hidden="true" size={17} /> Your spaces</Tabs.Trigger>
          <Tabs.Trigger value="create"><Plus aria-hidden="true" size={17} /> Create</Tabs.Trigger>
          <Tabs.Trigger value="accept"><Ticket aria-hidden="true" size={17} /> Accept invite</Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content className="collab-tab-content" value="spaces">
          {requestError ? <ErrorMessage error={requestError} onRetry={() => void loadCommunities()} /> : null}
          {working && communities.length === 0 ? <p aria-live="polite" className="collab-loading">Loading your collaboration spaces.</p> : null}
          {!working && communities.length === 0 && !requestError ? <div className="collab-empty"><UsersThree aria-hidden="true" size={25} weight="duotone" /><h2>No collaboration spaces yet</h2><p>Create a space or accept a recipient-bound invitation.</p></div> : null}
          {communities.length > 0 ? <ul className="collab-space-list">{communities.map((community) => <li key={community.id}><div><strong>{community.name}</strong><span>{community.slug}</span><span className="collab-role">{community.role.charAt(0) + community.role.slice(1).toLowerCase()}</span></div><Button asChild size="2" variant="outline"><Link href={`/communities/${encodeURIComponent(community.id)}`}>{community.role === "ADMINISTRATOR" ? "Manage" : "View access"}<ArrowRight aria-hidden="true" size={16} /></Link></Button></li>)}</ul> : null}
        </Tabs.Content>

        <Tabs.Content className="collab-tab-content" value="create">
          <form className="collab-form" onSubmit={createCommunity}>
            <div className="collab-form-heading"><h2>Create a collaboration space</h2><p>You become its first Administrator.</p></div>
            <div className="collab-field"><label htmlFor="collab-community-name">Name</label><input id="collab-community-name" maxLength={120} onChange={(event) => setName(event.target.value)} required type="text" value={name} /></div>
            <div className="collab-field"><label htmlFor="collab-community-slug">Slug</label><input aria-describedby="collab-slug-help" id="collab-community-slug" maxLength={64} minLength={3} onChange={(event) => setSlug(event.target.value)} pattern="[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])?" required type="text" value={slug} /><span id="collab-slug-help">3-64 lowercase letters, numbers or hyphens. Start and end with a letter or number.</span></div>
            {requestError ? <ErrorMessage error={requestError} /> : null}
            <Button className="collab-submit" disabled={working} size="3" type="submit">{working ? "Creating" : "Create space"}</Button>
          </form>
        </Tabs.Content>

        <Tabs.Content className="collab-tab-content" value="accept">
          <form className="collab-form" onSubmit={acceptInvitation}>
            <div className="collab-form-heading"><h2>Accept an invitation</h2><p>The token works only for the username or email named by the Administrator.</p></div>
            <div className="collab-field"><label htmlFor="collab-invite-token">Invitation token</label><input autoComplete="off" id="collab-invite-token" maxLength={128} minLength={40} onChange={(event) => setInviteToken(event.target.value)} pattern="[A-Za-z0-9_-]+" required spellCheck="false" type="password" value={inviteToken} /><span>The token stays only in this form and is cleared when submitted.</span></div>
            {requestError ? <ErrorMessage error={requestError} /> : null}
            <Button className="collab-submit" disabled={working} size="3" type="submit">{working ? "Accepting" : "Accept invite"}</Button>
          </form>
        </Tabs.Content>
      </Tabs.Root>
      {communities.length > 0 ? <p className="collab-update-note"><CheckCircle aria-hidden="true" size={17} weight="duotone" /> Roles shown here come from the current authenticated session and community API.</p> : null}
    </section>
  );
}
