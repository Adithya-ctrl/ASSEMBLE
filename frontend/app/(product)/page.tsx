"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import CivicScene from "../../components/visual/CivicScene";
import { CIVIC_WORLD_SCENE } from "../../components/visual/sceneAssets";
import { useAssembly } from "../../lib/workflow-context";

export default function OverviewRoute() {
  const { demo, community, compile } = useAssembly();
  if (!demo || !community) return null;
  return (
    <section className="module-screen overview-screen" aria-labelledby="overview-title">
      <div className="overview-hero">
        <div className="overview-welcome">
          <h1 id="overview-title">Build what your community is ready for.</h1>
          <p>Bring people, places and shared resources together around one initiative, then prove the plan before delivery.</p>
          <div className="overview-actions">
            <Link className="primary-link" href="/initiatives">{compile ? "Continue planning" : "Explore initiatives"} <ArrowRight aria-hidden="true" size={17} weight="bold" /></Link>
            <Link className="secondary-link" href="/community">See community capacity</Link>
          </div>
          <small>{compile ? "Your planning evidence is ready to continue." : "The fictional demo community is ready to explore."}</small>
        </div>
        <CivicScene alt="Neighbours assembling a community plan around a shared table" assetSrc={CIVIC_WORLD_SCENE} kind="overview" priority />
      </div>
      <dl className="overview-summary" aria-label="Current planning model">
        <div><dt>People ready to contribute</dt><dd>{community.people.length}</dd></div>
        <div><dt>Shared places</dt><dd>{community.spaces.length}</dd></div>
        <div><dt>Resource pools</dt><dd>{community.resources.length}</dd></div>
        <div><dt>Initiatives to explore</dt><dd>{demo.initiatives.length}</dd></div>
      </dl>
    </section>
  );
}
