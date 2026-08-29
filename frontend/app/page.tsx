"use client";

import {
  ArrowClockwise,
  ArrowRight,
  BracketsCurly,
  Buildings,
  CaretDown,
  CaretRight,
  Check,
  CheckCircle,
  CircleNotch,
  Clock,
  Code,
  Cpu,
  Database,
  GitBranch,
  Info,
  Lightning,
  LinkSimple,
  ListChecks,
  LockKeyOpen,
  MagnifyingGlass,
  Plus,
  Sparkle,
  Toolbox,
  UserCircle,
  UsersThree,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";
import { Badge, Button, Theme } from "@radix-ui/themes";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiRequestError } from "../lib/api";
import type {
  AnalyseResponse,
  AssemblyTraceEntry,
  CatalystAction,
  CommunityState,
  CreateProjectResponse,
  DemoFixture,
  ExplainResponse,
  InitiativeAnalysisResult,
  InitiativeBlueprint,
  PlanResponse,
  SolverStatus,
  TransitionResponse,
  UnlockResponse,
} from "../lib/types";

type RequestKey = "demo" | "analyse" | "explain" | "unlock" | "plan" | "transition" | "verify" | "project";
type RequestState = "idle" | "loading" | "success" | "error";
type BlockKind = "person" | "space" | "resource";

interface UiError {
  code: string;
  message: string;
}

interface WorkflowBinding {
  generation: number;
  initiativeId: string;
  sourceStateId: string;
  pathKey: string;
}

const REQUEST_KEYS: RequestKey[] = ["demo", "analyse", "explain", "unlock", "plan", "transition", "verify", "project"];

const initialRequestStates: Record<RequestKey, RequestState> = {
  demo: "loading",
  analyse: "idle",
  explain: "idle",
  unlock: "idle",
  plan: "idle",
  transition: "idle",
  verify: "idle",
  project: "idle",
};

const initialRequestErrors: Partial<Record<RequestKey, UiError>> = {};

function humanize(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function compactId(value: string): string {
  return value.replaceAll("_", " ").toLowerCase();
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function requireResponse(condition: unknown, message: string): asserts condition {
  if (!condition) throw new ApiRequestError(message, 502, "RESPONSE_CONTRACT_ERROR");
}

function sameOrderedIds(actual: string[], expected: string[]): boolean {
  return actual.length === expected.length && actual.every((id, index) => id === expected[index]);
}

function defaultProjectMetadata(initiative: InitiativeBlueprint | undefined): ProjectMetadata {
  const name = initiative?.name ?? "Community initiative";
  return {
    title: `${name} — Saturday delivery`,
    short_description: `${name} assembled from verified people, venue, time and shared resources.`,
    objective: `Deliver ${name.toLowerCase()} with every operational dependency verified before launch.`,
  };
}

function statusLabel(status: SolverStatus | undefined): string {
  if (!status) return "Awaiting compile";
  if (status === "OPTIMAL" || status === "FEASIBLE") return "Buildable";
  if (status === "INFEASIBLE") return "Blocked";
  return "Unknown";
}

function statusClass(status: SolverStatus | undefined): string {
  if (status === "OPTIMAL" || status === "FEASIBLE") return "status-success";
  if (status === "INFEASIBLE") return "status-blocked";
  if (status === "UNKNOWN") return "status-unknown";
  return "status-neutral";
}

function StatusIcon({ status, size = 15 }: { status: SolverStatus | undefined; size?: number }) {
  if (status === "OPTIMAL" || status === "FEASIBLE") return <CheckCircle aria-hidden="true" size={size} weight="fill" />;
  if (status === "INFEASIBLE") return <XCircle aria-hidden="true" size={size} weight="fill" />;
  if (status === "UNKNOWN") return <WarningCircle aria-hidden="true" size={size} weight="fill" />;
  return <Clock aria-hidden="true" size={size} weight="bold" />;
}

function StatusBadge({ status, label }: { status: SolverStatus | undefined; label?: string }) {
  return (
    <Badge className={`status-badge ${statusClass(status)}`}>
      <StatusIcon status={status} />
      <span>{label ?? statusLabel(status)}</span>
    </Badge>
  );
}

function BlockIcon({ kind, size = 18 }: { kind: BlockKind; size?: number }) {
  if (kind === "person") return <UserCircle aria-hidden="true" size={size} weight="duotone" />;
  if (kind === "space") return <Buildings aria-hidden="true" size={size} weight="duotone" />;
  return <Toolbox aria-hidden="true" size={size} weight="duotone" />;
}

function LoadingDots({ label }: { label: string }) {
  return (
    <span className="loading-label">
      <CircleNotch aria-hidden="true" className="spin" size={15} weight="bold" />
      {label}
    </span>
  );
}

function ErrorNotice({ error, onRetry, retryLabel = "Try again" }: { error: UiError; onRetry?: () => void; retryLabel?: string }) {
  return (
    <div className="notice notice-error" role="alert">
      <XCircle aria-hidden="true" size={19} weight="fill" />
      <div className="notice-copy">
        <strong>{error.message}</strong>
        <span className="mono">{error.code}</span>
      </div>
      {onRetry ? <Button className="button-quiet" size="1" variant="outline" onClick={onRetry}>{retryLabel}</Button> : null}
    </div>
  );
}

function UnknownNotice({ copy = "The bounded solver returned UNKNOWN. No blocked or buildable claim is being made." }: { copy?: string }) {
  return (
    <div className="notice notice-unknown" role="status">
      <WarningCircle aria-hidden="true" size={19} weight="fill" />
      <div className="notice-copy"><strong>Result unavailable</strong><span>{copy}</span></div>
    </div>
  );
}

function InlineSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="inline-skeleton" aria-label="Loading">
      {Array.from({ length: lines }, (_, index) => <span className={index === lines - 1 ? "skeleton-line skeleton-line-short" : "skeleton-line"} key={index} />)}
    </div>
  );
}

