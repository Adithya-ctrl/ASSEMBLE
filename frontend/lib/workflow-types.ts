import type { InitiativeBlueprint } from "./types";

export type RequestKey = "demo" | "analyse" | "explain" | "unlock" | "plan" | "transition" | "verify" | "project";
export type RequestState = "idle" | "loading" | "success" | "error";
export type InventoryView = "graph" | "list";

export interface UiError {
  code: string;
  message: string;
}

export interface WorkflowBinding {
  generation: number;
  initiativeId: string;
  sourceStateId: string;
  pathKey: string;
}

export interface ProjectMetadata {
  title: string;
  short_description: string;
  objective: string;
}

export const REQUEST_KEYS: RequestKey[] = ["demo", "analyse", "explain", "unlock", "plan", "transition", "verify", "project"];

export const initialRequestStates: Record<RequestKey, RequestState> = {
  demo: "loading",
  analyse: "idle",
  explain: "idle",
  unlock: "idle",
  plan: "idle",
  transition: "idle",
  verify: "idle",
  project: "idle",
};

export function defaultProjectMetadata(initiative: InitiativeBlueprint | undefined): ProjectMetadata {
  const name = initiative?.name ?? "Community initiative";
  return {
    title: `${name} - Saturday delivery`,
    short_description: `${name} assembled from verified people, venue, time and shared resources.`,
    objective: `Deliver ${name.toLowerCase()} with every operational dependency verified before launch.`,
  };
}
