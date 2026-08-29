"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiRequestError, api } from "../../lib/api";
import {
  deriveResilienceSource,
  frontierRequestBody,
  recoveryRequestBody,
  requestMatchesSource,
  ResilienceRequestLanes,
  stressRequestBody,
  type ResilienceSourceContext,
} from "../../lib/resilience-integration";
import {
  parseFrontierResponse,
  parseRecompileResponse,
  parseStressResponse,
  perturbationBindingsMatch,
  ResilienceContractError,
} from "../../lib/resilience-contract";
import type {
  FrontierRunRequest,
  RecoveryRunRequest,
  ResilienceTaskError,
  ResilienceTaskState,
  StressRunRequest,
} from "../../lib/resilience-types";
import { humanize, isAbortError } from "../../lib/ui";
import { useAssembly } from "../../lib/workflow-context";
import ResilienceLab from "./ResilienceLab";
import styles from "./ResilienceIntegration.module.css";

const idleTask = <Request,>(): ResilienceTaskState<Request> => ({ request: null, result: null, error: null, loading: false });

function taskError(error: unknown): ResilienceTaskError {
  if (error instanceof ApiRequestError) return { code: error.code, message: error.message };
  if (error instanceof ResilienceContractError) {
    return { code: "CLIENT_CONTRACT_ERROR", message: "Returned resilience evidence did not match the bound request." };
  }
  return { code: "REQUEST_FAILED", message: "The resilience analysis returned an unexpected response." };
}

function failTask<Request>(
  error: unknown,
  setTask: (value: ResilienceTaskState<Request>) => void,
  request: Request,
  announce: (message: string) => void,
): void {
  if (isAbortError(error)) return;
  const nextError = taskError(error);
  setTask({ request, result: null, error: nextError, loading: false });
  announce(`${nextError.code}. ${nextError.message}`);
}

