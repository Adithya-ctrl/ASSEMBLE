"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import CommunityInventory from "../../../components/community/CommunityInventory";
import { useAssembly } from "../../../lib/workflow-context";

export default function CommunityRoute() {
  const workflow = useAssembly();
  if (!workflow.community) return null;
  return <section className="module-screen community-screen" aria-labelledby="community-page-title"><div className="module-heading"><div><h1 id="community-page-title">Community capacity</h1><p>Find the people, places or shared resources that can support a local initiative.</p></div><Link className="primary-link" href="/initiatives">Continue to initiatives <ArrowRight aria-hidden="true" size={16} /></Link></div><CommunityInventory community={workflow.community} selectedId={workflow.selectedBlockId} viewMode={workflow.preferences.inventoryView} judgeMode={workflow.judgeProofMode} onSelect={workflow.setSelectedBlockId} onViewModeChange={(view) => workflow.updatePreferences({ inventoryView: view })} onAnnounce={workflow.announce} /></section>;
}
