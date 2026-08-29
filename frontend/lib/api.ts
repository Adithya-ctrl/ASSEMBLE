import type {
  AnalyseResponse,
  CatalystAction,
  CommunityState,
  DemoFixture,
  ExplainResponse,
  PlanResponse,
  UnlockResponse,
  TransitionResponse,
  ApiErrorPayload,
} from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_ASSEMBLE_API_URL ?? "";

export class ApiRequestError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(message: string, status: number, code = "REQUEST_FAILED", details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.details = details;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError("The planning service could not be reached.", 0, "SERVICE_UNAVAILABLE");
  }

  const payload = (await response.json().catch(() => null)) as T | ApiErrorPayload | null;

  if (!response.ok) {
    const errorPayload = payload as ApiErrorPayload | null;
    throw new ApiRequestError(
      errorPayload?.error?.message ?? `The planning service returned ${response.status}.`,
      response.status,
      errorPayload?.error?.code ?? "REQUEST_FAILED",
      errorPayload?.error?.details ?? {},
    );
  }

  if (payload === null) {
    throw new ApiRequestError("The planning service returned an empty response.", response.status, "EMPTY_RESPONSE");
  }

  return payload as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export const api = {
  getDemo: () => request<DemoFixture>("/api/demo"),
  analyse: (community: CommunityState, initiativeIds: string[]) =>
    postJson<AnalyseResponse>("/api/analyse", { community, initiative_ids: initiativeIds }),
  explain: (community: CommunityState, initiativeId: string) =>
    postJson<ExplainResponse>("/api/explain", { community, initiative_id: initiativeId }),
  unlock: (community: CommunityState, initiativeId: string, actions: CatalystAction[]) =>
    postJson<UnlockResponse>("/api/unlock", { community, initiative_id: initiativeId, actions }),
  plan: (community: CommunityState, initiativeId: string, actions: CatalystAction[]) =>
    postJson<PlanResponse>("/api/plan", {
      community,
      initiative_id: initiativeId,
      actions,
      max_depth: 2,
      max_expanded_states: 20,
    }),
  transition: (community: CommunityState, actionId: string, actions: CatalystAction[]) =>
    postJson<TransitionResponse>("/api/transition", { community, action_id: actionId, actions }),
};
