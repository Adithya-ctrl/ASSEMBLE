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
  DemoFixture,
  ExplainResponse,
  InitiativeAnalysisResult,
  InitiativeBlueprint,
  PlanResponse,
  SolverStatus,
  TransitionResponse,
  UnlockResponse,
} from "../lib/types";

type RequestKey = "demo" | "analyse" | "explain" | "unlock" | "plan" | "transition" | "verify";
type RequestState = "idle" | "loading" | "success" | "error";
type BlockKind = "person" | "space" | "resource";

interface UiError {
  code: string;
  message: string;
}

const REQUEST_KEYS: RequestKey[] = ["demo", "analyse", "explain", "unlock", "plan", "transition", "verify"];

const initialRequestStates: Record<RequestKey, RequestState> = {
  demo: "loading",
  analyse: "idle",
  explain: "idle",
  unlock: "idle",
  plan: "idle",
  transition: "idle",
  verify: "idle",
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

function CommunityCanvas({ community, analyses, selectedId, onSelect, transition }: { community: CommunityState; analyses: Record<string, InitiativeAnalysisResult>; selectedId: string; onSelect: (id: string) => void; transition: TransitionResponse | null }) {
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
        <span className="region-count mono">{community.state_id}</span>
      </div>
      <div className="canvas-meta">
        <span><UsersThree aria-hidden="true" size={15} weight="duotone" />{community.people.length} people</span>
        <span><Buildings aria-hidden="true" size={15} weight="duotone" />{community.spaces.length} space</span>
        <span><Toolbox aria-hidden="true" size={15} weight="duotone" />{community.resources.length} resource pools</span>
      </div>
      <div className="community-stage" aria-label="Community blocks and their relationships">
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
                      <span className="block-icon block-icon-person"><BlockIcon kind="person" /></span><span className="block-copy"><strong>{person.name}</strong><small>{person.capabilities.length > 0 ? humanize(person.capabilities[0]) : "Learner"} / {person.available_slots.length} available slots</small></span>{activePersonIds.has(person.id) ? <Check aria-label="Assigned" className="block-check" size={15} weight="bold" /> : null}
                    </button>
                  ))}
                  {spaces.map((space) => (
                    <button aria-pressed={selectedId === space.id} className={`community-block ${selectedId === space.id ? "community-block-selected" : ""}`} key={space.id} onClick={() => onSelect(space.id)} type="button">
                      <span className="block-icon block-icon-space"><BlockIcon kind="space" /></span><span className="block-copy"><strong>{space.name}</strong><small>Capacity {space.capacity} / {space.available_slots.length} available slots</small></span>
                    </button>
                  ))}
                  {resources.map((resource) => (
                    <button aria-pressed={selectedId === resource.id} className={`community-block ${selectedId === resource.id ? "community-block-selected" : ""}`} key={resource.id} onClick={() => onSelect(resource.id)} type="button">
                      <span className="block-icon block-icon-resource"><BlockIcon kind="resource" /></span><span className="block-copy"><strong>{resource.name}</strong><small>{resource.quantity} available / {resource.available_slots.length} time slots</small></span>
                    </button>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </div>
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
      <div className="region-heading rail-heading"><div><p className="section-kicker">Initiatives</p><h2 id="initiatives-title">What the community can carry</h2></div><span className="region-count">{initiatives.length} briefs</span></div>
      <div className="rail-summary" aria-live="polite"><span><span className="summary-dot dot-success" />{buildableCount} buildable</span><span><span className="summary-dot dot-blocked" />{blockedCount} blocked</span>{plan ? <span><span className="summary-dot dot-cobalt" />1 path found</span> : null}</div>
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
  return <div className="trace-table" role="table" aria-label="Assembly trace">{entries.map((entry) => <div className="trace-row" key={`${entry.requirement_kind}-${entry.requirement_id}`} role="row"><div className="trace-kind" role="cell"><span className="trace-marker" />{humanize(entry.requirement_kind)}</div><div className="trace-requirement mono" role="cell">{entry.requirement_id}</div><div className="trace-selection" role="cell">{entry.selected_ids.map((id) => <span className="selection-tag" key={id}>{names.get(id) ?? id}</span>)}</div><div className="trace-facts" role="cell">{Object.entries(entry.facts).map(([key, value]) => <span key={key}>{humanize(key)}: {String(value)}</span>)}</div></div>)}</div>;
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
  return <div className="unlock-content"><div className="unlock-result"><div className="unlock-result-icon"><LockKeyOpen aria-hidden="true" size={22} weight="duotone" /></div><div><span className="section-kicker">Minimum modelled unlock</span><strong>{selectedActions.map((action) => action.name).join(" + ") || unlock.interventions.join(", ")}</strong><span>Returns {unlock.resulting_status.toLowerCase()} at a total cost of <b className="mono">{unlock.total_cost}</b>.</span></div><StatusBadge status={unlock.resulting_status} /></div><div className="comparison-grid"><div className="comparison-column comparison-column-selected"><span className="comparison-label">Selected valid path</span>{selectedActions.map((action) => <div className="comparison-row" key={action.id}><CheckCircle aria-hidden="true" size={16} weight="fill" /><span><b>{action.name}</b><small>Minimum sufficient intervention</small></span><strong className="mono">{action.cost}</strong></div>)}<div className="comparison-total"><span>Total cost</span><strong className="mono">{unlock.total_cost}</strong></div></div><div className="comparison-column"><span className="comparison-label">Other catalogue options</span>{alternativeActions.slice(0, 3).map((action) => <div className="comparison-row comparison-row-muted" key={action.id}><span><b>{action.name}</b><small>{alternativeVerdict(action)}</small></span><strong className="mono">{action.cost}</strong></div>)}{recruitmentActions.length > 1 ? <div className="comparison-row comparison-row-muted"><span><b>Recruit both helpers</b><small>Valid: repairs 2 of 2, but costs more</small></span><strong className="mono">{recruitmentCost}</strong></div> : null}<div className="comparison-total"><span>Subsets evaluated</span><strong className="mono">{unlock.candidate_subsets_evaluated}</strong></div></div></div>{planState === "loading" ? <div className="plan-loading"><LoadingDots label="Tracing the successor state" /></div> : null}{planError ? <ErrorNotice error={planError} onRetry={onRetry} retryLabel="Trace path" /> : null}{plan ? <PlanTrace plan={plan} actions={actions} /> : null}</div>;
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
  return <div className="transition-content">{error ? <ErrorNotice error={error} onRetry={onRetry} retryLabel="Apply again" /> : null}<div className="transition-banner"><div className="transition-state"><span className="mono">{transition.predecessor_state_id}</span><ArrowRight aria-hidden="true" size={17} weight="bold" /><span className="mono transition-state-next">{transition.successor_state.state_id}</span></div><div><strong>Successor state created</strong><span>The predecessor remains unchanged. The Clinic stays blocked until the returned state is verified.</span></div></div>{hasChanges ? <div className="diff-list">{capabilityChanges.map(([personId, capabilities]) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personId}</strong> gains {capabilities.map(humanize).join(", ")}</span></div>)}{transition.diff.added_people.map((personId) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personId}</strong> joins the community state</span></div>)}{Object.entries(transition.diff.resource_quantity_changes).map(([resourceId, quantity]) => <div className="diff-row" key={resourceId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{resourceId}</strong> changes by {quantity}</span></div>)}</div> : <div className="empty-subtle">The transition returned no machine-readable changes.</div>}{verifyError ? <ErrorNotice error={verifyError} /> : null}{successorResult ? (successorResult.status === "UNKNOWN" ? <UnknownNotice copy="The successor-state verification returned UNKNOWN. The clinic is not being marked buildable." /> : <div className={`verification-result ${successorResult.status === "INFEASIBLE" ? "verification-result-blocked" : "verification-result-success"}`}><StatusIcon status={successorResult.status} size={21} /><div><strong>{successorResult.status === "INFEASIBLE" ? "The catalyst did not unlock this brief." : "Verified: the clinic is buildable in the successor state."}</strong><span>Verification used the returned {transition.successor_state.state_id} community state.</span></div></div>) : <div className="verification-prompt"><CheckCircle aria-hidden="true" size={20} weight="duotone" /><div><strong>Successor proof is ready to run.</strong><span>Continue with the single VERIFY NEW STATE action above.</span></div></div>}</div>;
}

function TechnicalInspector({ compile, selectedResult, explanation, unlock, plan, transition, fixtureVersion, inspectorRef, open, onOpenChange }: { compile: AnalyseResponse["compile"] | null; selectedResult: InitiativeAnalysisResult | null; explanation: ExplainResponse | null; unlock: UnlockResponse | null; plan: PlanResponse | null; transition: TransitionResponse | null; fixtureVersion: string; inspectorRef: React.RefObject<HTMLDetailsElement | null>; open: boolean; onOpenChange: (open: boolean) => void }) {
  return <details className="inspector-region" id="technical-inspector" onToggle={(event) => onOpenChange(event.currentTarget.open)} open={open} ref={inspectorRef}><summary className="inspector-summary"><span className="inspector-title"><Code aria-hidden="true" size={18} weight="duotone" /><strong>Technical inspector</strong><span>Model, solver and state evidence</span></span><span className="inspector-summary-right"><span className="mono">{fixtureVersion}</span><CaretDown aria-hidden="true" className="inspector-caret" size={17} weight="bold" /></span></summary><div className="inspector-content"><div className="inspector-group"><div className="inspector-group-heading"><Database aria-hidden="true" size={17} weight="duotone" /><span>Model</span></div>{compile ? <div className="metric-grid"><Metric label="People" value={compile.people} /><Metric label="Organisations" value={compile.organisations} /><Metric label="Spaces" value={compile.spaces} /><Metric label="Resources" value={compile.resources} /><Metric label="Decision vars" value={compile.decision_variables} /><Metric label="Hard constraints" value={compile.hard_constraints} /></div> : <span className="inspector-empty">Waiting for a compile response.</span>}</div><div className="inspector-group"><div className="inspector-group-heading"><Cpu aria-hidden="true" size={17} weight="duotone" /><span>Solver</span></div>{selectedResult ? <div className="solver-readout"><StatusBadge status={selectedResult.status} /><Metric label="Objective" value={selectedResult.objective_value ?? "Not set"} /><Metric label="Branches" value={selectedResult.solver_stats.branches} /><Metric label="Conflicts" value={selectedResult.solver_stats.conflicts} /><Metric label="Runtime" value={`${selectedResult.solver_stats.wall_time_seconds.toFixed(3)}s`} /></div> : <span className="inspector-empty">Waiting for a selected result.</span>}</div><div className="inspector-group"><div className="inspector-group-heading"><MagnifyingGlass aria-hidden="true" size={17} weight="duotone" /><span>Search &amp; transitions</span></div><div className="inspector-rows"><InspectorRow label="Explanation runs" value={explanation?.solver_runs} /><InspectorRow label="Unlock subsets" value={unlock?.candidate_subsets_evaluated} /><InspectorRow label="Transition" value={transition ? `${transition.predecessor_state_id} to ${transition.successor_state.state_id}` : undefined} mono /><InspectorRow label="Planned states" value={plan?.states.join(" to ")} mono /></div></div></div></details>;
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
  return <section className="workspace-region" aria-labelledby="workspace-title"><div className="workspace-heading"><div><p className="section-kicker">Action workspace</p><h2 id="workspace-title">Turn a brief into a verified next state</h2></div>{selectedInitiative ? <StatusBadge status={selectedStatus} /> : null}</div>{selectedInitiative ? <div className="selected-brief"><div className="selected-brief-index mono">{selectedInitiative.id.slice(0, 2)}</div><div><strong>{selectedInitiative.name}</strong><span>{selectedInitiative.roles.map((role) => role.label).join(" / ")}</span></div><span className="mono selected-brief-id">{selectedInitiative.id}</span></div> : null}<div className="action-grid" aria-label="Six action journey"><ActionButton step={1} label="COMPILE COMMUNITY" hint="Load model evidence" icon={<Lightning aria-hidden="true" size={18} weight="fill" />} onClick={handlers.compile} loading={requestStates.analyse === "loading" && journeyStep < 1} complete={journeyStep >= 1} primary={journeyStep === 0} disabled={!demo} /><ActionButton step={2} label="ASSEMBLE NOW" hint="Solve selected brief" icon={<ListChecks aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.assemble} loading={requestStates.analyse === "loading" && journeyStep >= 1} complete={journeyStep >= 2} primary={journeyStep === 1} disabled={!selectedInitiative || journeyStep < 1} /><ActionButton step={3} label="WHY BLOCKED?" hint="Inspect bounded facts" icon={<MagnifyingGlass aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.explain} loading={requestStates.explain === "loading"} complete={journeyStep >= 3} primary={journeyStep === 2 && canExplain} disabled={!canExplain} /><ActionButton step={4} label="FIND MINIMUM UNLOCK" hint="Compare interventions" icon={<LockKeyOpen aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.unlock} loading={requestStates.unlock === "loading" || requestStates.plan === "loading"} complete={journeyStep >= 4} primary={journeyStep === 3 && canUnlock} disabled={!canUnlock} /><ActionButton step={5} label="APPLY CATALYST" hint={successorExists ? "Already applied; retry is checked" : "Create successor state"} icon={<Sparkle aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.apply} loading={requestStates.transition === "loading"} complete={journeyStep >= 5} primary={journeyStep === 4 && catalystReady} disabled={!catalystReady} /><ActionButton step={6} label="VERIFY NEW STATE" hint="Re-solve with evidence" icon={<CheckCircle aria-hidden="true" size={18} weight="duotone" />} onClick={handlers.verify} loading={requestStates.verify === "loading"} complete={journeyStep >= 6} primary={journeyStep === 5 && successorExists} disabled={!successorExists || Boolean(verifiedResult)} /></div><div className="workspace-divider"><span>Evidence returned by the selected action</span><span className="divider-line" /></div><AnalysisPanel result={selectedResult} community={community} requestState={requestStates.analyse} error={requestErrors.analyse} onRetry={handlers.assemble} />{isBlocked ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">02</span><div><strong>Why this is blocked</strong><span>Requirement facts, not a generic warning.</span></div></div><BlockerPanel explanation={explanation} requestState={requestStates.explain} error={requestErrors.explain} onRetry={handlers.explain} /></div> : null}{unlock || requestStates.unlock === "loading" || requestStates.unlock === "error" ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">03</span><div><strong>Minimum unlock and path</strong><span>Finite intervention catalogue with a bounded successor trace.</span></div></div><UnlockPanel unlock={unlock} plan={plan} actions={demo.actions} requestState={requestStates.unlock} planState={requestStates.plan} error={requestErrors.unlock} planError={requestErrors.plan} onRetry={handlers.unlock} /></div> : null}{transition || requestStates.transition === "loading" || requestStates.transition === "error" ? <div className="evidence-section"><div className="evidence-heading"><span className="evidence-step mono">04</span><div><strong>Capability transition</strong><span>Immutable diff followed by independent verification.</span></div></div><TransitionPanel transition={transition} successorResult={verifiedResult} requestState={requestStates.transition} error={requestErrors.transition} verifyError={requestErrors.verify} onRetry={handlers.apply} /></div> : null}{requestErrors.analyse && !selectedResult ? <ErrorNotice error={requestErrors.analyse} onRetry={handlers.compile} retryLabel="Compile again" /> : null}</section>;
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
  const [verifiedResult, setVerifiedResult] = useState<InitiativeAnalysisResult | null>(null);
  const [journeyStep, setJourneyStep] = useState(0);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inspectorRef = useRef<HTMLDetailsElement>(null);
  const [requestStates, setRequestStates] = useState<Record<RequestKey, RequestState>>(initialRequestStates);
  const [requestErrors, setRequestErrors] = useState<Partial<Record<RequestKey, UiError>>>(initialRequestErrors);
  const setRequestState = useCallback((key: RequestKey, state: RequestState) => { setRequestStates((current) => ({ ...current, [key]: state })); }, []);
  const clearRequestError = useCallback((key: RequestKey) => { setRequestErrors((current) => { const next = { ...current }; delete next[key]; return next; }); }, []);
  const getUiError = useCallback((error: unknown): UiError => error instanceof ApiRequestError ? { code: error.code, message: error.message } : { code: "REQUEST_FAILED", message: "The planning service returned an unexpected response." }, []);
  const loadDemo = useCallback(async () => {
    setRequestState("demo", "loading"); clearRequestError("demo");
    try {
      const nextDemo = await api.getDemo();
      setDemo(nextDemo); setCommunity(nextDemo.community); setSelectedId(nextDemo.initiatives[0]?.id ?? ""); setSelectedBlockId(""); setAnalyses({}); setCompile(null); setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setVerifiedResult(null); setJourneyStep(0); setInspectorOpen(false); setRequestStates({ ...initialRequestStates, demo: "success" }); setRequestErrors({});
      if (window.location.hash) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    } catch (error) { setRequestState("demo", "error"); setRequestErrors((current) => ({ ...current, demo: getUiError(error) })); }
  }, [clearRequestError, getUiError, setRequestState]);
  useEffect(() => { void loadDemo(); }, [loadDemo]);
  const runRequest = useCallback(async <T,>(key: RequestKey, task: () => Promise<T>): Promise<T | null> => {
    setRequestState(key, "loading"); clearRequestError(key);
    try { const result = await task(); setRequestState(key, "success"); return result; } catch (error) { setRequestState(key, "error"); setRequestErrors((current) => ({ ...current, [key]: getUiError(error) })); return null; }
  }, [clearRequestError, getUiError, setRequestState]);
  const compileCommunity = useCallback(async (initiativeIds?: string[]) => {
    if (!demo || !community) return;
    setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setVerifiedResult(null);
    const response = await runRequest("analyse", () => api.analyse(community, initiativeIds ?? demo.initiatives.map((initiative) => initiative.id)));
    if (!response) return;
    setCompile(response.compile); setAnalyses((current) => ({ ...current, ...Object.fromEntries(response.results.map((result) => [result.initiative_id, result])) })); setJourneyStep(initiativeIds ? 2 : 1);
  }, [community, demo, runRequest]);
  const explainSelected = useCallback(async () => { if (!community || !selectedId) return; const response = await runRequest("explain", () => api.explain(community, selectedId)); if (response) { setExplanation(response); setJourneyStep(3); } }, [community, runRequest, selectedId]);
  const findUnlock = useCallback(async () => {
    if (!community || !demo || !selectedId) return;
    const response = await runRequest("unlock", () => api.unlock(community, selectedId, demo.actions)); if (!response) return;
    setUnlock(response); setPlan(null); const planResponse = await runRequest("plan", () => api.plan(community, selectedId, demo.actions)); if (planResponse) { setPlan(planResponse); setJourneyStep(4); }
  }, [community, demo, runRequest, selectedId]);
  const applyCatalyst = useCallback(async () => {
    if (!community || !demo) return;
    const actionId = unlock?.interventions[0] ?? plan?.path[0]; if (!actionId) return;
    const response = await runRequest("transition", () => api.transition(community, actionId, demo.actions)); if (response) { setTransition(response); setVerifiedResult(null); setCommunity(response.successor_state); setJourneyStep(5); }
  }, [community, demo, plan, runRequest, unlock]);
  const verifyNewState = useCallback(async () => {
    if (!transition || !demo) return;
    const targetId = plan?.target_initiative_id ?? unlock?.target_initiative_id ?? selectedId; if (!targetId) return;
    const response = await runRequest("verify", () => api.analyse(transition.successor_state, [targetId])); if (!response) return;
    setCompile(response.compile); const result = response.results.find((item) => item.initiative_id === targetId) ?? response.results[0] ?? null;
    if (result) { setVerifiedResult(result); setAnalyses((current) => ({ ...current, [result.initiative_id]: result })); clearRequestError("transition"); setJourneyStep(6); }
  }, [clearRequestError, demo, plan, runRequest, selectedId, transition, unlock]);
  const selectInitiative = useCallback((id: string) => {
    if (!demo?.initiatives.some((initiative) => initiative.id === id)) return;
    setSelectedId(id); setSelectedBlockId(""); setExplanation(null); setUnlock(null); setPlan(null); setTransition(null); setVerifiedResult(null); setJourneyStep((current) => Math.min(current, 2)); setRequestStates((current) => ({ ...current, explain: "idle", unlock: "idle", plan: "idle", transition: "idle", verify: "idle" }));
    setRequestErrors((current) => { const next = { ...current }; REQUEST_KEYS.filter((key) => key !== "demo" && key !== "analyse").forEach((key) => delete next[key]); return next; });
  }, [demo]);
  const selectedInitiative = demo?.initiatives.find((initiative) => initiative.id === selectedId) ?? null;
  const selectedResult = selectedId ? analyses[selectedId] ?? null : null;
  const toggleInspector = useCallback(() => {
    const nextOpen = !inspectorOpen;
    setInspectorOpen(nextOpen);
    if (nextOpen) requestAnimationFrame(() => { inspectorRef.current?.scrollIntoView({ block: "start" }); inspectorRef.current?.querySelector("summary")?.focus(); });
  }, [inspectorOpen]);
  const isDemoLoading = requestStates.demo === "loading";
  if (isDemoLoading && !demo) return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell loading-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="page-loading"><div className="loading-orbit"><CircleNotch aria-hidden="true" className="spin" size={23} weight="bold" /></div><h1>Opening the community fixture</h1><p>Loading people, places and shared resources before the first compile.</p><div className="loading-layout"><div className="loading-canvas"><InlineSkeleton lines={5} /></div><div className="loading-rail"><InlineSkeleton lines={7} /></div></div></div></main></Theme>;
  if (!demo || !community) { const error = requestErrors.demo ?? { code: "SERVICE_UNAVAILABLE", message: "The community fixture could not be loaded." }; return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell error-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="fatal-state"><div className="empty-icon empty-icon-error"><WarningCircle aria-hidden="true" size={25} weight="fill" /></div><h1>We could not open the planning table.</h1><p>Check that the planning service is running, then try the deterministic fixture again.</p><ErrorNotice error={error} onRetry={() => void loadDemo()} retryLabel="Reload fixture" /></div></main></Theme>; }
  const stateLabel = verifiedResult ? "Verified successor" : transition ? "Successor pending proof" : "Current state";
  return <Theme appearance="light" accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><div className="header-context"><span>Civic capacity planner</span><span className="header-divider" /><span className="mono">{demo.fixture_version}</span></div><div className="header-actions"><div className={`state-indicator ${transition ? "state-indicator-successor" : ""}`} aria-live="polite"><GitBranch aria-hidden="true" size={16} weight="duotone" /><span>{stateLabel}</span><strong className="mono">{transition ? <><span>{transition.predecessor_state_id}</span><ArrowRight aria-hidden="true" size={13} weight="bold" /><span className="state-id">{transition.successor_state.state_id}</span></> : <span>{community.state_id}</span>}</strong></div><Button aria-controls="technical-inspector" aria-expanded={inspectorOpen} className="inspector-button" onClick={toggleInspector} size="2" variant="outline"><Code aria-hidden="true" size={17} weight="duotone" /> Inspector</Button><Button className="reset-button" onClick={() => void loadDemo()} size="2" variant="ghost"><ArrowClockwise aria-hidden="true" size={17} weight="bold" /> Reset</Button></div></header>{requestErrors.demo ? <ErrorNotice error={requestErrors.demo} onRetry={() => void loadDemo()} retryLabel="Reload fixture" /> : null}<div className="page-intro"><div><p className="eyebrow">A living planning table</p><h1>Plan with the capacity already here.</h1><p className="intro-copy">Test an initiative, inspect the blocker, and prove the smallest intervention against a new community state.</p></div><div className="intro-status"><span className="intro-status-icon"><Lightning aria-hidden="true" size={18} weight="fill" /></span><div><strong>{compile ? "Community compiled" : "Ready to compile"}</strong><span>{compile ? `${compile.people} people / ${compile.hard_constraints} constraints` : "Start with the full fixture to reveal returned solver evidence."}</span></div></div></div><div className="workspace-grid"><CommunityCanvas community={community} analyses={analyses} selectedId={selectedBlockId} onSelect={setSelectedBlockId} transition={transition} /><aside className="rail-column"><InitiativeRail initiatives={demo.initiatives} analyses={analyses} verifiedResult={verifiedResult} plan={plan} selectedId={selectedId} onSelect={selectInitiative} /><ActionWorkspace selectedInitiative={selectedInitiative} selectedResult={selectedResult} community={community} demo={demo} requestStates={requestStates} requestErrors={requestErrors} explanation={explanation} unlock={unlock} plan={plan} transition={transition} verifiedResult={verifiedResult} journeyStep={journeyStep} handlers={{ compile: () => void compileCommunity(), assemble: () => void compileCommunity([selectedId]), explain: () => void explainSelected(), unlock: () => void findUnlock(), apply: () => void applyCatalyst(), verify: () => void verifyNewState() }} /></aside></div><TechnicalInspector compile={compile} selectedResult={verifiedResult ?? selectedResult} explanation={explanation} unlock={unlock} plan={plan} transition={transition} fixtureVersion={demo.fixture_version} inspectorRef={inspectorRef} open={inspectorOpen} onOpenChange={setInspectorOpen} /><footer className="page-footer"><span><Info aria-hidden="true" size={15} weight="bold" /> Results remain bounded to this deterministic fixture and the returned solver state.</span><span className="mono">{transition ? `${transition.predecessor_state_id} to ${transition.successor_state.state_id}` : community.state_id}</span></footer></main></Theme>;
}
