"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import { useAssembly } from "../../lib/workflow-context";

export default function OverviewRoute() {
  const { demo, community, compile } = useAssembly();
  if (!demo || !community) return null;
  return <section className="module-screen overview-screen" aria-labelledby="overview-title"><div className="overview-welcome"><h1 id="overview-title">Turn community capacity into a plan people can trust.</h1><p>Choose a local initiative, prove what is possible, and create a Project from returned evidence.</p><Link className="primary-link" href="/initiatives">{compile ? "Continue planning" : "View initiatives"} <ArrowRight aria-hidden="true" size={17} weight="bold" /></Link><small>{compile ? "Planning evidence is ready to continue." : "The demo community is ready to explore."}</small></div><dl className="overview-summary" aria-label="Current planning model"><div><dt>People</dt><dd>{community.people.length}</dd></div><div><dt>Shared places</dt><dd>{community.spaces.length}</dd></div><div><dt>Resource pools</dt><dd>{community.resources.length}</dd></div><div><dt>Initiatives</dt><dd>{demo.initiatives.length}</dd></div></dl></section>;
}
