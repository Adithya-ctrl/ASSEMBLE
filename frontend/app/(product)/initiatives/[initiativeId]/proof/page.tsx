"use client";

import { ArrowClockwise, WarningCircle } from "@phosphor-icons/react";
import { Button } from "@radix-ui/themes";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";

import { ActionWorkspace, ProjectCreationPanel } from "../../../../../components/AssemblyProduct";
import { useAssembly } from "../../../../../lib/workflow-context";

export default function InitiativeProofRoute() {
  const params = useParams<{ initiativeId: string }>();
  const workflow = useAssembly();
  let routeId = "";
  try {
    routeId = decodeURIComponent(params.initiativeId);
  } catch {
    routeId = "";
  }
  const initiative = workflow.demo?.initiatives.find((item) => item.id === routeId) ?? null;
  const selectedId = workflow.selectedId;
  const selectInitiative = workflow.selectInitiative;
  useEffect(() => {
    if (initiative && selectedId !== routeId) selectInitiative(routeId);
  }, [initiative, routeId, selectInitiative, selectedId]);
  if (!workflow.demo || !workflow.community) return null;
  if (!initiative) return <section className="module-screen" aria-labelledby="invalid-initiative-title"><div className="route-empty"><WarningCircle aria-hidden="true" size={28} weight="duotone" /><h1 id="invalid-initiative-title">Initiative not found</h1><p>This proof URL does not match an initiative in the authoritative fixture. No analysis was run for a fallback initiative.</p><Link className="primary-link" href="/initiatives">Back to initiatives</Link></div></section>;
  if (workflow.selectedId !== routeId) return <section className="module-screen"><div className="route-empty"><h1>Opening {initiative.name}</h1><p>Preparing the selected initiative without reusing another proof.</p></div></section>;
  const handlers = { compile: () => void workflow.compileCommunity(), assemble: () => void workflow.compileCommunity([routeId]), explain: () => void workflow.explainSelected(), unlock: () => void workflow.findUnlock(), apply: () => void workflow.applyCatalyst(), verify: () => void workflow.verifyNewState() };
  return <section className="module-screen proof-screen" aria-labelledby="proof-page-title"><div className="module-heading"><div><h1 id="proof-page-title">Initiative proof</h1><p>Complete the six actions in order. Every result comes from the planning service.</p></div><div className="module-heading-actions"><Link className="secondary-link" href="/initiatives">Change initiative</Link><Button className="proof-reset-button" onClick={() => void workflow.loadDemo()} size="2" type="button" variant="ghost"><ArrowClockwise aria-hidden="true" size={17} weight="bold" />Reset proof</Button></div></div><ActionWorkspace selectedInitiative={initiative} selectedResult={workflow.selectedResult} community={workflow.community} demo={workflow.demo} requestStates={workflow.requestStates} requestErrors={workflow.requestErrors} explanation={workflow.explanation} unlock={workflow.unlock} plan={workflow.plan} transition={workflow.transition} verifiedResult={workflow.verifiedResult} journeyStep={workflow.journeyStep} handlers={handlers} showAllEvidence={workflow.judgeProofMode} />{workflow.projectProof ? <ProjectCreationPanel initiative={initiative} proof={workflow.projectProof} path={workflow.projectPath} metadata={workflow.projectMetadata} response={workflow.projectResponse} requestState={workflow.requestStates.project} error={workflow.requestErrors.project} onMetadataChange={workflow.setProjectMetadata} onCreate={() => void workflow.createProject()} /> : null}</section>;
}
