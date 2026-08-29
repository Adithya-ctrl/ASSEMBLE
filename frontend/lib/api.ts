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
  CreateProjectResponse,
} from "./types";

const apiBaseUrl = "";
const API_TIMEOUT_MS = 12_000;

export type ResponseValidator<T> = (value: unknown) => T;

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

async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  const timeoutSignal = AbortSignal.timeout(API_TIMEOUT_MS);
  const signal = init?.signal ? AbortSignal.any([init.signal, timeoutSignal]) : timeoutSignal;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      signal,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiRequestError("The ASSEMBLE service did not respond in time.", 0, "SERVICE_TIMEOUT");
    }
    throw new ApiRequestError("The ASSEMBLE service could not be reached.", 0, "SERVICE_UNAVAILABLE");
  }

  return response;
}

function errorFromPayload(response: Response, payload: unknown): ApiRequestError {
  const problem = payload as ApiErrorPayload | null;
  return new ApiRequestError(
    problem?.error?.message ?? `The ASSEMBLE service returned ${response.status}.`,
    response.status,
    problem?.error?.code ?? "REQUEST_FAILED",
    problem?.error?.details ?? {},
  );
}

async function errorFromResponse(response: Response): Promise<ApiRequestError> {
  const payload: unknown = await response.json().catch(() => null);
  return errorFromPayload(response, payload);
}

export async function requestJson<T>(path: string, init?: RequestInit, validate?: ResponseValidator<T>): Promise<T> {
  const response = await fetchResponse(path, init);

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw errorFromPayload(response, payload);
  }

  if (payload === null) {
    throw new ApiRequestError("The ASSEMBLE service returned an empty response.", response.status, "EMPTY_RESPONSE");
  }

  return validate ? validate(payload) : payload as T;
}

export async function requestNoContent(path: string, init?: RequestInit): Promise<void> {
  const response = await fetchResponse(path, init);
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status !== 204) {
    throw new ApiRequestError("The ASSEMBLE service returned an unexpected response.", response.status, "UNEXPECTED_RESPONSE");
  }
}

function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, { method: "POST", body: JSON.stringify(body), signal });
}

export const api = {
  getDemo: (signal?: AbortSignal) => requestJson<DemoFixture>("/api/demo", { signal }),
  analyse: (community: CommunityState, initiativeIds: string[], signal?: AbortSignal) =>
    postJson<AnalyseResponse>("/api/analyse", { community, initiative_ids: initiativeIds }, signal),
  explain: (community: CommunityState, initiativeId: string, signal?: AbortSignal) =>
    postJson<ExplainResponse>("/api/explain", { community, initiative_id: initiativeId }, signal),
  unlock: (community: CommunityState, initiativeId: string, actions: CatalystAction[], signal?: AbortSignal) =>
    postJson<UnlockResponse>("/api/unlock", { community, initiative_id: initiativeId, actions }, signal),
  plan: (community: CommunityState, initiativeId: string, actions: CatalystAction[], signal?: AbortSignal) =>
    postJson<PlanResponse>("/api/plan", {
      community,
      initiative_id: initiativeId,
      actions,
      max_depth: 2,
      max_expanded_states: 20,
    }, signal),
  transition: (community: CommunityState, actionId: string, actions: CatalystAction[], signal?: AbortSignal) =>
    postJson<TransitionResponse>("/api/transition", { community, action_id: actionId, actions }, signal),
  createProject: (
    baseCommunity: CommunityState,
    initiativeId: string,
    catalystPath: string[],
    metadata: { title: string; short_description: string; objective: string },
    signal?: AbortSignal,
  ) => postJson<CreateProjectResponse>("/api/projects/from-plan", {
    base_community: baseCommunity,
    initiative_id: initiativeId,
    catalyst_path: catalystPath,
    ...metadata,
  }, signal),
  stressTest: (body: unknown, signal?: AbortSignal) => postJson<unknown>("/api/stress-test", body, signal),
  recompile: (body: unknown, signal?: AbortSignal) => postJson<unknown>("/api/recompile", body, signal),
  frontier: (body: unknown, signal?: AbortSignal) => postJson<unknown>("/api/frontier", body, signal),
};
