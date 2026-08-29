export type AdversarialLane = "demo" | "analyse" | "explain" | "unlock" | "plan" | "transition" | "verify" | "project" | "stress" | "recovery" | "frontier" | "identity" | "communities" | "administration";

export interface GenerationTicket<Lane extends string = AdversarialLane> {
  lane: Lane;
  generation: number;
  controller: AbortController;
}

type LaneState = { generation: number; controller: AbortController | null };

/**
 * Dependency-free request generation model for late-response tests.
 * A ticket is current only while its lane still owns the same controller and
 * generation. Invalidating one lane leaves all other lanes untouched.
 */
export class GenerationLanes<Lane extends string = AdversarialLane> {
  readonly #lanes: Map<Lane, LaneState>;

  constructor(lanes: readonly Lane[]) {
    this.#lanes = new Map(lanes.map((lane) => [lane, { generation: 0, controller: null }]));
  }

  begin(lane: Lane): GenerationTicket<Lane> {
    this.invalidate(lane);
    const state = this.#state(lane);
    const controller = new AbortController();
    state.controller = controller;
    return { lane, generation: state.generation, controller };
  }

  invalidate(lane: Lane): void {
    const state = this.#state(lane);
    state.controller?.abort();
    state.controller = null;
    state.generation += 1;
  }

  invalidateAll(): void {
    for (const lane of this.#lanes.keys()) this.invalidate(lane);
  }

  isCurrent(ticket: GenerationTicket<Lane>): boolean {
    const state = this.#state(ticket.lane);
    return state.generation === ticket.generation &&
      state.controller === ticket.controller &&
      !ticket.controller.signal.aborted;
  }

  generation(lane: Lane): number {
    return this.#state(lane).generation;
  }

  #state(lane: Lane): LaneState {
    const state = this.#lanes.get(lane);
    if (!state) throw new Error(`Unknown adversarial lane: ${String(lane)}`);
    return state;
  }
}

export interface Deferred<Value> {
  promise: Promise<Value>;
  resolve(value: Value): void;
  reject(error: unknown): void;
}

export function deferred<Value>(): Deferred<Value> {
  let resolvePromise!: (value: Value) => void;
  let rejectPromise!: (error: unknown) => void;
  const promise = new Promise<Value>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return { promise, resolve: resolvePromise, reject: rejectPromise };
}
