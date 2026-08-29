"use client";

import { Code } from "@phosphor-icons/react";
import Link from "next/link";

import ProjectProofView from "../../../../components/project/ProjectProofView";
import { useAssembly } from "../../../../lib/workflow-context";

export default function ProjectProofRoute() {
  const workflow = useAssembly();
  const proofHref = `/initiatives/${encodeURIComponent(workflow.selectedId)}/proof`;
  return <section className="module-screen" aria-labelledby="project-proof-page-title"><div className="module-heading"><div><h1 id="project-proof-page-title">Project source proof</h1><p>Inspect Project identity, fresh verification, source plan, catalyst outputs and immutable state lineage.</p></div><Link className="secondary-link" href="/projects">Back to Projects</Link></div>{workflow.projectResponse ? <ProjectProofView response={workflow.projectResponse} onOpenInspector={workflow.openInspector} /> : <div className="route-empty"><Code aria-hidden="true" size={28} weight="duotone" /><h2>No Project proof is available</h2><p>Project evidence is session-only. Create a Project from a verified initiative to inspect it here.</p><Link className="primary-link" href={proofHref}>Open proof workspace</Link></div>}</section>;
}
