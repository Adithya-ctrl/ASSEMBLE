"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import { useAssembly } from "../../lib/workflow-context";

export default function OverviewRoute() {
  const { demo, community, compile } = useAssembly();
  if (!demo || !community) return null;
  return <section className="module-screen overview-screen" aria-labelledby="overview-title"><div className="page-intro modular-intro"><div><p className="eyebrow">Civic capacity planning</p><h1 id="overview-title">Turn available capacity into a verified plan.</h1><p className="intro-copy">Choose an initiative, prove what is possible, and create an execution-ready Project from returned evidence.</p></div><div className="overview-next"><strong>{compile ? "Evidence is ready" : "Start with an initiative"}</strong><p>{compile ? "Continue with the selected initiative proof." : "The deterministic community fixture is loaded and ready."}</p><Link className="primary-link" href="/initiatives">View initiatives <ArrowRight aria-hidden="true" size={17} weight="bold" /></Link></div></div><div className="overview-summary" aria-label="Current planning summary"><div><strong>{community.people.length}</strong><span>people</span></div><div><strong>{community.spaces.length}</strong><span>shared place</span></div><div><strong>{community.resources.length}</strong><span>resource pools</span></div><div><strong>{demo.initiatives.length}</strong><span>initiatives</span></div></div></section>;
}