function CommunityCanvas({ community, analyses, selectedId, onSelect, transition, viewMode, onViewModeChange }: { community: CommunityState; analyses: Record<string, InitiativeAnalysisResult>; selectedId: string; onSelect: (id: string) => void; transition: TransitionResponse | null; viewMode: "graph" | "list"; onViewModeChange: (view: "graph" | "list") => void }) {
  const activePersonIds = useMemo(() => {
    const ids = new Set<string>();
    Object.values(analyses).forEach((result) => result.assignments.forEach((assignment) => ids.add(assignment.person_id)));
    Object.keys(transition?.diff.added_capabilities ?? {}).forEach((id) => ids.add(id));
    return ids;
  }, [analyses, transition]);

  return (
    <section className="region canvas-region" aria-labelledby="community-canvas-title">
      <div className="region-heading">
        <div><p className="section-kicker">Community canvas</p><h2 id="community-canvas-title">The people and places that make a plan possible</h2></div>
        <div className="canvas-heading-tools"><div className="view-toggle" role="group" aria-label="Community view"><button aria-pressed={viewMode === "graph"} onClick={() => onViewModeChange("graph")} type="button"><GitBranch aria-hidden="true" size={16} />Graph view</button><button aria-pressed={viewMode === "list"} onClick={() => onViewModeChange("list")} type="button"><ListChecks aria-hidden="true" size={16} />List view</button></div><span className="region-count mono">{community.state_id}</span></div>
      </div>
      <div className="canvas-meta">
        <span><UsersThree aria-hidden="true" size={15} weight="duotone" />{community.people.length} people</span>
        <span><Buildings aria-hidden="true" size={15} weight="duotone" />{community.spaces.length} space</span>
        <span><Toolbox aria-hidden="true" size={15} weight="duotone" />{community.resources.length} resource pools</span>
      </div>
      {viewMode === "graph" ? <div className="community-stage" aria-label="Community blocks and their relationships">
        <svg className="connection-layer" viewBox="0 0 1000 540" preserveAspectRatio="none" aria-hidden="true">
          <path className={activePersonIds.size > 0 ? "connection active" : "connection"} d="M244 122 C366 122 414 122 548 122" />
          <path className={activePersonIds.size > 0 ? "connection active" : "connection"} d="M244 152 C360 190 426 316 548 378" />
          <path className="connection" d="M244 378 C358 350 420 246 548 164" />
          <path className="connection" d="M244 408 C378 408 422 408 548 408" />
          <circle className="connection-node" cx="244" cy="122" r="5" /><circle className="connection-node" cx="548" cy="122" r="5" />
          <circle className="connection-node" cx="244" cy="378" r="5" /><circle className="connection-node" cx="548" cy="408" r="5" />
        </svg>
        <div className="cluster-grid">
          {community.organisations.map((organisation, index) => {
            const people = community.people.filter((person) => person.organisation_id === organisation.id);
            const spaces = community.spaces.filter((space) => space.organisation_id === organisation.id);
            const resources = community.resources.filter((resource) => resource.organisation_id === organisation.id);
            return (
              <article className={`org-cluster org-cluster-${index + 1}`} key={organisation.id}>
                <div className="cluster-heading"><span className="cluster-icon"><UsersThree aria-hidden="true" size={17} weight="duotone" /></span><div><h3>{organisation.name}</h3><span className="mono">{organisation.id}</span></div></div>
                <div className="cluster-blocks">
                  {people.map((person) => (
                    <button aria-pressed={selectedId === person.id} className={`community-block ${activePersonIds.has(person.id) ? "community-block-active" : ""}`} key={person.id} onClick={() => onSelect(person.id)} type="button">
                      <span className="block-icon block-icon-person"><BlockIcon kind="person" /></span><span className="block-copy"><strong>{person.name}</strong><small>{person.id} / {person.capabilities.map(humanize).join(", ") || "Learner"} / {person.languages.map((language) => language.toUpperCase()).join(", ")} / {person.available_slots.join(", ")}</small></span>{activePersonIds.has(person.id) ? <Check aria-label="Assigned" className="block-check" size={15} weight="bold" /> : null}
                    </button>
                  ))}
                  {spaces.map((space) => (
                    <button aria-pressed={selectedId === space.id} className={`community-block ${selectedId === space.id ? "community-block-selected" : ""}`} key={space.id} onClick={() => onSelect(space.id)} type="button">
                      <span className="block-icon block-icon-space"><BlockIcon kind="space" /></span><span className="block-copy"><strong>{space.name}</strong><small>{space.id} / capacity {space.capacity} / {space.features.map(humanize).join(", ")} / {space.available_slots.join(", ")}</small></span>
                    </button>
                  ))}
                  {resources.map((resource) => (
                    <button aria-pressed={selectedId === resource.id} className={`community-block ${selectedId === resource.id ? "community-block-selected" : ""}`} key={resource.id} onClick={() => onSelect(resource.id)} type="button">
                      <span className="block-icon block-icon-resource"><BlockIcon kind="resource" /></span><span className="block-copy"><strong>{resource.name}</strong><small>{resource.id} / {resource.quantity} available / {resource.available_slots.join(", ")}</small></span>
                    </button>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </div> : <div className="community-list-view" aria-label="Community blocks as a list">{community.organisations.map((organisation) => { const people = community.people.filter((person) => person.organisation_id === organisation.id); const spaces = community.spaces.filter((space) => space.organisation_id === organisation.id); const resources = community.resources.filter((resource) => resource.organisation_id === organisation.id); return <section className="community-list-group" aria-labelledby={`list-${organisation.id}`} key={organisation.id}><h3 id={`list-${organisation.id}`}>{organisation.name}</h3><span className="mono">{organisation.id}</span><ul>{people.map((person) => <li key={person.id}><button aria-pressed={selectedId === person.id} onClick={() => onSelect(person.id)} type="button"><BlockIcon kind="person" /><span><strong>{person.name}</strong><small>{person.id} / {person.capabilities.map(humanize).join(", ") || "Learner"} / {person.languages.map((language) => language.toUpperCase()).join(", ")} / {person.available_slots.join(", ")}</small></span>{activePersonIds.has(person.id) ? <Check aria-label="Assigned" size={16} weight="bold" /> : null}</button></li>)}{spaces.map((space) => <li key={space.id}><button aria-pressed={selectedId === space.id} onClick={() => onSelect(space.id)} type="button"><BlockIcon kind="space" /><span><strong>{space.name}</strong><small>{space.id} / capacity {space.capacity} / {space.features.map(humanize).join(", ")} / {space.available_slots.join(", ")}</small></span></button></li>)}{resources.map((resource) => <li key={resource.id}><button aria-pressed={selectedId === resource.id} onClick={() => onSelect(resource.id)} type="button"><BlockIcon kind="resource" /><span><strong>{resource.name}</strong><small>{resource.id} / {resource.quantity} available / {resource.available_slots.join(", ")}</small></span></button></li>)}</ul></section>; })}</div>}
      <div className="canvas-footer"><span><LinkSimple aria-hidden="true" size={15} weight="bold" />Lines show possible composition paths; cobalt marks a returned assignment.</span><span className="mono">{community.parent_state_id ? `from ${community.parent_state_id}` : "baseline fixture"}</span></div>
      <ul className="sr-only" aria-label="Community relationships"><li>People can connect to organisations through their capability blocks.</li><li>Shared spaces and resources connect initiatives to the community canvas.</li>{Object.entries(analyses).flatMap(([initiativeId, result]) => result.assignments.map((assignment) => <li key={`${initiativeId}-${assignment.role_instance_id}`}>{assignment.person_id} is assigned to {assignment.role_instance_id} for {initiativeId}.</li>))}</ul>
    </section>
  );
}

function InitiativeRail({ initiatives, analyses, verifiedResult, plan, selectedId, onSelect }: { initiatives: InitiativeBlueprint[]; analyses: Record<string, InitiativeAnalysisResult>; verifiedResult: InitiativeAnalysisResult | null; plan: PlanResponse | null; selectedId: string; onSelect: (id: string) => void }) {
  const effectiveResults = useMemo(() => {
    const resultMap = { ...analyses };
    if (verifiedResult) resultMap[verifiedResult.initiative_id] = verifiedResult;
    return resultMap;
  }, [analyses, verifiedResult]);
  const resultValues = Object.values(effectiveResults);
  const buildableCount = resultValues.filter((result) => result.status === "OPTIMAL" || result.status === "FEASIBLE").length;
  const blockedCount = resultValues.filter((result) => result.status === "INFEASIBLE").length;
  return (
    <section className="rail-region" aria-labelledby="initiatives-title">
      <div className="region-heading rail-heading"><div><p className="section-kicker">Initiatives</p><h2 id="initiatives-title">What is individually buildable</h2></div><span className="region-count">{initiatives.length} briefs</span></div>
      <div className="rail-summary"><span><span className="summary-dot dot-success" />{buildableCount} individually buildable</span><span><span className="summary-dot dot-blocked" />{blockedCount} blocked</span>{plan ? <span><span className="summary-dot dot-cobalt" />1 path found</span> : null}</div>
      <div className="initiative-list">
        {initiatives.map((initiative, index) => {
          const result = effectiveResults[initiative.id];
          const isPathTarget = plan?.target_initiative_id === initiative.id && (plan.target_status_after === "OPTIMAL" || plan.target_status_after === "FEASIBLE");
          const shownStatus = result?.status ?? (isPathTarget ? plan.target_status_before : undefined);
          return (
            <button aria-current={selectedId === initiative.id ? "true" : undefined} className={`initiative-card ${selectedId === initiative.id ? "initiative-card-selected" : ""}`} key={initiative.id} onClick={() => onSelect(initiative.id)} type="button">
              <div className="initiative-card-topline"><span className="initiative-index mono">{String(index + 1).padStart(2, "0")}</span><StatusBadge status={shownStatus} /></div>
              <h3>{initiative.name}</h3><p>{initiative.roles.length} roles / {initiative.duration_slots} time blocks / {initiative.resources.length} resource requirement</p>
              <div className="requirement-sockets" aria-label={`${statusLabel(shownStatus)} requirement proof`}>
                {["Roles", "Time", "Resources"].map((label) => <span className={`requirement-socket ${shownStatus === "OPTIMAL" || shownStatus === "FEASIBLE" ? "requirement-socket-closed" : "requirement-socket-pending"}`} key={label}><span aria-hidden="true" />{label}</span>)}
              </div>
              <div className="initiative-card-footer"><span className="mono">{compactId(initiative.id)}</span>{isPathTarget && shownStatus === "INFEASIBLE" ? <span className="path-pending">Successor path ready</span> : null}<CaretRight aria-hidden="true" size={17} weight="bold" /></div>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function ActionButton({ step, label, hint, icon, onClick, disabled, loading, complete, primary }: { step: number; label: string; hint: string; icon: React.ReactNode; onClick: () => void; disabled?: boolean; loading?: boolean; complete?: boolean; primary?: boolean }) {
  return (
    <Button aria-busy={loading} className={`action-button ${primary ? "action-button-primary" : ""} ${complete ? "action-button-complete" : ""}`} disabled={disabled || loading} onClick={onClick} size="2" variant={primary ? "solid" : "outline"}>
      <span className="action-step mono">{String(step).padStart(2, "0")}</span><span className="action-button-icon">{loading ? <CircleNotch aria-hidden="true" className="spin" size={18} weight="bold" /> : complete ? <Check aria-hidden="true" size={18} weight="bold" /> : icon}</span><span className="action-button-copy"><strong>{label}</strong><small>{loading ? "Working" : hint}</small></span>{!loading && !complete ? <ArrowRight aria-hidden="true" className="action-arrow" size={16} weight="bold" /> : null}
    </Button>
  );
}

function TraceTable({ entries, community }: { entries: AssemblyTraceEntry[]; community: CommunityState }) {
  const names = new Map<string, string>([...community.people.map((person) => [person.id, person.name] as [string, string]), ...community.spaces.map((space) => [space.id, space.name] as [string, string]), ...community.resources.map((resource) => [resource.id, resource.name] as [string, string])]);
  return <table className="trace-table"><caption className="sr-only">Assembly trace</caption><thead><tr className="trace-row trace-head"><th className="trace-kind" scope="col">Kind</th><th className="trace-requirement" scope="col">Requirement</th><th className="trace-selection" scope="col">Selected capacity</th><th className="trace-facts" scope="col">Proof facts</th></tr></thead><tbody>{entries.map((entry) => <tr className="trace-row" key={`${entry.requirement_kind}-${entry.requirement_id}`}><td className="trace-kind"><span className="trace-marker" />{humanize(entry.requirement_kind)}</td><td className="trace-requirement mono">{entry.requirement_id}</td><td className="trace-selection">{entry.selected_ids.map((id) => <span className="selection-tag" key={id}>{names.get(id) ?? id}</span>)}</td><td className="trace-facts">{Object.entries(entry.facts).map(([key, value]) => <span key={key}>{humanize(key)}: {String(value)}</span>)}</td></tr>)}</tbody></table>;
}

function AnalysisPanel({ result, community, requestState, error, onRetry }: { result: InitiativeAnalysisResult | null; community: CommunityState; requestState: RequestState; error?: UiError; onRetry: () => void }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Compiling the selected brief…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Recompile" />;
  if (!result) return <div className="empty-panel"><div className="empty-icon"><BracketsCurly aria-hidden="true" size={23} weight="duotone" /></div><div><strong>Compile a brief to see the assembly trace.</strong><span>The solver response will populate assignments, facts and technical evidence here.</span></div></div>;
  if (result.status === "UNKNOWN") return <UnknownNotice />;
  if (result.status === "INFEASIBLE") return <div className="result-callout result-callout-blocked"><div className="result-callout-icon"><XCircle aria-hidden="true" size={22} weight="fill" /></div><div><strong>This brief is blocked in the current state.</strong><span>Use WHY BLOCKED? to inspect the exact requirement set that prevents assembly.</span></div></div>;
  return <div className="analysis-success"><div className="result-callout result-callout-success"><div className="result-callout-icon"><CheckCircle aria-hidden="true" size={22} weight="fill" /></div><div><strong>Assembly found for this brief.</strong><span>Every shown assignment and fact below came from the solver response.</span></div><div className="result-objective"><span>Objective</span><strong className="mono">{result.objective_value ?? "Not set"}</strong></div></div>{result.assembly_trace.length > 0 ? <TraceTable entries={result.assembly_trace} community={community} /> : <div className="empty-subtle">The solver returned no assembly trace entries for this result.</div>}</div>;
}

function BlockingFactRow({ fact }: { fact: ExplainResponse["blocking_requirement_sets"][number]["facts"][number] }) {
  const hasCounts = fact.required !== null && fact.available !== null;
  const shortfall = hasCounts ? Math.max((fact.required ?? 0) - (fact.available ?? 0), 0) : null;
  return <div className="fact-row"><span className="fact-label">{fact.capability ? humanize(fact.capability) : fact.language ? `Language: ${fact.language}` : fact.requirement_id ?? "Requirement"}</span>{hasCounts ? <span className="fact-value"><span><small>Required</small><strong className="mono">{fact.required}</strong></span><span><small>Available</small><strong className="mono">{fact.available}</strong></span><span className="fact-shortfall"><small>Shortfall</small><strong className="mono">{shortfall}</strong></span></span> : null}{fact.note ? <span className="fact-note">{fact.note}</span> : null}{fact.relevant_ids.length > 0 ? <span className="fact-ids mono">Source: {fact.relevant_ids.join(", ")}</span> : null}</div>;
}

function BlockerPanel({ explanation, requestState, error, onRetry }: { explanation: ExplainResponse | null; requestState: RequestState; error?: UiError; onRetry: () => void }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Checking blocking requirements…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Recheck" />;
  if (!explanation) return <div className="empty-subtle">Select a blocked initiative, then run WHY BLOCKED? for bounded evidence.</div>;
  if (explanation.status === "UNKNOWN") return <UnknownNotice copy="The explanation solver returned UNKNOWN. The current blocker is not being inferred." />;
  if (explanation.blocking_requirement_sets.length === 0) return <div className="empty-subtle">The backend returned no blocking requirement set for this result.</div>;
  return <div className="blocker-list">{explanation.blocking_requirement_sets.map((set, index) => <div className="blocker-item" key={`${set.groups.join("-")}-${index}`}><div className="blocker-item-heading"><span className="blocker-number mono">0{index + 1}</span><div><strong>{set.groups.map(humanize).join(" + ")}</strong><span>{set.restored_feasibility_when_relaxed ? "Feasibility returns when this set is relaxed." : "Relaxing this set did not restore feasibility."}</span></div></div><div className="fact-list">{set.facts.map((fact, factIndex) => <BlockingFactRow fact={fact} key={`${fact.capability ?? fact.language ?? fact.requirement_id ?? "fact"}-${factIndex}`} />)}</div></div>)}<div className="method-line"><MagnifyingGlass aria-hidden="true" size={15} weight="bold" />{explanation.method.replaceAll("_", " ")} / {explanation.solver_runs} bounded solver runs</div></div>;
}

function UnlockPanel({ unlock, plan, actions, requestState, planState, error, planError, onRetry }: { unlock: UnlockResponse | null; plan: PlanResponse | null; actions: CatalystAction[]; requestState: RequestState; planState: RequestState; error?: UiError; planError?: UiError; onRetry: () => void }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Comparing modelled interventions…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Search again" />;
  if (!unlock) return <div className="empty-subtle">Run FIND MINIMUM UNLOCK to compare the finite intervention catalogue.</div>;
  if (unlock.resulting_status === "UNKNOWN") return <UnknownNotice copy="The intervention search returned UNKNOWN. No unlock is being presented as sufficient." />;
  const selectedActions = unlock.interventions.map((id) => actions.find((action) => action.id === id)).filter((action): action is CatalystAction => Boolean(action));
  const alternativeActions = actions.filter((action) => !unlock.interventions.includes(action.id)).sort((left, right) => left.cost - right.cost);
  const recruitmentActions = actions.filter((action) => action.id.startsWith("RECRUIT_HELPER"));
  const recruitmentCost = recruitmentActions.reduce((total, action) => total + action.cost, 0);
  const alternativeVerdict = (action: CatalystAction) => action.id === "BORROW_TWO_LAPTOPS" ? "Invalid: does not repair the capability shortfall" : action.id.startsWith("RECRUIT_HELPER") ? "Insufficient alone: repairs 1 of 2" : "Not sufficient alone";
  return <div className="unlock-content"><div className="unlock-result"><div className="unlock-result-icon"><LockKeyOpen aria-hidden="true" size={22} weight="duotone" /></div><div><span className="section-kicker">Minimum modelled unlock</span><strong>{selectedActions.map((action) => action.name).join(" + ") || unlock.interventions.join(", ")}</strong><span>Returns {unlock.resulting_status.toLowerCase()} at a total cost of <b className="mono">{unlock.total_cost}</b>.</span></div><StatusBadge status={unlock.resulting_status} /></div><div className="comparison-grid"><div className="comparison-column comparison-column-selected"><span className="comparison-label">Selected valid path</span>{selectedActions.map((action) => <div className="comparison-row" key={action.id}><CheckCircle aria-hidden="true" size={16} weight="fill" /><span><b>{action.name}</b><small>Minimum sufficient intervention</small></span><strong className="mono">{action.cost}</strong></div>)}<div className="comparison-total"><span>Total cost</span><strong className="mono">{unlock.total_cost}</strong></div></div><div className="comparison-column"><span className="comparison-label">Other catalogue options</span>{alternativeActions.slice(0, 3).map((action) => <div className="comparison-row comparison-row-muted" key={action.id}><span><b>{action.name}</b><small>{alternativeVerdict(action)}</small></span><strong className="mono">{action.cost}</strong></div>)}{recruitmentActions.length > 1 ? <div className="comparison-row comparison-row-muted"><span><b>Recruit both helpers</b><small>Valid: repairs 2 of 2, but costs more</small></span><strong className="mono">{recruitmentCost}</strong></div> : null}<div className="comparison-total"><span>Ordered paths evaluated</span><strong className="mono">{unlock.candidate_paths_evaluated}</strong></div></div></div>{planState === "loading" ? <div className="plan-loading"><LoadingDots label="Tracing the successor state" /></div> : null}{planError ? <ErrorNotice error={planError} onRetry={onRetry} retryLabel="Trace path" /> : null}{plan ? <PlanTrace plan={plan} actions={actions} /> : null}</div>;
}

function PlanTrace({ plan, actions }: { plan: PlanResponse; actions: CatalystAction[] }) {
  const actionNames = new Map(actions.map((action) => [action.id, action.name]));
  return <div className="plan-trace"><div className="plan-heading"><GitBranch aria-hidden="true" size={17} weight="duotone" /><strong>Depth-two path</strong><span className="mono">{plan.nodes.length} nodes</span></div><div className="path-steps">{plan.states.map((stateId, index) => <div className="path-step" key={stateId}><span className={`path-node ${index === plan.states.length - 1 ? "path-node-final" : ""}`}><span className="mono">{stateId}</span>{index === plan.states.length - 1 ? <Check aria-label="Target state" size={14} weight="bold" /> : null}</span>{index < plan.states.length - 1 ? <span className="path-arrow"><ArrowRight aria-hidden="true" size={16} weight="bold" /><small>{actionNames.get(plan.path[index]) ?? plan.path[index]}</small></span> : null}</div>)}</div><div className="plan-foot"><span>Before <StatusBadge status={plan.target_status_before} /></span><ArrowRight aria-hidden="true" size={15} /><span>After <StatusBadge status={plan.target_status_after} /></span><span className="mono">cost {plan.total_cost}</span></div></div>;
}

function TransitionPanel({ transition, successorResult, requestState, error, verifyError, onRetry }: { transition: TransitionResponse | null; successorResult: InitiativeAnalysisResult | null; requestState: RequestState; error?: UiError; verifyError?: UiError; onRetry: () => void }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Applying catalyst to a new immutable state…" /><InlineSkeleton lines={2} /></div>;
  if (error && !transition) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Apply again" />;
  if (!transition) return <div className="empty-subtle">Apply the returned catalyst path to create a successor state.</div>;
  const capabilityChanges = Object.entries(transition.diff.added_capabilities);
  const hasChanges = capabilityChanges.length > 0 || transition.diff.added_people.length > 0 || Object.keys(transition.diff.resource_quantity_changes).length > 0;
  return <div className="transition-content">{error ? <ErrorNotice error={error} onRetry={onRetry} retryLabel="Apply again" /> : null}<div className="transition-banner"><div className="transition-state"><span className="mono">{transition.predecessor_state_id}</span><ArrowRight aria-hidden="true" size={17} weight="bold" /><span className="mono transition-state-next">{transition.successor_state.state_id}</span></div><div><strong>Successor state created</strong><span>The predecessor remains unchanged. The Clinic stays blocked until the returned state is verified.</span></div></div>{hasChanges ? <div className="diff-list">{capabilityChanges.map(([personId, capabilities]) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personId}</strong> gains {capabilities.map(humanize).join(", ")}</span></div>)}{transition.diff.added_people.map((personId) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personId}</strong> joins the community state</span></div>)}{Object.entries(transition.diff.resource_quantity_changes).map(([resourceId, quantity]) => <div className="diff-row" key={resourceId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{resourceId}</strong> changes by {quantity}</span></div>)}</div> : <div className="empty-subtle">The transition returned no machine-readable changes.</div>}{verifyError ? <ErrorNotice error={verifyError} /> : null}{successorResult ? (successorResult.status === "UNKNOWN" ? <UnknownNotice copy="The successor-state verification returned UNKNOWN. The clinic is not being marked buildable; VERIFY remains available to retry." /> : <div className={`verification-result ${successorResult.status === "INFEASIBLE" ? "verification-result-blocked" : "verification-result-success"}`}><StatusIcon status={successorResult.status} size={21} /><div><strong>{successorResult.status === "INFEASIBLE" ? "The catalyst did not unlock this brief." : "Verified: the clinic is buildable in the successor state."}</strong><span>Verification used the returned {transition.successor_state.state_id} community state.</span></div></div>) : <div className="verification-prompt"><CheckCircle aria-hidden="true" size={20} weight="duotone" /><div><strong>Successor proof is ready to run.</strong><span>Continue with the single VERIFY NEW STATE action above.</span></div></div>}</div>;
}

interface ProjectMetadata {
  title: string;
  short_description: string;
  objective: string;
}

function ProjectCreationPanel({ initiative, proof, path, metadata, response, requestState, error, onMetadataChange, onCreate, onOpenInspector }: { initiative: InitiativeBlueprint; proof: InitiativeAnalysisResult; path: string[]; metadata: ProjectMetadata; response: CreateProjectResponse | null; requestState: RequestState; error?: UiError; onMetadataChange: (metadata: ProjectMetadata) => void; onCreate: () => void; onOpenInspector: () => void }) {
  const project = response?.project;
  const loading = requestState === "loading";
  const ready = project?.status === "READY";
  return <section className="project-region" aria-labelledby="project-creation-title"><div className="project-region-heading"><div><p className="section-kicker">Executable project</p><h2 id="project-creation-title">Create a project from this verified plan</h2><p>The server replays the disclosed path and derives every assignment, readiness check, venue and resource allocation from a fresh solver proof.</p></div><span className="proof-chip"><CheckCircle aria-hidden="true" size={17} weight="fill" />{proof.status} proof</span></div><form aria-busy={loading} className="project-form" onSubmit={(event) => { event.preventDefault(); if (!loading) onCreate(); }}><div className="project-proof-line"><span><strong>Proof state</strong><span className="mono">{path.length === 0 ? "Base state / explicit [] path" : `${path.length} catalyst / ${path.join(" → ")}`}</span></span><span><strong>Initiative</strong><span>{initiative.name}</span></span></div><label><span>Project title</span><input disabled={loading} maxLength={100} minLength={3} onChange={(event) => onMetadataChange({ ...metadata, title: event.target.value })} required value={metadata.title} /></label><label><span>Short description</span><textarea disabled={loading} maxLength={280} minLength={20} onChange={(event) => onMetadataChange({ ...metadata, short_description: event.target.value })} required rows={3} value={metadata.short_description} /></label><label><span>Objective</span><textarea disabled={loading} maxLength={280} minLength={20} onChange={(event) => onMetadataChange({ ...metadata, objective: event.target.value })} required rows={3} value={metadata.objective} /></label>{error && !loading ? <ErrorNotice error={error} onRetry={onCreate} retryLabel="Create again" /> : null}<Button className="create-project-button" disabled={loading} size="3" type="submit">{loading ? <LoadingDots label="Replaying and verifying plan…" /> : <><Sparkle aria-hidden="true" size={18} weight="fill" />CREATE PROJECT</>}</Button></form>{project ? <article className={`project-detail ${ready ? "project-detail-ready" : "project-detail-not-ready"}`} aria-labelledby="project-detail-title"><div className="project-detail-hero"><div><p className="section-kicker">{ready ? "Ready for delivery" : "Readiness gaps remain"}</p><h2 id="project-detail-title">{project.title}</h2><p>{project.short_description}</p></div><span className={`project-ready-badge ${ready ? "" : "project-not-ready-badge"}`}>{ready ? <CheckCircle aria-hidden="true" size={18} weight="fill" /> : <WarningCircle aria-hidden="true" size={18} weight="fill" />}{project.status}</span></div><div className="project-objective"><strong>Objective</strong><p>{project.objective}</p></div><dl className="project-facts"><div><dt>When</dt><dd>{humanize(project.schedule.start_slot)}–{humanize(project.schedule.end_slot)} / {project.schedule.duration_slots} slots</dd></div><div><dt>Where</dt><dd>{project.venue.venue_name} / capacity {project.participant_capacity}</dd></div><div><dt>Host organisation</dt><dd>{project.host_organisation_name}</dd></div><div><dt>Proof</dt><dd className="mono">{project.base_state_id} → {project.verified_state_id}</dd></div></dl><div className="project-detail-grid"><section aria-labelledby="operational-team-title"><h3 id="operational-team-title">Operational team</h3><ul className="assignment-list">{project.operational_assignments.map((assignment) => <li key={assignment.role_id}><span className="assignment-status"><Check aria-hidden="true" size={15} weight="bold" /></span><div><strong>{assignment.role_label}</strong><span>{assignment.person_name} / {assignment.organisation_name}</span><small>{[...assignment.matched_capabilities, ...assignment.matched_languages].map(humanize).join(" / ") || "Availability matched"}</small></div></li>)}</ul></section><section aria-labelledby="readiness-title"><h3 id="readiness-title">Constraint-derived readiness</h3><ul className="readiness-list">{project.readiness.checks.map((check) => <li className={check.ready ? "readiness-ready" : "readiness-missing"} key={check.check_id}>{check.ready ? <CheckCircle aria-hidden="true" size={17} weight="fill" /> : <XCircle aria-hidden="true" size={17} weight="fill" />}<div><strong>{check.ready ? "Ready: " : "Missing: "}{check.label}</strong><span>{check.evidence.join(" / ")}</span></div></li>)}</ul></section></div><div className="project-detail-grid project-detail-grid-compact"><section><h3>Resources &amp; access</h3>{project.resources.map((resource) => <p key={resource.resource_id}><strong>{resource.resource_name}</strong><br />{resource.quantity_required} allocated / {resource.quantity_available} available</p>)}<p><strong>Accessibility</strong><br />{project.accessibility_requirements.map(humanize).join(", ") || "No additional requirements declared"}</p></section><section><h3>Capabilities &amp; languages</h3><p><strong>Modules</strong><br />{project.capability_modules.map(humanize).join(", ")}</p><p><strong>Operational languages</strong><br />{project.supported_languages.map((language) => language.toUpperCase()).join(", ")}</p></section></div><footer className="project-proof-footer"><span>{ready ? <CheckCircle aria-hidden="true" size={16} weight="fill" /> : <WarningCircle aria-hidden="true" size={16} weight="fill" />}Fresh server verification: {response.verification.status} / Project {project.status}</span><span className="source-plan-control"><span className="mono">{project.source_plan_id}</span><Button onClick={onOpenInspector} size="2" type="button" variant="outline"><Code aria-hidden="true" size={16} />View source proof</Button></span></footer></article> : null}</section>;
}

function SelectedTeamFacts({ response }: { response: CreateProjectResponse }) {
  return <section className="selected-team-facts" aria-labelledby="selected-team-facts-title"><h2 id="selected-team-facts-title">Selected-person capacity facts</h2><p>Full facts from the verified community state, separate from the narrower requirement matches above.</p><ul>{response.project.operational_assignments.map((assignment) => <li key={assignment.role_id}><strong>{assignment.person_name}</strong><span>{assignment.person_capabilities.map(humanize).join(", ") || "No capabilities listed"}</span><span>{assignment.person_languages.map((language) => language.toUpperCase()).join(", ") || "No languages listed"}</span></li>)}</ul></section>;
}

function TechnicalInspector({ compile, selectedResult, explanation, unlock, plan, transition, projectResponse, fixtureVersion, inspectorRef, open, onOpenChange }: { compile: AnalyseResponse["compile"] | null; selectedResult: InitiativeAnalysisResult | null; explanation: ExplainResponse | null; unlock: UnlockResponse | null; plan: PlanResponse | null; transition: TransitionResponse | null; projectResponse: CreateProjectResponse | null; fixtureVersion: string; inspectorRef: React.RefObject<HTMLDetailsElement | null>; open: boolean; onOpenChange: (open: boolean) => void }) {
  const project = projectResponse?.project;
  return <details className="inspector-region" id="technical-inspector" onToggle={(event) => onOpenChange(event.currentTarget.open)} open={open} ref={inspectorRef}>
    <summary className="inspector-summary"><span className="inspector-title"><Code aria-hidden="true" size={18} weight="duotone" /><strong>Technical inspector</strong><span>Model, solver and state evidence</span></span><span className="inspector-summary-right"><span className="mono">{fixtureVersion}</span><CaretDown aria-hidden="true" className="inspector-caret" size={17} weight="bold" /></span></summary>
    <div className="inspector-content">
      <div className="inspector-group"><div className="inspector-group-heading"><Database aria-hidden="true" size={17} weight="duotone" /><span>Model</span></div>{compile ? <div className="metric-grid"><Metric label="People" value={compile.people} /><Metric label="Organisations" value={compile.organisations} /><Metric label="Spaces" value={compile.spaces} /><Metric label="Resources" value={compile.resources} /><Metric label="Decision vars" value={compile.decision_variables} /><Metric label="Hard constraints" value={compile.hard_constraints} /></div> : <span className="inspector-empty">Waiting for a compile response.</span>}</div>
      <div className="inspector-group"><div className="inspector-group-heading"><Cpu aria-hidden="true" size={17} weight="duotone" /><span>Solver</span></div>{selectedResult ? <div className="solver-readout"><StatusBadge status={selectedResult.status} /><Metric label="Objective" value={selectedResult.objective_value ?? "Not set"} /><Metric label="Branches" value={selectedResult.solver_stats.branches} /><Metric label="Conflicts" value={selectedResult.solver_stats.conflicts} /><Metric label="Runtime" value={`${selectedResult.solver_stats.wall_time_seconds.toFixed(3)}s`} /></div> : <span className="inspector-empty">Waiting for a selected result.</span>}</div>
      <div className="inspector-group"><div className="inspector-group-heading"><MagnifyingGlass aria-hidden="true" size={17} weight="duotone" /><span>Search &amp; transitions</span></div><div className="inspector-rows"><InspectorRow label="Explanation runs" value={explanation?.solver_runs} /><InspectorRow label="Unlock paths" value={unlock?.candidate_paths_evaluated} /><InspectorRow label="Transition" value={transition ? `${transition.predecessor_state_id} to ${transition.successor_state.state_id}` : undefined} mono /><InspectorRow label="Planned states" value={plan?.states.join(" to ")} mono /></div></div>
      <div className="inspector-group" data-testid="project-proof-inspector"><div className="inspector-group-heading"><CheckCircle aria-hidden="true" size={17} weight="duotone" /><span>Project source proof</span></div>{project ? <div className="inspector-rows"><InspectorRow label="Project ID" value={project.id} mono /><InspectorRow label="Project status" value={project.status} /><InspectorRow label="Source initiative" value={`${project.source_initiative_name} / ${project.source_initiative_id}`} mono /><InspectorRow label="Fresh verification" value={`${projectResponse.verification.status}${projectResponse.verification.objective_value === null ? "" : ` / objective ${projectResponse.verification.objective_value}`}`} /><InspectorRow label="Source plan" value={project.source_plan_id} mono /><InspectorRow label="Catalyst path" value={project.catalyst_path.length === 0 ? "[]" : project.catalyst_path.join(" → ")} mono /><InspectorRow label="State lineage" value={`${project.base_state_id} → ${project.verified_state_id}`} mono />{project.catalyst_outputs.map((output, index) => <InspectorRow key={`${output.action_id}-${index}`} label={`Catalyst ${index + 1}`} value={`${output.action_id}: ${output.predecessor_state_id} → ${output.successor_state_id}; ${Object.keys(output.diff.added_capabilities).length} capability, ${output.diff.added_people.length} people, ${Object.keys(output.diff.resource_quantity_changes).length} resource changes`} mono />)}</div> : <span className="inspector-empty">Create a Project to inspect its fresh verification and source plan.</span>}</div>
    </div>
  </details>;
}

function Metric({ label, value }: { label: string; value: number | string }) { return <div className="metric"><span>{label}</span><strong className="mono">{value}</strong></div>; }
function InspectorRow({ label, value, mono = false }: { label: string; value?: number | string; mono?: boolean }) { return <div className="inspector-row"><span>{label}</span><strong className={mono ? "mono" : ""}>{value ?? "Not set"}</strong></div>; }

function ActionWorkspace({ selectedInitiative, selectedResult, community, demo, requestStates, requestErrors, explanation, unlock, plan, transition, verifiedResult, journeyStep, handlers }: { selectedInitiative: InitiativeBlueprint | null; selectedResult: InitiativeAnalysisResult | null; community: CommunityState; demo: DemoFixture; requestStates: Record<RequestKey, RequestState>; requestErrors: Partial<Record<RequestKey, UiError>>; explanation: ExplainResponse | null; unlock: UnlockResponse | null; plan: PlanResponse | null; transition: TransitionResponse | null; verifiedResult: InitiativeAnalysisResult | null; journeyStep: number; handlers: { compile: () => void; assemble: () => void; explain: () => void; unlock: () => void; apply: () => void; verify: () => void } }) {
  const selectedStatus = verifiedResult?.status ?? selectedResult?.status;
  const isBlocked = selectedStatus === "INFEASIBLE";
  const canUnlock = isBlocked && Boolean(explanation) && requestStates.unlock !== "loading";
  const canExplain = isBlocked && requestStates.explain !== "loading";
  const catalystReady = Boolean(unlock?.interventions[0] ?? plan?.path[0]) && unlock?.resulting_status !== "UNKNOWN" && plan?.target_status_after !== "UNKNOWN";
  const successorExists = Boolean(transition);
  return <section className="workspace-region" aria-labelledby="workspace-title"><div className="workspace-heading"><div><p className="section-kicker">Action workspace</p><h2 id="workspace-title">Turn a brief into a verified next state</h2></div>{selectedInitiative ? <StatusBadge status={selectedStatus} /> : null}</div>{selectedInitiative ? <div className="selected-brief"><div className="selected-brief-index mono">{selectedInitiative.id.slice(0, 2)}</div><div><strong>{selectedInitiative.name}</strong><span>{selectedInitiative.roles.map((role) => role.label).join(" / ")}</span></div><span className="mono selected-brief-id">{selectedInitiative.id}</span></div> : null}<div className="action-grid" aria-label="Six action journey"><ActionButton step={1} label="COMPILE COMMUNITY" hint="Load model evidence" icon={<Lightning aria-hidden="true" size={18} weight="fill" />} onClick={handlers.compile} loading={requestStates.analyse === "loading" && journeyStep < 1} complete={journeyStep >= 1} primary={journeyStep === 0} disabled={!demo} /><ActionButton step={2} label="ASSEMBLE NOW" hint="Solve selected brief" icon={<ListChecks aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.assemble} loading={requestStates.analyse === "loading" && journeyStep >= 1} complete={journeyStep >= 2} primary={journeyStep === 1} disabled={!selectedInitiative || journeyStep < 1} /><ActionButton step={3} label="WHY BLOCKED?" hint="Inspect bounded facts" icon={<MagnifyingGlass aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.explain} loading={requestStates.explain === "loading"} complete={journeyStep >= 3} primary={journeyStep === 2 && canExplain} disabled={!canExplain} /><ActionButton step={4} label="FIND MINIMUM UNLOCK" hint="Compare interventions" icon={<LockKeyOpen aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.unlock} loading={requestStates.unlock === "loading" || requestStates.plan === "loading"} complete={journeyStep >= 4} primary={journeyStep === 3 && canUnlock} disabled={!canUnlock} /><ActionButton step={5} label="APPLY CATALYST" hint={successorExists ? "Already applied; retry is checked" : "Create successor state"} icon={<Sparkle aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.apply} loading={requestStates.transition === "loading"} complete={journeyStep >= 5} primary={journeyStep === 4 && catalystReady} disabled={!catalystReady} /><ActionButton step={6} label="VERIFY NEW STATE" hint={verifiedResult?.status === "UNKNOWN" ? "Retry bounded proof" : "Re-solve with evidence"} icon={<CheckCircle aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.verify} loading={requestStates.verify === "loading"} complete={journeyStep >= 6} primary={journeyStep === 5 && successorExists} disabled={!successorExists || Boolean(verifiedResult && verifiedResult.status !== "UNKNOWN")} /></div><div className="workspace-divider"><span>Evidence returned by the selected action</span><span className="divider-line" /></div><AnalysisPanel result={selectedResult} community={community} requestState={requestStates.analyse} error={requestErrors.analyse} onRetry={handlers.assemble} />{isBlocked ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">02</span><div><strong>Why this is blocked</strong><span>Requirement facts, not a generic warning.</span></div></div><BlockerPanel explanation={explanation} requestState={requestStates.explain} error={requestErrors.explain} onRetry={handlers.explain} /></div> : null}{unlock || requestStates.unlock === "loading" || requestStates.unlock === "error" ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">03</span><div><strong>Minimum unlock and path</strong><span>Finite intervention catalogue with a bounded successor trace.</span></div></div><UnlockPanel unlock={unlock} plan={plan} actions={demo.actions} requestState={requestStates.unlock} planState={requestStates.plan} error={requestErrors.unlock} planError={requestErrors.plan} onRetry={handlers.unlock} /></div> : null}{transition || requestStates.transition === "loading" || requestStates.transition === "error" ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">04</span><div><strong>Capability transition</strong><span>Immutable diff followed by independent verification.</span></div></div><TransitionPanel transition={transition} successorResult={verifiedResult} requestState={requestStates.transition} error={requestErrors.transition} verifyError={requestErrors.verify} onRetry={handlers.apply} /></div> : null}{requestErrors.analyse && !selectedResult ? <ErrorNotice error={requestErrors.analyse} onRetry={handlers.compile} retryLabel="Compile again" /> : null}</section>;
}

export default function Home() {
  const [demo, setDemo] = useState<DemoFixture | null>(null);
  const [community, setCommunity] = useState<CommunityState | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [selectedBlockId, setSelectedBlockId] = useState("");
  const [analyses, setAnalyses] = useState<Record<string, InitiativeAnalysisResult>>({});
  const [compile, setCompile] = useState<AnalyseResponse["compile"] | null>(null);
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [unlock, setUnlock] = useState<UnlockResponse | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [transition, setTransition] = useState<TransitionResponse | null>(null);
  const [appliedTransitions, setAppliedTransitions] = useState<TransitionResponse[]>([]);
  const [verifiedResult, setVerifiedResult] = useState<InitiativeAnalysisResult | null>(null);
  const [projectResponse, setProjectResponse] = useState<CreateProjectResponse | null>(null);
  const [projectMetadata, setProjectMetadata] = useState<ProjectMetadata>(() => defaultProjectMetadata(undefined));
  const [canvasView, setCanvasView] = useState<"graph" | "list">("graph");
  const [highContrast, setHighContrast] = useState(false);
  const [liveStatus, setLiveStatus] = useState("Community fixture is loading.");
  const [journeyStep, setJourneyStep] = useState(0);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inspectorRef = useRef<HTMLDetailsElement>(null);
  const projectRequestNonce = useRef(0);
  const projectRequestInFlight = useRef(false);
  const workflowRef = useRef<WorkflowBinding>({ generation: 0, initiativeId: "", sourceStateId: "", pathKey: "" });
  const requestControllersRef = useRef<Partial<Record<RequestKey, AbortController>>>({});
  const [requestStates, setRequestStates] = useState<Record<RequestKey, RequestState>>(initialRequestStates);
  const [requestErrors, setRequestErrors] = useState<Partial<Record<RequestKey, UiError>>>(initialRequestErrors);
  const setRequestState = useCallback((key: RequestKey, state: RequestState) => { setRequestStates((current) => ({ ...current, [key]: state })); }, []);
  const clearRequestError = useCallback((key: RequestKey) => { setRequestErrors((current) => { const next = { ...current }; delete next[key]; return next; }); }, []);
  const getUiError = useCallback((error: unknown): UiError => error instanceof ApiRequestError ? { code: error.code, message: error.message } : { code: "REQUEST_FAILED", message: "The planning service returned an unexpected response." }, []);
  const abortRequests = useCallback((keys: readonly RequestKey[]) => {
    keys.forEach((key) => {
      requestControllersRef.current[key]?.abort();
      delete requestControllersRef.current[key];
    });
  }, []);
  const invalidateProjectRequest = useCallback(() => {
    abortRequests(["project"]);
    projectRequestNonce.current += 1;
    projectRequestInFlight.current = false;
    setProjectResponse(null);
    setRequestStates((current) => ({ ...current, project: "idle" }));
    clearRequestError("project");
  }, [abortRequests, clearRequestError]);
  const beginWorkflow = useCallback((initiativeId: string, sourceStateId: string): WorkflowBinding => {
    abortRequests(REQUEST_KEYS);
    projectRequestNonce.current += 1;
    projectRequestInFlight.current = false;
    const binding = {
      generation: workflowRef.current.generation + 1,
      initiativeId,
      sourceStateId,
      pathKey: "",
    };
    workflowRef.current = binding;
    setProjectResponse(null);
    setRequestStates((current) => ({
      ...initialRequestStates,
      demo: current.demo === "success" ? "success" : current.demo,
    }));
    setRequestErrors({});
    return binding;
  }, [abortRequests]);
  const bindingMatches = useCallback((binding: WorkflowBinding): boolean => {
    const current = workflowRef.current;
    return current.generation === binding.generation
      && current.initiativeId === binding.initiativeId
      && current.sourceStateId === binding.sourceStateId
      && current.pathKey === binding.pathKey;
  }, []);
  const runRequest = useCallback(async <T,>(
    key: RequestKey,
    binding: WorkflowBinding,
    task: (signal: AbortSignal) => Promise<T>,
  ): Promise<T | null> => {
    abortRequests([key]);
    const controller = new AbortController();
    requestControllersRef.current[key] = controller;
    setRequestState(key, "loading");
    clearRequestError(key);
    try {
      const result = await task(controller.signal);
      if (controller.signal.aborted || !bindingMatches(binding)) return null;
      setRequestState(key, "success");
      return result;
    } catch (error) {
      if (controller.signal.aborted || isAbortError(error) || !bindingMatches(binding)) return null;
      setRequestState(key, "error");
      setRequestErrors((current) => ({ ...current, [key]: getUiError(error) }));
      return null;
    } finally {
      if (requestControllersRef.current[key] === controller) delete requestControllersRef.current[key];
    }
  }, [abortRequests, bindingMatches, clearRequestError, getUiError, setRequestState]);
  const loadDemo = useCallback(async () => {
    const binding = beginWorkflow("", "");
    const nextDemo = await runRequest("demo", binding, (signal) => api.getDemo(signal));
    if (!nextDemo) return;
    const initialInitiativeId = nextDemo.initiatives[0]?.id ?? "";
    workflowRef.current = {
      ...binding,
      initiativeId: initialInitiativeId,
      sourceStateId: nextDemo.community.state_id,
    };
    setDemo(nextDemo); setCommunity(nextDemo.community); setSelectedId(initialInitiativeId); setSelectedBlockId(""); setAnalyses({}); setCompile(null); setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setAppliedTransitions([]); setVerifiedResult(null); setProjectResponse(null); setProjectMetadata(defaultProjectMetadata(nextDemo.initiatives[0])); setCanvasView("graph"); setJourneyStep(0); setInspectorOpen(false); setLiveStatus("Community fixture reset. Downstream evidence and project details were cleared."); setRequestStates({ ...initialRequestStates, demo: "success" }); setRequestErrors({});
    if (window.location.hash) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  }, [beginWorkflow, runRequest]);
  useEffect(() => {
    void loadDemo();
    return () => abortRequests(REQUEST_KEYS);
  }, [abortRequests, loadDemo]);
  const compileCommunity = useCallback(async (initiativeIds?: string[]) => {
    if (!demo) return;
    const baseCommunity = demo.community;
    const activeInitiativeId = selectedId || initiativeIds?.[0] || demo.initiatives[0]?.id || "";
    const requestedIds = initiativeIds ?? demo.initiatives.map((initiative) => initiative.id);
    const binding = beginWorkflow(activeInitiativeId, baseCommunity.state_id);
    setCommunity(baseCommunity); setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setAppliedTransitions([]); setVerifiedResult(null);
    const response = await runRequest("analyse", binding, async (signal) => {
      const next = await api.analyse(baseCommunity, requestedIds, signal);
      requireResponse(sameOrderedIds(next.results.map((result) => result.initiative_id), requestedIds), "Analysis response initiative IDs did not match the request.");
      return next;
    });
    if (!response) return;
    setCompile(response.compile); setAnalyses((current) => ({ ...current, ...Object.fromEntries(response.results.map((result) => [result.initiative_id, result])) })); setJourneyStep(initiativeIds ? 2 : 1); setLiveStatus(initiativeIds ? `${humanize(initiativeIds[0])} analysis returned ${response.results[0]?.status ?? "UNKNOWN"}.` : `Community compiled. ${response.results.length} initiatives analysed.`);
  }, [beginWorkflow, demo, runRequest, selectedId]);
  const explainSelected = useCallback(async () => { if (!community || !selectedId) return; const binding = { ...workflowRef.current }; const response = await runRequest("explain", binding, async (signal) => { const next = await api.explain(community, selectedId, signal); requireResponse(next.initiative_id === selectedId, "Explanation response initiative did not match the request."); return next; }); if (response) { setExplanation(response); setJourneyStep(3); const fact = response.blocking_requirement_sets.flatMap((item) => item.facts).find((item) => item.required !== null && item.available !== null); const shortfall = fact && fact.required !== null && fact.available !== null ? ` Shortfall ${Math.max(0, fact.required - fact.available)}: ${fact.available} available, ${fact.required} required.` : ""; setLiveStatus(`Blocker explanation complete.${shortfall}`); } }, [community, runRequest, selectedId]);
  const findUnlock = useCallback(async () => {
    if (!community || !demo || !selectedId) return;
    const binding = { ...workflowRef.current };
    const response = await runRequest("unlock", binding, async (signal) => {
      const next = await api.unlock(community, selectedId, demo.actions, signal);
      requireResponse(next.target_initiative_id === selectedId, "Unlock response initiative did not match the request.");
      requireResponse(next.interventions.length >= 1 && next.interventions.length <= 2 && next.interventions.every((id) => demo.actions.some((action) => action.id === id)), "Unlock response path was not a known depth-two action path.");
      return next;
    }); if (!response) return;
    setUnlock(response); setPlan(null); const planResponse = await runRequest("plan", binding, async (signal) => {
      const next = await api.plan(community, selectedId, demo.actions, signal);
      requireResponse(next.target_initiative_id === selectedId, "Plan response initiative did not match the request.");
      requireResponse(sameOrderedIds(next.path, response.interventions), "Plan path did not match the minimum unlock path.");
      requireResponse(next.states.length === next.path.length + 1 && next.states[0] === community.state_id, "Plan state lineage did not match the requested source state.");
      return next;
    }); if (planResponse) { invalidateProjectRequest(); workflowRef.current = { ...workflowRef.current, pathKey: planResponse.path.join("\u001f") }; setPlan(planResponse); setJourneyStep(4); setLiveStatus(`Minimum unlock selected ${response.interventions.map(humanize).join(", ")} at cost ${response.total_cost}.`); }
  }, [community, demo, invalidateProjectRequest, runRequest, selectedId]);
  const applyCatalyst = useCallback(async () => {
    if (!community || !demo || !plan?.path.length) return;
    const binding = { ...workflowRef.current };
    let current = community;
    const outputs: TransitionResponse[] = [];
    for (const actionId of plan.path) {
      const requestedStateId = current.state_id;
      const response = await runRequest("transition", binding, async (signal) => {
        const next = await api.transition(current, actionId, demo.actions, signal);
        requireResponse(next.action_id === actionId, "Transition response action did not match the requested path.");
        requireResponse(next.predecessor_state_id === requestedStateId && next.successor_state.parent_state_id === requestedStateId, "Transition response lineage did not match the requested source state.");
        return next;
      });
      if (!response) return;
      outputs.push(response);
      current = response.successor_state;
    }
    const finalTransition = outputs.at(-1);
    if (!finalTransition) return;
    invalidateProjectRequest(); abortRequests(["explain", "unlock", "plan", "verify"]); workflowRef.current = { ...workflowRef.current, sourceStateId: finalTransition.successor_state.state_id }; setAppliedTransitions(outputs); setTransition(finalTransition); setVerifiedResult(null); setCommunity(finalTransition.successor_state); setJourneyStep(5); setLiveStatus(`${outputs.length} catalyst action${outputs.length === 1 ? "" : "s"} applied in order. Successor ${finalTransition.successor_state.state_id} is pending verification.`);
  }, [abortRequests, community, demo, invalidateProjectRequest, plan, runRequest]);
  const verifyNewState = useCallback(async () => {
    if (!transition || !demo) return;
    const targetId = plan?.target_initiative_id ?? unlock?.target_initiative_id ?? selectedId; if (!targetId) return;
    const binding = { ...workflowRef.current };
    const response = await runRequest("verify", binding, async (signal) => {
      const next = await api.analyse(transition.successor_state, [targetId], signal);
      requireResponse(next.results.length === 1 && next.results[0].initiative_id === targetId, "Verification response initiative did not match the requested successor proof.");
      return next;
    }); if (!response) return;
    setCompile(response.compile); const result = response.results.find((item) => item.initiative_id === targetId) ?? null;
    if (result) { setVerifiedResult(result); clearRequestError("transition"); setJourneyStep(result.status === "UNKNOWN" ? 5 : 6); setLiveStatus(`${humanize(targetId)} successor verification returned ${result.status}.${result.status === "UNKNOWN" ? " Retry remains available; no Project can be created." : ""}`); }
  }, [clearRequestError, demo, plan, runRequest, selectedId, transition, unlock]);
  const selectInitiative = useCallback((id: string) => {
    if (!demo?.initiatives.some((initiative) => initiative.id === id)) return;
    const initiative = demo.initiatives.find((item) => item.id === id);
    beginWorkflow(id, demo.community.state_id);
    setCommunity(demo.community); setSelectedId(id); setSelectedBlockId(""); setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setAppliedTransitions([]); setVerifiedResult(null); setProjectMetadata(defaultProjectMetadata(initiative)); setJourneyStep((current) => Math.min(current, 2)); setRequestStates((current) => ({ ...current, explain: "idle", unlock: "idle", plan: "idle", transition: "idle", verify: "idle", project: "idle" }));
    setRequestErrors((current) => { const next = { ...current }; REQUEST_KEYS.filter((key) => key !== "demo" && key !== "analyse").forEach((key) => delete next[key]); return next; });
  }, [beginWorkflow, demo]);
  const selectedInitiative = demo?.initiatives.find((initiative) => initiative.id === selectedId) ?? null;
  const selectedResult = selectedId ? analyses[selectedId] ?? null : null;
  const feasible = (result: InitiativeAnalysisResult | null): result is InitiativeAnalysisResult => Boolean(result && (result.status === "OPTIMAL" || result.status === "FEASIBLE"));
  const isAuthoritativeBase = Boolean(demo && community && JSON.stringify(community) === JSON.stringify(demo.community));
  const fullPathApplied = Boolean(transition && plan && appliedTransitions.length === plan.path.length && appliedTransitions.every((output, index) => output.action_id === plan.path[index]) && appliedTransitions.every((output, index) => index === 0 || output.predecessor_state_id === appliedTransitions[index - 1].successor_state.state_id));
  const successorProof = fullPathApplied && transition && plan && community?.state_id === transition.successor_state.state_id && verifiedResult?.initiative_id === selectedId && feasible(verifiedResult) ? verifiedResult : null;
  const baseProof = isAuthoritativeBase && !transition && feasible(selectedResult) ? selectedResult : null;
  const projectProof = successorProof ?? baseProof;
  const projectPath = useMemo(
    () => successorProof ? plan?.path ?? [] : [],
    [plan, successorProof],
  );
  const createProject = useCallback(async () => {
    if (!demo || !selectedId || !projectProof || projectRequestInFlight.current) return;
    projectRequestInFlight.current = true;
    const nonce = ++projectRequestNonce.current;
    const binding = { ...workflowRef.current };
    const response = await runRequest("project", binding, async (signal) => {
      const next = await api.createProject(demo.community, selectedId, projectPath, projectMetadata, signal);
      const { project } = next;
      requireResponse(project.source_initiative_id === selectedId && next.verification.initiative_id === selectedId, "Project response initiative did not match the request.");
      requireResponse(project.base_state_id === demo.community.state_id && sameOrderedIds(project.catalyst_path, projectPath), "Project response source state or catalyst path did not match the request.");
      requireResponse(project.catalyst_outputs.length === projectPath.length && project.catalyst_outputs.every((output, index) => output.action_id === projectPath[index]), "Project response catalyst outputs did not match the requested path.");
      if (project.catalyst_outputs.length === 0) {
        requireResponse(project.verified_state_id === project.base_state_id, "Empty-path Project response changed the verified state.");
      } else {
        requireResponse(project.catalyst_outputs[0].predecessor_state_id === project.base_state_id && project.catalyst_outputs.every((output, index) => index === 0 || output.predecessor_state_id === project.catalyst_outputs[index - 1].successor_state_id) && project.catalyst_outputs.at(-1)?.successor_state_id === project.verified_state_id, "Project response catalyst lineage was not continuous.");
      }
      return next;
    });
    if (response && nonce === projectRequestNonce.current) {
      setProjectResponse(response);
      setLiveStatus(`${response.project.title} created. Readiness is ${response.project.status}.`);
    }
    if (nonce === projectRequestNonce.current) projectRequestInFlight.current = false;
  }, [demo, projectMetadata, projectPath, projectProof, runRequest, selectedId]);
  const toggleInspector = useCallback(() => {
    const nextOpen = !inspectorOpen;
    setInspectorOpen(nextOpen);
    if (nextOpen) requestAnimationFrame(() => { inspectorRef.current?.scrollIntoView({ block: "start" }); inspectorRef.current?.querySelector("summary")?.focus(); });
  }, [inspectorOpen]);
  const openInspector = useCallback(() => {
    setInspectorOpen(true);
    requestAnimationFrame(() => { inspectorRef.current?.scrollIntoView({ block: "start" }); inspectorRef.current?.querySelector("summary")?.focus(); });
  }, []);
  const isDemoLoading = requestStates.demo === "loading";
  if (isDemoLoading && !demo) return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell loading-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="page-loading"><div className="loading-orbit"><CircleNotch aria-hidden="true" className="spin" size={23} weight="bold" /></div><h1>Opening the community fixture</h1><p>Loading people, places and shared resources before the first compile.</p><div className="loading-layout"><div className="loading-canvas"><InlineSkeleton lines={5} /></div><div className="loading-rail"><InlineSkeleton lines={7} /></div></div></div></main></Theme>;
  if (!demo || !community) { const error = requestErrors.demo ?? { code: "SERVICE_UNAVAILABLE", message: "The community fixture could not be loaded." }; return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell error-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="fatal-state"><div className="empty-icon empty-icon-error"><WarningCircle aria-hidden="true" size={25} weight="fill" /></div><h1>We could not open the planning table.</h1><p>Check that the planning service is running, then try the deterministic fixture again.</p><ErrorNotice error={error} onRetry={() => void loadDemo()} retryLabel="Reload fixture" /></div></main></Theme>; }
  const stateLabel = verifiedResult ? "Verified successor" : transition ? "Successor pending proof" : "Current state";
  const transitionBaseStateId = appliedTransitions[0]?.predecessor_state_id ?? transition?.predecessor_state_id;
  return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className={`app-shell ${highContrast ? "contrast-high" : ""}`}><p className="sr-only" aria-live="assertive">{liveStatus}</p><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><div className="header-context"><span>Civic capacity planner</span><span className="header-divider" /><span className="mono">{demo.fixture_version}</span></div><div className="header-actions"><div className={`state-indicator ${transition ? "state-indicator-successor" : ""}`}><GitBranch aria-hidden="true" size={16} weight="duotone" /><span>{stateLabel}</span><strong className="mono">{transition ? <><span>{transitionBaseStateId}</span><ArrowRight aria-hidden="true" size={13} weight="bold" /><span className="state-id">{transition.successor_state.state_id}</span></> : <span>{community.state_id}</span>}</strong></div><Button aria-pressed={highContrast} className="contrast-button" onClick={() => { setHighContrast((current) => !current); setLiveStatus(`High contrast mode ${highContrast ? "disabled" : "enabled"}.`); }} size="2" variant="outline"><BracketsCurly aria-hidden="true" size={17} weight="duotone" /> Contrast</Button><Button aria-controls="technical-inspector" aria-expanded={inspectorOpen} className="inspector-button" onClick={toggleInspector} size="2" variant="outline"><Code aria-hidden="true" size={17} weight="duotone" /> Inspector</Button><Button className="reset-button" onClick={() => void loadDemo()} size="2" variant="ghost"><ArrowClockwise aria-hidden="true" size={17} weight="bold" /> Reset</Button></div></header>{requestErrors.demo ? <ErrorNotice error={requestErrors.demo} onRetry={() => void loadDemo()} retryLabel="Reload fixture" /> : null}<div className="page-intro"><div><p className="eyebrow">A living planning table</p><h1>Plan with the capacity already here.</h1><p className="intro-copy">Test an initiative, inspect the blocker, prove the smallest intervention, then turn a verified plan into an executable project.</p></div><div className="intro-status"><span className="intro-status-icon"><Lightning aria-hidden="true" size={18} weight="fill" /></span><div><strong>{compile ? "Community compiled" : "Ready to compile"}</strong><span>{compile ? `${compile.people} people / ${compile.hard_constraints} constraints` : "Start with the full fixture to reveal returned solver evidence."}</span></div></div></div><div className="workspace-grid"><CommunityCanvas community={community} analyses={analyses} selectedId={selectedBlockId} onSelect={setSelectedBlockId} transition={transition} viewMode={canvasView} onViewModeChange={(view) => { setCanvasView(view); setLiveStatus(`Community ${view} view enabled.`); }} /><aside className="rail-column"><InitiativeRail initiatives={demo.initiatives} analyses={analyses} verifiedResult={verifiedResult} plan={plan} selectedId={selectedId} onSelect={selectInitiative} /><ActionWorkspace selectedInitiative={selectedInitiative} selectedResult={selectedResult} community={community} demo={demo} requestStates={requestStates} requestErrors={requestErrors} explanation={explanation} unlock={unlock} plan={plan} transition={transition} verifiedResult={verifiedResult} journeyStep={journeyStep} handlers={{ compile: () => void compileCommunity(), assemble: () => void compileCommunity([selectedId]), explain: () => void explainSelected(), unlock: () => void findUnlock(), apply: () => void applyCatalyst(), verify: () => void verifyNewState() }} /></aside></div>{selectedInitiative && projectProof ? <ProjectCreationPanel initiative={selectedInitiative} proof={projectProof} path={projectPath} metadata={projectMetadata} response={projectResponse} requestState={requestStates.project} error={requestErrors.project} onMetadataChange={(metadata) => { invalidateProjectRequest(); setProjectMetadata(metadata); }} onCreate={() => void createProject()} onOpenInspector={openInspector} /> : null}{projectResponse ? <SelectedTeamFacts response={projectResponse} /> : null}<TechnicalInspector compile={compile} selectedResult={verifiedResult ?? selectedResult} explanation={explanation} unlock={unlock} plan={plan} transition={transition} projectResponse={projectResponse} fixtureVersion={demo.fixture_version} inspectorRef={inspectorRef} open={inspectorOpen} onOpenChange={setInspectorOpen} /><footer className="page-footer"><span><Info aria-hidden="true" size={15} weight="bold" /> Results remain bounded to this deterministic fixture and the returned solver state.</span><span className="mono">{transition ? `${transitionBaseStateId} to ${transition.successor_state.state_id}` : community.state_id}</span></footer></main></Theme>;
}
