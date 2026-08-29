"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";

import { api, ApiRequestError } from "./api";
import { DEFAULT_UI_PREFERENCES, readUiPreferencesCookie, writeUiPreferencesCookie, type UiPreferences } from "./preferences";
import type {
  AnalyseResponse,
  CommunityState,
  CreateProjectResponse,
  DemoFixture,
  ExplainResponse,
  InitiativeAnalysisResult,
  InitiativeBlueprint,
  PlanResponse,
  TransitionResponse,
  UnlockResponse,
} from "./types";
import { humanize, isAbortError, requireResponse, sameOrderedIds } from "./ui";
import {
  REQUEST_KEYS,
  defaultProjectMetadata,
  initialRequestStates,
  type ProjectMetadata,
  type RequestKey,
  type RequestState,
  type UiError,
  type WorkflowBinding,
} from "./workflow-types";

export interface AssemblyWorkflow {
  demo: DemoFixture | null;
  community: CommunityState | null;
  selectedId: string;
  selectedBlockId: string;
  analyses: Record<string, InitiativeAnalysisResult>;
  compile: AnalyseResponse["compile"] | null;
  explanation: ExplainResponse | null;
  unlock: UnlockResponse | null;
  plan: PlanResponse | null;
  transition: TransitionResponse | null;
  appliedTransitions: TransitionResponse[];
  verifiedResult: InitiativeAnalysisResult | null;
  projectResponse: CreateProjectResponse | null;
  projectMetadata: ProjectMetadata;
  selectedInitiative: InitiativeBlueprint | null;
  selectedResult: InitiativeAnalysisResult | null;
  projectProof: InitiativeAnalysisResult | null;
  projectPath: string[];
  requestStates: Record<RequestKey, RequestState>;
  requestErrors: Partial<Record<RequestKey, UiError>>;
  journeyStep: number;
  liveStatus: string;
  inspectorOpen: boolean;
  judgeProofMode: boolean;
  preferences: UiPreferences;
  inspectorRef: RefObject<HTMLDetailsElement | null>;
  loadDemo: () => Promise<void>;
  compileCommunity: (initiativeIds?: string[]) => Promise<void>;
  explainSelected: () => Promise<void>;
  findUnlock: () => Promise<void>;
  applyCatalyst: () => Promise<void>;
  verifyNewState: () => Promise<void>;
  createProject: () => Promise<void>;
  selectInitiative: (id: string) => void;
  setSelectedBlockId: (id: string) => void;
  setProjectMetadata: (metadata: ProjectMetadata) => void;
  updatePreferences: (patch: Partial<Omit<UiPreferences, "version">>) => void;
  setInspectorOpen: (open: boolean) => void;
  toggleInspector: () => void;
  openInspector: () => void;
  setJudgeProofMode: (enabled: boolean) => void;
  announce: (message: string) => void;
}

const AssemblyWorkflowContext = createContext<AssemblyWorkflow | null>(null);