function ResilienceSession({
  context,
  announce,
  judgeMode,
}: {
  context: Extract<ResilienceSourceContext, { kind: "ready" }>;
  announce: (message: string) => void;
  judgeMode: boolean;
}) {
  const [stress, setStress] = useState<ResilienceTaskState<StressRunRequest>>(() => idleTask());
  const [recovery, setRecovery] = useState<ResilienceTaskState<RecoveryRunRequest>>(() => idleTask());
  const [frontier, setFrontier] = useState<ResilienceTaskState<FrontierRunRequest>>(() => idleTask());
  const lanes = useRef(new ResilienceRequestLanes());

  useEffect(() => () => lanes.current.invalidateAll(), []);

  const onRunStress = useCallback((callbackRequest: StressRunRequest) => {
    const request: StressRunRequest = { ...callbackRequest, catalystPath: [...callbackRequest.catalystPath] };
    if (!requestMatchesSource(request, context.source) || !context.initiatives.some((item) => item.id === request.initiativeId)) {
      const error = { code: "SOURCE_CHANGED", message: "The selected initiative or source changed before the stress test began." };
      setStress({ request, result: null, error, loading: false });
      announce(error.message);
      return;
    }
    lanes.current.invalidate("recovery");
    setRecovery(idleTask());
    const ticket = lanes.current.begin("stress");
    setStress({ request, result: null, error: null, loading: true });
    void api.stressTest(stressRequestBody(context.baseCommunity, request), ticket.controller.signal)
      .then((payload) => {
        if (!lanes.current.isCurrent(ticket)) return;
        const result = parseStressResponse(payload, request);
        setStress({ request, result: payload, error: null, loading: false });
        announce(`${humanize(result.initiative_id)} stress test complete. ${result.failed_count} critical and ${result.unknown_count} unknown across ${result.catalogue_size} disruptions.`);
      })
      .catch((error: unknown) => {
        if (!lanes.current.isCurrent(ticket) || isAbortError(error)) return;
        failTask(error, setStress, request, announce);
      });
  }, [announce, context]);

  const onRunRecovery = useCallback((callbackRequest: RecoveryRunRequest) => {
    const request: RecoveryRunRequest = { ...callbackRequest, catalystPath: [...callbackRequest.catalystPath], perturbationBinding: structuredClone(callbackRequest.perturbationBinding) };
    if (!requestMatchesSource(request, context.source) || !stress.request || !stress.result) {
      const error = { code: "STRESS_RESULT_REQUIRED", message: "Run a current stress test and select one returned disruption first." };
      setRecovery({ request, result: null, error, loading: false });
      announce(error.message);
      return;
    }
    try {
      const currentStress = parseStressResponse(stress.result, stress.request);
      const selected = currentStress.outcomes.find((item) => item.perturbation_id === request.perturbationId);
      if (!selected || !perturbationBindingsMatch(selected.perturbation, request.perturbationBinding)) {
        throw new ResilienceContractError("The selected perturbation is not bound to the current stress result.");
      }
    } catch (error) {
      const nextError = taskError(error);
      setRecovery({ request, result: null, error: nextError, loading: false });
      announce(nextError.message);
      return;
    }
    const ticket = lanes.current.begin("recovery");
    setRecovery({ request, result: null, error: null, loading: true });
    void api.recompile(recoveryRequestBody(context.baseCommunity, request), ticket.controller.signal)
      .then((payload) => {
        if (!lanes.current.isCurrent(ticket)) return;
        const result = parseRecompileResponse(payload, request);
        setRecovery({ request, result: payload, error: null, loading: false });
        announce(`Recovery analysis returned ${result.status}. ${result.minimum_assignment_changes === null ? "No minimum change was claimed." : `Minimum ${result.minimum_assignment_changes} changed assignment${result.minimum_assignment_changes === 1 ? "" : "s"}.`}`);
      })
      .catch((error: unknown) => {
        if (!lanes.current.isCurrent(ticket) || isAbortError(error)) return;
        failTask(error, setRecovery, request, announce);
      });
  }, [announce, context, stress]);

  const onRunFrontier = useCallback((callbackRequest: FrontierRunRequest) => {
    const request: FrontierRunRequest = {
      ...callbackRequest,
      catalystPath: [...callbackRequest.catalystPath],
      expectedInitiativeIds: [...callbackRequest.expectedInitiativeIds],
      expectedActionIds: [...callbackRequest.expectedActionIds],
    };
    const cataloguesMatch = request.expectedInitiativeIds.length === context.expectedInitiativeIds.length &&
      request.expectedInitiativeIds.every((item, index) => item === context.expectedInitiativeIds[index]) &&
      request.expectedActionIds.length === context.expectedActionIds.length &&
      request.expectedActionIds.every((item, index) => item === context.expectedActionIds[index]);
    if (!requestMatchesSource(request, context.source) || !cataloguesMatch) {
      const error = { code: "SOURCE_CHANGED", message: "The source or authoritative catalogue changed before frontier analysis began." };
      setFrontier({ request, result: null, error, loading: false });
      announce(error.message);
      return;
    }
    const ticket = lanes.current.begin("frontier");
    setFrontier({ request, result: null, error: null, loading: true });
    void api.frontier(frontierRequestBody(context.baseCommunity, request), ticket.controller.signal)
      .then((payload) => {
        if (!lanes.current.isCurrent(ticket)) return;
        const result = parseFrontierResponse(payload, request);
        setFrontier({ request, result: payload, error: null, loading: false });
        const winner = result.highest_leverage_action_id
          ? humanize(result.highest_leverage_action_id)
          : "none";
        announce(`Capability frontier complete. Highest leverage: ${winner}.`);
      })
      .catch((error: unknown) => {
        if (!lanes.current.isCurrent(ticket) || isAbortError(error)) return;
        failTask(error, setFrontier, request, announce);
      });
  }, [announce, context]);

  return (
    <>
      {context.initiatives.length === 0 ? (
        <div className={styles.proofNeeded} role="note">
          <strong>Prove a buildable initiative first</strong>
          <span>Stress testing needs an existing feasible proof. Frontier analysis remains available without changing the planning workflow.</span>
          <Link href="/initiatives">Open Initiatives</Link>
        </div>
      ) : null}
      <ResilienceLab
        source={context.source}
        initiatives={context.initiatives}
        frontierExpectations={{ initiativeIds: context.expectedInitiativeIds, actionIds: context.expectedActionIds }}
        stress={stress}
        recovery={recovery}
        frontier={frontier}
        judgeMode={judgeMode}
        onRunStress={onRunStress}
        onRunRecovery={onRunRecovery}
        onRunFrontier={onRunFrontier}
      />
    </>
  );
}

export default function ResilienceIntegration() {
  const workflow = useAssembly();
  const context = useMemo(() => workflow.demo && workflow.community ? deriveResilienceSource({
    demo: workflow.demo,
    community: workflow.community,
    analyses: workflow.analyses,
    transition: workflow.transition,
    verifiedResult: workflow.verifiedResult,
    projectPath: workflow.projectPath,
  }) : null, [workflow.analyses, workflow.community, workflow.demo, workflow.projectPath, workflow.transition, workflow.verifiedResult]);

  if (!context) return null;
  if (context.kind === "blocked") {
    return (
      <section className={styles.unavailable} aria-labelledby="resilience-unavailable-title">
        <h1 id="resilience-unavailable-title">Verification is required</h1>
        <span>{context.reason}</span>
        <Link href={workflow.selectedId ? `/initiatives/${encodeURIComponent(workflow.selectedId)}/proof` : "/initiatives"}>Return to Initiative Proof</Link>
      </section>
    );
  }
  return (
    <ResilienceSession
      key={context.sourceKey}
      context={context}
      announce={workflow.announce}
      judgeMode={workflow.judgeProofMode}
    />
  );
}
