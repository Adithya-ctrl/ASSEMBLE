"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import { InitiativeRail } from "../../../components/AssemblyProduct";
import { useAssembly } from "../../../lib/workflow-context";

export default function InitiativesRoute() {
  const workflow = useAssembly();
  if (!workflow.demo) return null;
  const proofHref = `/initiatives/${encodeURIComponent(workflow.selectedId)}/proof`;
  return <section className="module-screen" aria-labelledby="initiatives-page-title"><div className="module-heading"><div><h1 id="initiatives-page-title">Choose an initiative</h1><p>See what is individually buildable, then open one proof workspace.</p></div><Link className="primary-link" href={proofHref}>Open selected proof <ArrowRight aria-hidden="true" size={17} /></Link></div><InitiativeRail initiatives={workflow.demo.initiatives} analyses={workflow.analyses} verifiedResult={workflow.verifiedResult} plan={workflow.plan} selectedId={workflow.selectedId} onSelect={workflow.selectInitiative} /></section>;
}