export function AssemblyProvider({ children }: { children: ReactNode }) {
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
  const [projectMetadata, setProjectMetadataState] = useState<ProjectMetadata>(() => defaultProjectMetadata(undefined));
  const [liveStatus, setLiveStatus] = useState("Community fixture is loading.");
  const [journeyStep, setJourneyStep] = useState(0);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [judgeProofMode, setJudgeProofModeState] = useState(false);
  const [preferences, setPreferences] = useState<UiPreferences>(DEFAULT_UI_PREFERENCES);
  const preferencesReady = useRef(false);
  const inspectorRef = useRef<HTMLDetailsElement>(null);
  const projectRequestNonce = useRef(0);
  const projectRequestInFlight = useRef(false);
  const workflowRef = useRef<WorkflowBinding>({ generation: 0, initiativeId: "", sourceStateId: "", pathKey: "" });
  const requestControllersRef = useRef<Partial<Record<RequestKey, AbortController>>>({});
  const [requestStates, setRequestStates] = useState<Record<RequestKey, RequestState>>(initialRequestStates);
  const [requestErrors, setRequestErrors] = useState<Partial<Record<RequestKey, UiError>>>({});

  useEffect(() => {
    const restored = readUiPreferencesCookie(document.cookie);
    setPreferences(restored);
    document.documentElement.dataset.theme = restored.theme;
    document.documentElement.dataset.motion = restored.motion;
    preferencesReady.current = true;
  }, []);

  useEffect(() => {
    if (!preferencesReady.current) return;
    document.cookie = writeUiPreferencesCookie(preferences);
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.dataset.motion = preferences.motion;
  }, [preferences]);

  const updatePreferences = useCallback((patch: Partial<Omit<UiPreferences, "version">>) => {
    setPreferences((current) => ({ ...current, ...patch, version: 1 }));
  }, []);
  const setRequestState = useCallback((key: RequestKey, state: RequestState) => setRequestStates((current) => ({ ...current, [key]: state })), []);
  const clearRequestError = useCallback((key: RequestKey) => setRequestErrors((current) => { const next = { ...current }; delete next[key]; return next; }), []);
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
    const binding = { generation: workflowRef.current.generation + 1, initiativeId, sourceStateId, pathKey: "" };
    workflowRef.current = binding;
    setProjectResponse(null);
    setRequestStates((current) => ({ ...initialRequestStates, demo: current.demo === "success" ? "success" : current.demo }));
    setRequestErrors({});
    return binding;
  }, [abortRequests]);
  const bindingMatches = useCallback((binding: WorkflowBinding): boolean => {
    const current = workflowRef.current;
    return current.generation === binding.generation && current.initiativeId === binding.initiativeId && current.sourceStateId === binding.sourceStateId && current.pathKey === binding.pathKey;
  }, []);
  const runRequest = useCallback(async <T,>(key: RequestKey, binding: WorkflowBinding, task: (signal: AbortSignal) => Promise<T>): Promise<T | null> => {
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
    workflowRef.current = { ...binding, initiativeId: initialInitiativeId, sourceStateId: nextDemo.community.state_id };
    setDemo(nextDemo);
    setCommunity(nextDemo.community);
    setSelectedId(initialInitiativeId);
    setSelectedBlockId("");
    setAnalyses({});
    setCompile(null);
    setExplanation(null);
    setUnlock(null);
    setPlan(null);
    setTransition(null);
    setAppliedTransitions([]);
    setVerifiedResult(null);
    setProjectResponse(null);
    setProjectMetadataState(defaultProjectMetadata(nextDemo.initiatives[0]));
    setJourneyStep(0);
    setInspectorOpen(false);
    setJudgeProofModeState(false);
    setLiveStatus("Community fixture reset. Downstream evidence and Project details were cleared.");
    setRequestStates({ ...initialRequestStates, demo: "success" });
    setRequestErrors({});
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
    setCommunity(baseCommunity);
    setExplanation(null);
    setUnlock(null);
    setPlan(null);
    setTransition(null);
    setAppliedTransitions([]);
    setVerifiedResult(null);
    const response = await runRequest("analyse", binding, async (signal) => {
      const next = await api.analyse(baseCommunity, requestedIds, signal);
      requireResponse(sameOrderedIds(next.results.map((result) => result.initiative_id), requestedIds), "Analysis response initiative IDs did not match the request.");
      return next;
    });
    if (!response) return;
    setCompile(response.compile);
    setAnalyses((current) => ({ ...current, ...Object.fromEntries(response.results.map((result) => [result.initiative_id, result])) }));
    setJourneyStep(initiativeIds ? 2 : 1);
    setLiveStatus(initiativeIds ? `${humanize(initiativeIds[0])} analysis returned ${response.results[0]?.status ?? "UNKNOWN"}.` : `Community compiled. ${response.results.length} initiatives analysed.`);
  }, [beginWorkflow, demo, runRequest, selectedId]);

  const explainSelected = useCallback(async () => {
    if (!community || !selectedId) return;
    const binding = { ...workflowRef.current };
    const response = await runRequest("explain", binding, async (signal) => {
      const next = await api.explain(community, selectedId, signal);
      requireResponse(next.initiative_id === selectedId, "Explanation response initiative did not match the request.");
      return next;
    });
    if (!response) return;
    setExplanation(response);
    setJourneyStep(3);
    const fact = response.blocking_requirement_sets.flatMap((item) => item.facts).find((item) => item.required !== null && item.available !== null);
    const shortfall = fact && fact.required !== null && fact.available !== null ? ` Shortfall ${Math.max(0, fact.required - fact.available)}: ${fact.available} available, ${fact.required} required.` : "";
    setLiveStatus(`Blocker explanation complete.${shortfall}`);
  }, [community, runRequest, selectedId]);

  const findUnlock = useCallback(async () => {
    if (!community || !demo || !selectedId) return;
    const binding = { ...workflowRef.current };
    const response = await runRequest("unlock", binding, async (signal) => {
      const next = await api.unlock(community, selectedId, demo.actions, signal);
      requireResponse(next.target_initiative_id === selectedId, "Unlock response initiative did not match the request.");
      requireResponse(next.interventions.length >= 1 && next.interventions.length <= 2 && next.interventions.every((id) => demo.actions.some((action) => action.id === id)), "Unlock response path was not a known depth-two action path.");
      return next;
    });
    if (!response) return;
    setUnlock(response);
    setPlan(null);
    const planResponse = await runRequest("plan", binding, async (signal) => {
      const next = await api.plan(community, selectedId, demo.actions, signal);
      requireResponse(next.target_initiative_id === selectedId, "Plan response initiative did not match the request.");
      requireResponse(sameOrderedIds(next.path, response.interventions), "Plan path did not match the minimum unlock path.");
      requireResponse(next.states.length === next.path.length + 1 && next.states[0] === community.state_id, "Plan state lineage did not match the requested source state.");
      return next;
    });
    if (!planResponse) return;
    invalidateProjectRequest();
    workflowRef.current = { ...workflowRef.current, pathKey: planResponse.path.join("\u001f") };
    setPlan(planResponse);
    setJourneyStep(4);
    setLiveStatus(`Minimum unlock selected ${response.interventions.map(humanize).join(", ")} at cost ${response.total_cost}.`);
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
    invalidateProjectRequest();
    abortRequests(["explain", "unlock", "plan", "verify"]);
    workflowRef.current = { ...workflowRef.current, sourceStateId: finalTransition.successor_state.state_id };
    setAppliedTransitions(outputs);
    setTransition(finalTransition);
    setVerifiedResult(null);
    setCommunity(finalTransition.successor_state);
    setJourneyStep(5);
    setLiveStatus(`${outputs.length} catalyst action${outputs.length === 1 ? "" : "s"} applied in order. An updated community is pending verification.`);
  }, [abortRequests, community, demo, invalidateProjectRequest, plan, runRequest]);

  const verifyNewState = useCallback(async () => {
    if (!transition || !demo) return;
    const targetId = plan?.target_initiative_id ?? unlock?.target_initiative_id ?? selectedId;
    if (!targetId) return;
    const binding = { ...workflowRef.current };
    const response = await runRequest("verify", binding, async (signal) => {
      const next = await api.analyse(transition.successor_state, [targetId], signal);
      requireResponse(next.results.length === 1 && next.results[0].initiative_id === targetId, "Verification response initiative did not match the requested successor proof.");
      return next;
    });
    if (!response) return;
    setCompile(response.compile);
    const result = response.results.find((item) => item.initiative_id === targetId) ?? null;
    if (!result) return;
    setVerifiedResult(result);
    clearRequestError("transition");
    setJourneyStep(result.status === "UNKNOWN" ? 5 : 6);
    setLiveStatus(`${humanize(targetId)} successor verification returned ${result.status}.${result.status === "UNKNOWN" ? " Retry remains available; no Project can be created." : ""}`);
  }, [clearRequestError, demo, plan, runRequest, selectedId, transition, unlock]);

  const selectInitiative = useCallback((id: string) => {
    if (!demo?.initiatives.some((initiative) => initiative.id === id)) return;
    const initiative = demo.initiatives.find((item) => item.id === id);
    beginWorkflow(id, demo.community.state_id);
    setCommunity(demo.community);
    setSelectedId(id);
    setSelectedBlockId("");
    setExplanation(null);
    setUnlock(null);
    setPlan(null);
    setTransition(null);
    setAppliedTransitions([]);
    setVerifiedResult(null);
    setProjectMetadataState(defaultProjectMetadata(initiative));
    setJourneyStep((current) => Math.min(current, 2));
    setRequestStates((current) => ({ ...current, explain: "idle", unlock: "idle", plan: "idle", transition: "idle", verify: "idle", project: "idle" }));
    setRequestErrors((current) => { const next = { ...current }; REQUEST_KEYS.filter((key) => key !== "demo" && key !== "analyse").forEach((key) => delete next[key]); return next; });
  }, [beginWorkflow, demo]);

  const selectedInitiative = demo?.initiatives.find((initiative) => initiative.id === selectedId) ?? null;
  const selectedResult = selectedId ? analyses[selectedId] ?? null : null;
  const feasible = (result: InitiativeAnalysisResult | null): result is InitiativeAnalysisResult => Boolean(result && (result.status === "OPTIMAL" || result.status === "FEASIBLE"));
  const isAuthoritativeBase = Boolean(demo && community && JSON.stringify(community) === JSON.stringify(demo.community));
  const fullPathApplied = Boolean(transition && plan && appliedTransitions.length === plan.path.length && appliedTransitions.every((output, index) => output.action_id === plan.path[index]) && appliedTransitions.every((output, index) => index === 0 || output.predecessor_state_id === appliedTransitions[index - 1].successor_state.state_id));
  const successorProof = fullPathApplied && transition && plan && community?.state_id === transition.successor_state.state_id && verifiedResult?.initiative_id === selectedId && feasible(verifiedResult) ? verifiedResult : null;
  const baseProof = isAuthoritativeBase && !transition && journeyStep >= 2 && feasible(selectedResult) ? selectedResult : null;
  const projectProof = successorProof ?? baseProof;
  const projectPath = useMemo(() => successorProof ? plan?.path ?? [] : [], [plan, successorProof]);

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

  const setProjectMetadata = useCallback((metadata: ProjectMetadata) => {
    invalidateProjectRequest();
    setProjectMetadataState(metadata);
  }, [invalidateProjectRequest]);
  const toggleInspector = useCallback(() => {
    const nextOpen = !inspectorOpen;
    setInspectorOpen(nextOpen);
    if (nextOpen) requestAnimationFrame(() => { inspectorRef.current?.scrollIntoView({ block: "start" }); inspectorRef.current?.querySelector("summary")?.focus(); });
  }, [inspectorOpen]);
  const openInspector = useCallback(() => {
    setInspectorOpen(true);
    requestAnimationFrame(() => { inspectorRef.current?.scrollIntoView({ block: "start" }); inspectorRef.current?.querySelector("summary")?.focus(); });
  }, []);
  const setJudgeProofMode = useCallback((enabled: boolean) => {
    setJudgeProofModeState(enabled);
    if (enabled) setInspectorOpen(true);
    setLiveStatus(`Judge Proof Mode ${enabled ? "enabled" : "disabled"}.`);
  }, []);

  const value = useMemo<AssemblyWorkflow>(() => ({
    demo, community, selectedId, selectedBlockId, analyses, compile, explanation, unlock, plan, transition, appliedTransitions, verifiedResult, projectResponse, projectMetadata, selectedInitiative, selectedResult, projectProof, projectPath, requestStates, requestErrors, journeyStep, liveStatus, inspectorOpen, judgeProofMode, preferences, inspectorRef, loadDemo, compileCommunity, explainSelected, findUnlock, applyCatalyst, verifyNewState, createProject, selectInitiative, setSelectedBlockId, setProjectMetadata, updatePreferences, setInspectorOpen, toggleInspector, openInspector, setJudgeProofMode, announce: setLiveStatus,
  }), [demo, community, selectedId, selectedBlockId, analyses, compile, explanation, unlock, plan, transition, appliedTransitions, verifiedResult, projectResponse, projectMetadata, selectedInitiative, selectedResult, projectProof, projectPath, requestStates, requestErrors, journeyStep, liveStatus, inspectorOpen, judgeProofMode, preferences, loadDemo, compileCommunity, explainSelected, findUnlock, applyCatalyst, verifyNewState, createProject, selectInitiative, setProjectMetadata, updatePreferences, toggleInspector, openInspector, setJudgeProofMode]);

  return <AssemblyWorkflowContext.Provider value={value}>{children}</AssemblyWorkflowContext.Provider>;
}

export function useAssembly(): AssemblyWorkflow {
  const value = useContext(AssemblyWorkflowContext);
  if (!value) throw new Error("useAssembly must be used inside AssemblyProvider");
  return value;
}
