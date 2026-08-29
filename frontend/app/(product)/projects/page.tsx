"use client";

import { Toolbox } from "@phosphor-icons/react";
import Link from "next/link";

import ProjectDetailView from "../../../components/project/ProjectDetailView";
import { useAssembly } from "../../../lib/workflow-context";

export default function ProjectsRoute() {
  const workflow = useAssembly();
  const proofHref = `/initiatives/${encodeURIComponent(workflow.selectedId)}/proof`;
  return <section className="module-screen" aria-labelledby="projects-page-title"><div className="module-heading"><div><h1 id="projects-page-title">Projects</h1><p>Review the delivery plan returned from a fresh server verification.</p></div></div>{workflow.projectResponse ? <ProjectDetailView response={workflow.projectResponse} /> : <div className="route-empty"><Toolbox aria-hidden="true" size={28} weight="duotone" /><h2>No Project in this session yet</h2><p>Verify an initiative first. The server will derive its schedule, venue, team, resources and readiness.</p><Link className="primary-link" href={proofHref}>Open proof workspace</Link></div>}</section>;
}
