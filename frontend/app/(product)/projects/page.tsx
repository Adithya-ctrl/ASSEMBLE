"use client";

import { Toolbox } from "@phosphor-icons/react";
import Link from "next/link";

import ProjectDetailView from "../../../components/project/ProjectDetailView";
import CivicScene from "../../../components/visual/CivicScene";
import { useAssembly } from "../../../lib/workflow-context";

export default function ProjectsRoute() {
  const workflow = useAssembly();
  const proofHref = `/initiatives/${encodeURIComponent(workflow.selectedId)}/proof`;
  return <section className="module-screen projects-screen" aria-labelledby="projects-page-title"><div className="module-heading"><div><h1 id="projects-page-title">Projects</h1><p>Turn a verified initiative into a practical delivery plan.</p></div></div>{workflow.projectResponse ? <ProjectDetailView response={workflow.projectResponse} /> : <div className="route-empty route-empty-visual"><div><Toolbox aria-hidden="true" size={28} weight="duotone" /><h2>Your first delivery plan starts with proof</h2><p>Verify an initiative and the server will derive its schedule, venue, team, resources and readiness.</p><Link className="primary-link" href={proofHref}>Open proof workspace</Link></div><div className="project-empty-scene"><CivicScene alt="" kind="project" /></div></div>}</section>;
}
