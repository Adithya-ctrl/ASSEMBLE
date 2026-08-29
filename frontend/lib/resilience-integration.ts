import type {
  CommunityState,
  DemoFixture,
  InitiativeAnalysisResult,
  TransitionResponse,
} from "./types";
import type {
  FrontierRunRequest,
  RecoveryRunRequest,
  ResilienceInitiativeChoice,
  ResilienceSourceSummary,
  StressRunRequest,
} from "./resilience-types";

const FEASIBLE = new Set(["OPTIMAL", "FEASIBLE"]);

export type ResilienceSourceContext =
  | { kind: "blocked"; reason: string; sourceKey: string }
  | {
      kind: "ready";
      sourceKey: string;
      baseCommunity: CommunityState;
      source: ResilienceSourceSummary;
      initiatives: ResilienceInitiativeChoice[];
      expectedInitiativeIds: string[];
      expectedActionIds: string[];
    };

export interface ResilienceWorkflowSnapshot {
  demo: DemoFixture;
  community: CommunityState;
  analyses: Record<string, InitiativeAnalysisResult>;
  transition: TransitionResponse | null;
  verifiedResult: InitiativeAnalysisResult | null;
  projectPath: readonly string[];
}

function isFeasible(result: InitiativeAnalysisResult | null | undefined): result is InitiativeAnalysisResult {
  return Boolean(result && FEASIBLE.has(result.status));
}

function sourceKey(stateId: string, path: readonly string[]): string {
  return `${stateId}\u001e${path.join("\u001f")}`;
}

export function deriveResilienceSource(snapshot: ResilienceWorkflowSnapshot): ResilienceSourceContext {
  const { demo, community, transition, verifiedResult, projectPath } = snapshot;
  const expectedInitiativeIds = demo.initiatives.map((initiative) => initiative.id);
  const expectedActionIds = demo.actions.map((action) => action.id);
  const actionLabels = new Map(demo.actions.map((action) => [action.id, action.name]));

  let source: ResilienceSourceSummary;
  if (transition) {
    const validPath = projectPath.length > 0 && projectPath.length <= 2 &&
      new Set(projectPath).size === projectPath.length &&
      projectPath.every((actionId) => actionLabels.has(actionId));
    const acceptedSuccessor = validPath &&
      isFeasible(verifiedResult) &&
      community.state_id === transition.successor_state.state_id;
    if (!acceptedSuccessor) {
      return {
        kind: "blocked",
        reason: "Finish verifying the updated community before running resilience analysis.",
        sourceKey: sourceKey(community.state_id, projectPath),
      };
    }
    source = {
      stateId: community.state_id,
      label: "Verified community after catalyst",
      catalystPath: projectPath.map((id) => ({ id, label: actionLabels.get(id) as string })),
    };
  } else {
    if (JSON.stringify(community) !== JSON.stringify(demo.community)) {
      return {
        kind: "blocked",
        reason: "Return to the authoritative demo community before running resilience analysis.",
        sourceKey: sourceKey(community.state_id, []),
      };
    }
    source = {
      stateId: demo.community.state_id,
      label: "Declared community",
      catalystPath: [],
    };
  }

  const feasibleIds = new Set(
    Object.values(snapshot.analyses).filter(isFeasible).map((result) => result.initiative_id),
  );
  if (isFeasible(verifiedResult)) feasibleIds.add(verifiedResult.initiative_id);
  const initiatives = demo.initiatives
    .filter((initiative) => feasibleIds.has(initiative.id))
    .map((initiative) => ({ id: initiative.id, label: initiative.name }));

  return {
    kind: "ready",
    sourceKey: sourceKey(source.stateId, source.catalystPath.map((item) => item.id)),
    baseCommunity: demo.community,
    source,
    initiatives,
    expectedInitiativeIds,
    expectedActionIds,
  };
}

export function requestMatchesSource(
  request: Pick<StressRunRequest, "sourceStateId" | "catalystPath">,
  source: ResilienceSourceSummary,
): boolean {
  const path = source.catalystPath.map((item) => item.id);
  return request.sourceStateId === source.stateId &&
    request.catalystPath.length === path.length &&
    request.catalystPath.every((item, index) => item === path[index]);
}

export function stressRequestBody(baseCommunity: CommunityState, request: StressRunRequest) {
  return {
    base_community: baseCommunity,
    initiative_id: request.initiativeId,
    catalyst_path: [...request.catalystPath],
  };
}

export function recoveryRequestBody(baseCommunity: CommunityState, request: RecoveryRunRequest) {
  return {
    base_community: baseCommunity,
    initiative_id: request.initiativeId,
    catalyst_path: [...request.catalystPath],
    perturbation_id: request.perturbationId,
  };
}

export function frontierRequestBody(baseCommunity: CommunityState, request: FrontierRunRequest) {
  return {
    base_community: baseCommunity,
    catalyst_path: [...request.catalystPath],
  };
}

export type ResilienceLane = "stress" | "recovery" | "frontier";

export interface LaneTicket {
  lane: ResilienceLane;
  generation: number;
  controller: AbortController;
}

export class ResilienceRequestLanes {
  readonly #lanes: Record<ResilienceLane, { generation: number; controller: AbortController | null }> = {
    stress: { generation: 0, controller: null },
    recovery: { generation: 0, controller: null },
    frontier: { generation: 0, controller: null },
  };

  begin(lane: ResilienceLane): LaneTicket {
    this.invalidate(lane);
    const current = this.#lanes[lane];
    const controller = new AbortController();
    current.controller = controller;
    return { lane, generation: current.generation, controller };
  }

  invalidate(lane: ResilienceLane): void {
    const current = this.#lanes[lane];
    current.controller?.abort();
    current.controller = null;
    current.generation += 1;
  }

  invalidateAll(): void {
    this.invalidate("stress");
    this.invalidate("recovery");
    this.invalidate("frontier");
  }

  isCurrent(ticket: LaneTicket): boolean {
    const current = this.#lanes[ticket.lane];
    return !ticket.controller.signal.aborted &&
      current.controller === ticket.controller &&
      current.generation === ticket.generation;
  }
}
