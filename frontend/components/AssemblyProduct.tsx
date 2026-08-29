"use client";

import {
  ArrowRight,
  BracketsCurly,
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
  Lightning,
  ListChecks,
  LockKeyOpen,
  MagnifyingGlass,
  Plus,
  Sparkle,
  WarningCircle,
  XCircle,
} from "@phosphor-icons/react";
import { Badge, Button } from "@radix-ui/themes";
import Link from "next/link";
import { useMemo } from "react";

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
import type { ProjectMetadata, RequestKey, RequestState, UiError } from "../lib/workflow-types";
import { humanize } from "../lib/ui";

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

function LoadingDots({ label }: { label: string }) {
  return (
    <span className="loading-label">
      <CircleNotch aria-hidden="true" className="spin" size={15} weight="bold" />
      {label}
    </span>
  );
}

export function ErrorNotice({ error, onRetry, retryLabel = "Try again" }: { error: UiError; onRetry?: () => void; retryLabel?: string }) {
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

export function InlineSkeleton({ lines = 2 }: { lines?: number }) {
  return (
    <div className="inline-skeleton" aria-label="Loading">
      {Array.from({ length: lines }, (_, index) => <span className={index === lines - 1 ? "skeleton-line skeleton-line-short" : "skeleton-line"} key={index} />)}
    </div>
  );
}

export function InitiativeRail({ initiatives, analyses, verifiedResult, plan, selectedId, onSelect }: { initiatives: InitiativeBlueprint[]; analyses: Record<string, InitiativeAnalysisResult>; verifiedResult: InitiativeAnalysisResult | null; plan: PlanResponse | null; selectedId: string; onSelect: (id: string) => void }) {
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
              <div className="initiative-card-footer"><span>{isPathTarget && shownStatus === "INFEASIBLE" ? "Successor path ready" : "Open proof workspace"}</span><CaretRight aria-hidden="true" size={17} weight="bold" /></div>
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

function AnalysisPanel({ result, community, requestState, error, onRetry, showTechnical = false }: { result: InitiativeAnalysisResult | null; community: CommunityState; requestState: RequestState; error?: UiError; onRetry: () => void; showTechnical?: boolean }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Compiling the selected brief…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Recompile" />;
  if (!result) return <div className="empty-panel"><div className="empty-icon"><BracketsCurly aria-hidden="true" size={23} weight="duotone" /></div><div><strong>Compile a brief to see the assembly trace.</strong><span>The solver response will populate assignments, facts and technical evidence here.</span></div></div>;
  if (result.status === "UNKNOWN") return <UnknownNotice />;
  if (result.status === "INFEASIBLE") return <div className="result-callout result-callout-blocked"><div className="result-callout-icon"><XCircle aria-hidden="true" size={22} weight="fill" /></div><div><strong>This brief is blocked in the current state.</strong><span>Use WHY BLOCKED? to inspect the exact requirement set that prevents assembly.</span></div></div>;
  const peopleById = new Map(community.people.map((person) => [person.id, person.name]));
  return <div className="analysis-success"><div className="result-callout result-callout-success"><div className="result-callout-icon"><CheckCircle aria-hidden="true" size={22} weight="fill" /></div><div><strong>Assembly found for this brief.</strong><span>The planning service returned a complete team, place, time and resource witness.</span></div>{showTechnical ? <div className="result-objective"><span>Objective</span><strong className="mono">{result.objective_value ?? "Not set"}</strong></div> : null}</div><ul className="human-proof-list" aria-label="Selected operational team">{result.assignments.map((assignment) => <li key={assignment.role_instance_id}><CheckCircle aria-hidden="true" size={16} weight="fill" /><span><strong>{peopleById.get(assignment.person_id) ?? "Selected community member"}</strong><small>{humanize(assignment.role_instance_id)}</small></span></li>)}</ul>{showTechnical ? (result.assembly_trace.length > 0 ? <TraceTable entries={result.assembly_trace} community={community} /> : <div className="empty-subtle">The solver returned no assembly trace entries for this result.</div>) : <div className="technical-disclosure-note"><Code aria-hidden="true" size={16} />Judge Proof Mode or the Technical Inspector shows exact trace fields.</div>}</div>;
}

function BlockingFactRow({ fact, showTechnical = false }: { fact: ExplainResponse["blocking_requirement_sets"][number]["facts"][number]; showTechnical?: boolean }) {
  const hasCounts = fact.required !== null && fact.available !== null;
  const shortfall = hasCounts ? Math.max((fact.required ?? 0) - (fact.available ?? 0), 0) : null;
  return <div className="fact-row"><span className="fact-label">{fact.capability ? humanize(fact.capability) : fact.language ? `Language: ${fact.language}` : humanize(fact.requirement_id ?? "Requirement")}</span>{hasCounts ? <span className="fact-value"><span><small>Required</small><strong>{fact.required}</strong></span><span><small>Available</small><strong>{fact.available}</strong></span><span className="fact-shortfall"><small>Shortfall</small><strong>{shortfall}</strong></span></span> : null}{fact.note ? <span className="fact-note">{fact.note}</span> : null}{showTechnical && fact.relevant_ids.length > 0 ? <span className="fact-ids mono">Source: {fact.relevant_ids.join(", ")}</span> : null}</div>;
}

function BlockerPanel({ explanation, requestState, error, onRetry, showTechnical = false }: { explanation: ExplainResponse | null; requestState: RequestState; error?: UiError; onRetry: () => void; showTechnical?: boolean }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Checking blocking requirements…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Recheck" />;
  if (!explanation) return <div className="empty-subtle">Select a blocked initiative, then run WHY BLOCKED? for bounded evidence.</div>;
  if (explanation.status === "UNKNOWN") return <UnknownNotice copy="The explanation solver returned UNKNOWN. The current blocker is not being inferred." />;
  if (explanation.blocking_requirement_sets.length === 0) return <div className="empty-subtle">The backend returned no blocking requirement set for this result.</div>;
  return <div className="blocker-list">{explanation.blocking_requirement_sets.map((set, index) => <div className="blocker-item" key={`${set.groups.join("-")}-${index}`}><div className="blocker-item-heading"><span className="blocker-number">{index + 1}</span><div><strong>{set.groups.map(humanize).join(" + ")}</strong><span>{set.restored_feasibility_when_relaxed ? "Feasibility returns when this requirement is addressed." : "This change alone did not restore feasibility."}</span></div></div><div className="fact-list">{set.facts.map((fact, factIndex) => <BlockingFactRow fact={fact} key={`${fact.capability ?? fact.language ?? fact.requirement_id ?? "fact"}-${factIndex}`} showTechnical={showTechnical} />)}</div></div>)}{showTechnical ? <div className="method-line"><MagnifyingGlass aria-hidden="true" size={15} weight="bold" />{explanation.method.replaceAll("_", " ")} / {explanation.solver_runs} bounded solver runs</div> : null}</div>;
}

function UnlockPanel({ unlock, plan, actions, requestState, planState, error, planError, onRetry, showTechnical = false }: { unlock: UnlockResponse | null; plan: PlanResponse | null; actions: CatalystAction[]; requestState: RequestState; planState: RequestState; error?: UiError; planError?: UiError; onRetry: () => void; showTechnical?: boolean }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Comparing modelled interventions…" /><InlineSkeleton lines={3} /></div>;
  if (error) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Search again" />;
  if (!unlock) return <div className="empty-subtle">Run FIND MINIMUM UNLOCK to compare the finite intervention catalogue.</div>;
  if (unlock.resulting_status === "UNKNOWN") return <UnknownNotice copy="The intervention search returned UNKNOWN. No unlock is being presented as sufficient." />;
  const selectedActions = unlock.interventions.map((id) => actions.find((action) => action.id === id)).filter((action): action is CatalystAction => Boolean(action));
  const alternativeActions = actions.filter((action) => !unlock.interventions.includes(action.id)).sort((left, right) => left.cost - right.cost);
  const recruitmentActions = actions.filter((action) => action.id.startsWith("RECRUIT_HELPER"));
  const recruitmentCost = recruitmentActions.reduce((total, action) => total + action.cost, 0);
  const alternativeVerdict = (action: CatalystAction) => action.id === "BORROW_TWO_LAPTOPS" ? "Invalid: does not repair the capability shortfall" : action.id.startsWith("RECRUIT_HELPER") ? "Insufficient alone: repairs 1 of 2" : "Not sufficient alone";
  return <div className="unlock-content"><div className="unlock-result"><div className="unlock-result-icon"><LockKeyOpen aria-hidden="true" size={22} weight="duotone" /></div><div><span className="section-kicker">Minimum modelled unlock</span><strong>{selectedActions.map((action) => action.name).join(" + ") || "Returned intervention"}</strong><span>Returns {unlock.resulting_status.toLowerCase()} at a total cost of <b>{unlock.total_cost}</b>.</span></div><StatusBadge status={unlock.resulting_status} /></div><div className="comparison-grid"><div className="comparison-column comparison-column-selected"><span className="comparison-label">Selected valid path</span>{selectedActions.map((action) => <div className="comparison-row" key={action.id}><CheckCircle aria-hidden="true" size={16} weight="fill" /><span><b>{action.name}</b><small>Minimum sufficient intervention</small></span><strong>{action.cost}</strong></div>)}<div className="comparison-total"><span>Total cost</span><strong>{unlock.total_cost}</strong></div></div><div className="comparison-column"><span className="comparison-label">Other catalogue options</span>{alternativeActions.slice(0, 3).map((action) => <div className="comparison-row comparison-row-muted" key={action.id}><span><b>{action.name}</b><small>{alternativeVerdict(action)}</small></span><strong>{action.cost}</strong></div>)}{recruitmentActions.length > 1 ? <div className="comparison-row comparison-row-muted"><span><b>Recruit both helpers</b><small>Valid: repairs 2 of 2, but costs more</small></span><strong>{recruitmentCost}</strong></div> : null}{showTechnical ? <div className="comparison-total"><span>Ordered paths evaluated</span><strong className="mono">{unlock.candidate_paths_evaluated}</strong></div> : null}</div></div>{planState === "loading" ? <div className="plan-loading"><LoadingDots label="Tracing the successor state" /></div> : null}{planError ? <ErrorNotice error={planError} onRetry={onRetry} retryLabel="Trace path" /> : null}{plan ? <PlanTrace plan={plan} actions={actions} showTechnical={showTechnical} /> : null}</div>;
}

function PlanTrace({ plan, actions, showTechnical = false }: { plan: PlanResponse; actions: CatalystAction[]; showTechnical?: boolean }) {
  const actionNames = new Map(actions.map((action) => [action.id, action.name]));
  return <div className="plan-trace"><div className="plan-heading"><GitBranch aria-hidden="true" size={17} weight="duotone" /><strong>Returned action path</strong>{showTechnical ? <span className="mono">{plan.nodes.length} nodes</span> : null}</div><div className="path-steps">{plan.path.map((actionId, index) => <div className="path-step" key={`${actionId}-${index}`}><span className={`path-node ${index === plan.path.length - 1 ? "path-node-final" : ""}`}><span>{index === 0 ? "Current community" : `Updated community ${index}`}</span></span><span className="path-arrow"><ArrowRight aria-hidden="true" size={16} weight="bold" /><small>{actionNames.get(actionId) ?? "Returned action"}</small></span>{index === plan.path.length - 1 ? <span className="path-node path-node-final"><span>Buildable successor</span><Check aria-label="Target state" size={14} weight="bold" /></span> : null}</div>)}</div><div className="plan-foot"><span>Before <StatusBadge status={plan.target_status_before} /></span><ArrowRight aria-hidden="true" size={15} /><span>After <StatusBadge status={plan.target_status_after} /></span><span>cost {plan.total_cost}</span></div>{showTechnical ? <div className="technical-disclosure-note mono">{plan.states.join(" to ")}</div> : null}</div>;
}

function TransitionPanel({ transition, successorResult, requestState, error, verifyError, onRetry, showTechnical = false }: { transition: TransitionResponse | null; successorResult: InitiativeAnalysisResult | null; requestState: RequestState; error?: UiError; verifyError?: UiError; onRetry: () => void; showTechnical?: boolean }) {
  if (requestState === "loading") return <div className="workspace-panel"><LoadingDots label="Applying catalyst to a new immutable state…" /><InlineSkeleton lines={2} /></div>;
  if (error && !transition) return <ErrorNotice error={error} onRetry={onRetry} retryLabel="Apply again" />;
  if (!transition) return <div className="empty-subtle">Apply the returned catalyst path to create a successor state.</div>;
  const capabilityChanges = Object.entries(transition.diff.added_capabilities);
  const hasChanges = capabilityChanges.length > 0 || transition.diff.added_people.length > 0 || Object.keys(transition.diff.resource_quantity_changes).length > 0;
  const personNames = new Map(transition.successor_state.people.map((person) => [person.id, person.name]));
  const resourceNames = new Map(transition.successor_state.resources.map((resource) => [resource.id, resource.name]));
  return <div className="transition-content">{error ? <ErrorNotice error={error} onRetry={onRetry} retryLabel="Apply again" /> : null}<div className="transition-banner">{showTechnical ? <div className="transition-state"><span className="mono">{transition.predecessor_state_id}</span><ArrowRight aria-hidden="true" size={17} weight="bold" /><span className="mono transition-state-next">{transition.successor_state.state_id}</span></div> : <GitBranch aria-hidden="true" size={24} weight="duotone" />}<div><strong>Updated community created</strong><span>The baseline remains unchanged. This initiative stays blocked until the updated community is verified.</span></div></div>{hasChanges ? <div className="diff-list">{capabilityChanges.map(([personId, capabilities]) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personNames.get(personId) ?? (showTechnical ? personId : "Community member")}</strong> gains {capabilities.map(humanize).join(", ")}</span></div>)}{transition.diff.added_people.map((personId) => <div className="diff-row" key={personId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{personNames.get(personId) ?? (showTechnical ? personId : "New community member")}</strong> joins the updated community</span></div>)}{Object.entries(transition.diff.resource_quantity_changes).map(([resourceId, quantity]) => <div className="diff-row" key={resourceId}><Plus aria-hidden="true" size={16} weight="bold" /><span><strong>{resourceNames.get(resourceId) ?? (showTechnical ? resourceId : "Shared resource")}</strong> changes by {quantity}</span></div>)}</div> : <div className="empty-subtle">The transition returned no visible capacity changes.</div>}{verifyError ? <ErrorNotice error={verifyError} /> : null}{successorResult ? (successorResult.status === "UNKNOWN" ? <UnknownNotice copy="The updated-community verification returned UNKNOWN. This initiative is not being marked buildable; VERIFY remains available to retry." /> : <div className={`verification-result ${successorResult.status === "INFEASIBLE" ? "verification-result-blocked" : "verification-result-success"}`}><StatusIcon status={successorResult.status} size={21} /><div><strong>{successorResult.status === "INFEASIBLE" ? "The returned change did not unlock this initiative." : "Verified: this initiative is buildable in the updated community."}</strong><span>{showTechnical ? `Verification used ${transition.successor_state.state_id}.` : "Verification used the exact returned updated community."}</span></div></div>) : <div className="verification-prompt"><CheckCircle aria-hidden="true" size={20} weight="duotone" /><div><strong>Updated-community proof is ready to run.</strong><span>Continue with the single VERIFY NEW STATE action above.</span></div></div>}</div>;
}

export function ProjectCreationPanel({ initiative, proof, path, metadata, response, requestState, error, onMetadataChange, onCreate, onOpenInspector }: { initiative: InitiativeBlueprint; proof: InitiativeAnalysisResult; path: string[]; metadata: ProjectMetadata; response: CreateProjectResponse | null; requestState: RequestState; error?: UiError; onMetadataChange: (metadata: ProjectMetadata) => void; onCreate: () => void; onOpenInspector: () => void }) {
  const project = response?.project;
  const loading = requestState === "loading";
  return <section className="project-region" aria-labelledby="project-creation-title"><div className="project-region-heading"><div><p className="section-kicker">Executable Project</p><h2 id="project-creation-title">Create a Project from this verified plan</h2><p>The server replays the plan and derives the schedule, assignments, venue, resources and readiness.</p></div><span className="proof-chip"><CheckCircle aria-hidden="true" size={17} weight="fill" />{proof.status} proof</span></div>{project ? null : <form aria-busy={loading} className="project-form" onSubmit={(event) => { event.preventDefault(); if (!loading) onCreate(); }}><div className="project-proof-line"><span><strong>Verified plan</strong><span>{path.length === 0 ? "Ready from the baseline community" : `${path.length} planned community change${path.length === 1 ? "" : "s"}`}</span></span><span><strong>Initiative</strong><span>{initiative.name}</span></span></div><label><span>Project title</span><input disabled={loading} maxLength={100} minLength={3} onChange={(event) => onMetadataChange({ ...metadata, title: event.target.value })} required value={metadata.title} /></label><label><span>Short description</span><textarea disabled={loading} maxLength={280} minLength={20} onChange={(event) => onMetadataChange({ ...metadata, short_description: event.target.value })} required rows={3} value={metadata.short_description} /></label><label><span>Objective</span><textarea disabled={loading} maxLength={280} minLength={20} onChange={(event) => onMetadataChange({ ...metadata, objective: event.target.value })} required rows={3} value={metadata.objective} /></label>{error && !loading ? <ErrorNotice error={error} onRetry={onCreate} retryLabel="Create again" /> : null}<Button className="create-project-button" disabled={loading} size="3" type="submit">{loading ? <LoadingDots label="Replaying and verifying plan…" /> : <><Sparkle aria-hidden="true" size={18} weight="fill" />CREATE PROJECT</>}</Button></form>}{project ? <div className="project-created-next"><CheckCircle aria-hidden="true" size={24} weight="fill" /><div><strong>{project.title} was created</strong><span>Server status: {project.status}. Open Projects for the complete operational plan.</span></div><span className="source-plan-control"><Link className="primary-link" href="/projects">Open Project</Link><Button onClick={onOpenInspector} size="2" type="button" variant="outline"><Code aria-hidden="true" size={16} />Inspect proof</Button></span></div> : null}</section>;
}

export function TechnicalInspector({ compile, selectedResult, explanation, unlock, plan, transition, projectResponse, fixtureVersion, inspectorRef, open, onOpenChange }: { compile: AnalyseResponse["compile"] | null; selectedResult: InitiativeAnalysisResult | null; explanation: ExplainResponse | null; unlock: UnlockResponse | null; plan: PlanResponse | null; transition: TransitionResponse | null; projectResponse: CreateProjectResponse | null; fixtureVersion: string; inspectorRef: React.RefObject<HTMLDetailsElement | null>; open: boolean; onOpenChange: (open: boolean) => void }) {
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

export function ActionWorkspace({ selectedInitiative, selectedResult, community, demo, requestStates, requestErrors, explanation, unlock, plan, transition, verifiedResult, journeyStep, handlers, showAllEvidence = false }: { selectedInitiative: InitiativeBlueprint | null; selectedResult: InitiativeAnalysisResult | null; community: CommunityState; demo: DemoFixture; requestStates: Record<RequestKey, RequestState>; requestErrors: Partial<Record<RequestKey, UiError>>; explanation: ExplainResponse | null; unlock: UnlockResponse | null; plan: PlanResponse | null; transition: TransitionResponse | null; verifiedResult: InitiativeAnalysisResult | null; journeyStep: number; handlers: { compile: () => void; assemble: () => void; explain: () => void; unlock: () => void; apply: () => void; verify: () => void }; showAllEvidence?: boolean }) {
  const selectedStatus = journeyStep >= 2 ? (verifiedResult?.status ?? selectedResult?.status) : undefined;
  const isBlocked = selectedStatus === "INFEASIBLE";
  const proofComplete = selectedStatus === "OPTIMAL" || selectedStatus === "FEASIBLE";
  const canUnlock = isBlocked && Boolean(explanation) && requestStates.unlock !== "loading";
  const canExplain = isBlocked && requestStates.explain !== "loading";
  const catalystReady = Boolean(unlock?.interventions[0] ?? plan?.path[0]) && unlock?.resulting_status !== "UNKNOWN" && plan?.target_status_after !== "UNKNOWN";
  const successorExists = Boolean(transition);
  const steps = [
    { step: 1, label: "COMPILE COMMUNITY", hint: "Load model evidence", icon: <Lightning aria-hidden="true" size={18} weight="fill" />, onClick: handlers.compile, loading: requestStates.analyse === "loading" && journeyStep < 1, disabled: !demo },
    { step: 2, label: "ASSEMBLE NOW", hint: "Solve selected brief", icon: <ListChecks aria-hidden="true" size={18} weight="duotone" />, onClick: handlers.assemble, loading: requestStates.analyse === "loading" && journeyStep >= 1, disabled: !selectedInitiative || journeyStep < 1 },
    { step: 3, label: "WHY BLOCKED?", hint: "Inspect bounded facts", icon: <MagnifyingGlass aria-hidden="true" size={18} weight="duotone" />, onClick: handlers.explain, loading: requestStates.explain === "loading", disabled: !canExplain },
    { step: 4, label: "FIND MINIMUM UNLOCK", hint: "Compare interventions", icon: <LockKeyOpen aria-hidden="true" size={18} weight="duotone" />, onClick: handlers.unlock, loading: requestStates.unlock === "loading" || requestStates.plan === "loading", disabled: !canUnlock },
    { step: 5, label: "APPLY CATALYST", hint: successorExists ? "Already applied; retry is checked" : "Create successor state", icon: <Sparkle aria-hidden="true" size={18} weight="duotone" />, onClick: handlers.apply, loading: requestStates.transition === "loading", disabled: !catalystReady },
    { step: 6, label: "VERIFY NEW STATE", hint: verifiedResult?.status === "UNKNOWN" ? "Retry bounded proof" : "Re-solve with evidence", icon: <CheckCircle aria-hidden="true" size={18} weight="duotone" />, onClick: handlers.verify, loading: requestStates.verify === "loading", disabled: !successorExists || Boolean(verifiedResult && verifiedResult.status !== "UNKNOWN") },
  ];
  const completedSteps = steps.slice(0, Math.min(journeyStep, 6));
  const currentStep = proofComplete && !transition && journeyStep >= 2 ? null : steps[Math.min(journeyStep, 5)];

  return <section className="workspace-region" aria-labelledby="workspace-title"><div className="workspace-heading"><div><p className="section-kicker">Action workspace</p><h2 id="workspace-title">Turn a brief into a verified next state</h2></div>{selectedInitiative ? <StatusBadge status={selectedStatus} /> : null}</div>{selectedInitiative ? <div className="selected-brief"><div className="selected-brief-index">{selectedInitiative.name.slice(0, 1)}</div><div><strong>{selectedInitiative.name}</strong><span>{selectedInitiative.roles.length} operational roles / {selectedInitiative.duration_slots} time blocks</span></div>{showAllEvidence ? <span className="mono selected-brief-id">{selectedInitiative.id}</span> : null}</div> : null}{completedSteps.length ? <ol className="journey-timeline" aria-label="Completed proof actions">{completedSteps.map((step) => <li key={step.step}><CheckCircle aria-hidden="true" size={18} weight="fill" /><span><strong>{step.label}</strong><small>Completed with returned evidence</small></span></li>)}</ol> : null}{currentStep ? <div className="current-action"><span>Current action</span><ActionButton step={currentStep.step} label={currentStep.label} hint={currentStep.hint} icon={currentStep.icon} onClick={currentStep.onClick} loading={currentStep.loading} primary disabled={currentStep.disabled} /></div> : <div className="proof-complete"><CheckCircle aria-hidden="true" size={22} weight="fill" /><div><strong>Proof complete</strong><span>{transition ? "The updated state is verified." : "This initiative is buildable from the baseline community."}</span></div></div>}<div className="workspace-divider"><span>{showAllEvidence ? "All returned evidence" : "Evidence for the current stage"}</span><span className="divider-line" /></div>{(showAllEvidence || journeyStep <= 2) ? <AnalysisPanel result={journeyStep >= 2 ? selectedResult : null} community={community} requestState={requestStates.analyse} error={requestErrors.analyse} onRetry={handlers.assemble} showTechnical={showAllEvidence} /> : null}{isBlocked && (showAllEvidence || journeyStep === 3) ? <div className="evidence-section"><div className="evidence-heading"><div><strong>Why this is blocked</strong><span>Requirement facts, not a generic warning.</span></div></div><BlockerPanel explanation={explanation} requestState={requestStates.explain} error={requestErrors.explain} onRetry={handlers.explain} showTechnical={showAllEvidence} /></div> : null}{(unlock || requestStates.unlock === "loading" || requestStates.unlock === "error") && (showAllEvidence || journeyStep === 4) ? <div className="evidence-section"><div className="evidence-heading"><div><strong>Minimum unlock and path</strong><span>Finite intervention catalogue with a bounded successor trace.</span></div></div><UnlockPanel unlock={unlock} plan={plan} actions={demo.actions} requestState={requestStates.unlock} planState={requestStates.plan} error={requestErrors.unlock} planError={requestErrors.plan} onRetry={handlers.unlock} showTechnical={showAllEvidence} /></div> : null}{(transition || requestStates.transition === "loading" || requestStates.transition === "error") && (showAllEvidence || journeyStep >= 5) ? <div className="evidence-section"><div className="evidence-heading"><div><strong>Capacity update</strong><span>Immutable changes followed by independent verification.</span></div></div><TransitionPanel transition={transition} successorResult={verifiedResult} requestState={requestStates.transition} error={requestErrors.transition} verifyError={requestErrors.verify} onRetry={handlers.apply} showTechnical={showAllEvidence} /></div> : null}{requestErrors.analyse && !selectedResult ? <ErrorNotice error={requestErrors.analyse} onRetry={handlers.compile} retryLabel="Compile again" /> : null}</section>;
}
