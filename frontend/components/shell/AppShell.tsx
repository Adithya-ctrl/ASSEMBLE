"use client";

import { ArrowClockwise, BracketsCurly, Code, GitBranch, Info, Sparkle, WarningCircle } from "@phosphor-icons/react";
import { Button, Theme } from "@radix-ui/themes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ErrorNotice, InlineSkeleton, TechnicalInspector } from "../AssemblyProduct";
import AccountMenu from "../identity/AccountMenu";
import { useIdentity } from "../../lib/identity-context";
import { useAssembly } from "../../lib/workflow-context";

function ProductLiveRegion({ identityStatus, workflowStatus }: { identityStatus: string; workflowStatus: string }) {
  const [message, setMessage] = useState(workflowStatus);
  const previousIdentity = useRef(identityStatus);
  const previousWorkflow = useRef(workflowStatus);

  useEffect(() => {
    const identityChanged = previousIdentity.current !== identityStatus;
    const workflowChanged = previousWorkflow.current !== workflowStatus;
    previousIdentity.current = identityStatus;
    previousWorkflow.current = workflowStatus;
    if (identityChanged) setMessage(identityStatus);
    else if (workflowChanged) setMessage(workflowStatus);
  }, [identityStatus, workflowStatus]);

  return <p className="sr-only" aria-live="assertive" aria-atomic="true">{message}</p>;
}

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const identity = useIdentity();
  const workflow = useAssembly();
  const {
    demo, community, transition, appliedTransitions, verifiedResult, compile, selectedResult,
    explanation, unlock, plan, projectResponse, requestStates, requestErrors, liveStatus,
    inspectorOpen, judgeProofMode, preferences, inspectorRef,
  } = workflow;
  const highContrast = preferences.contrast === "high";
  const stateLabel = verifiedResult ? "Verified updated state" : transition ? "Updated state awaiting proof" : "Baseline community";
  const transitionBaseStateId = appliedTransitions[0]?.predecessor_state_id ?? transition?.predecessor_state_id;
  const navItems = [
    { href: "/", label: "Overview", active: pathname === "/" },
    { href: "/community", label: "Demo model", active: pathname === "/community" },
    { href: "/initiatives", label: "Initiatives", active: pathname === "/initiatives" || pathname.startsWith("/initiatives/") },
    { href: "/projects", label: "Projects", active: pathname === "/projects" || pathname.startsWith("/projects/") },
    { href: "/communities", label: "Collaboration", active: pathname === "/communities" || pathname.startsWith("/communities/") },
  ];
  const appearance = preferences.theme === "system" ? "inherit" : preferences.theme;

  if (requestStates.demo === "loading" && !demo) {
    return <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell loading-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="page-loading"><h1>Opening the community fixture</h1><p>Loading people, places and shared resources.</p><div className="loading-layout"><div className="loading-canvas"><InlineSkeleton lines={5} /></div><div className="loading-rail"><InlineSkeleton lines={7} /></div></div></div></main></Theme>;
  }
  if (!demo || !community) {
    const error = requestErrors.demo ?? { code: "SERVICE_UNAVAILABLE", message: "The community fixture could not be loaded." };
    return <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell error-shell"><header className="product-header"><div className="brand-lockup"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></div></header><div className="fatal-state"><div className="empty-icon empty-icon-error"><WarningCircle aria-hidden="true" size={25} weight="fill" /></div><h1>We could not open the planning table.</h1><p>Check that the planning service is running, then try again.</p><ErrorNotice error={error} onRetry={() => void workflow.loadDemo()} retryLabel="Reload fixture" /></div></main></Theme>;
  }

  return (
    <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%">
      <main className={`app-shell modular-shell ${highContrast ? "contrast-high" : ""}`}>
        <ProductLiveRegion identityStatus={identity.liveStatus} workflowStatus={liveStatus} />
        <header className="product-header modular-header">
          <Link className="brand-lockup" href="/" aria-label="ASSEMBLE overview"><span className="brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span><span>ASSEMBLE</span></Link>
          <nav className="primary-navigation" aria-label="Primary navigation">{navItems.map((item) => <Link aria-current={item.active ? "page" : undefined} href={item.href} key={item.href}>{item.label}</Link>)}</nav>
          <div className="header-actions modular-header-actions">
            <Button aria-pressed={judgeProofMode} className="judge-mode-button" onClick={() => workflow.setJudgeProofMode(!judgeProofMode)} size="2" variant="outline"><Code aria-hidden="true" size={17} weight="duotone" /><span>Judge mode</span></Button>
            <AccountMenu />
          </div>
        </header>
        <nav className="mobile-navigation" aria-label="Mobile navigation">{navItems.map((item) => <Link aria-current={item.active ? "page" : undefined} href={item.href} key={item.href}>{item.label}</Link>)}</nav>
        <div className="utility-bar"><span className={`utility-state ${transition ? "utility-state-successor" : ""}`}><GitBranch aria-hidden="true" size={16} weight="duotone" /><span>{stateLabel}</span>{judgeProofMode ? <strong className="mono">{transition ? `${transitionBaseStateId} to ${transition.successor_state.state_id}` : community.state_id}</strong> : null}</span><div><Button aria-pressed={highContrast} className="contrast-button" onClick={() => { workflow.updatePreferences({ contrast: highContrast ? "standard" : "high" }); workflow.announce(`High contrast mode ${highContrast ? "disabled" : "enabled"}.`); }} size="2" variant="ghost"><BracketsCurly aria-hidden="true" size={17} weight="duotone" /> High contrast</Button><Button aria-controls="technical-inspector" aria-expanded={inspectorOpen || judgeProofMode} className="inspector-button" onClick={workflow.toggleInspector} size="2" variant="ghost"><Code aria-hidden="true" size={17} weight="duotone" /> Technical inspector</Button><Button className="reset-button" onClick={() => void workflow.loadDemo()} size="2" variant="ghost"><ArrowClockwise aria-hidden="true" size={17} weight="bold" /> Reset</Button></div></div>
        {requestErrors.demo ? <ErrorNotice error={requestErrors.demo} onRetry={() => void workflow.loadDemo()} retryLabel="Reload fixture" /> : null}
        {children}
        <TechnicalInspector compile={compile} selectedResult={verifiedResult ?? selectedResult} explanation={explanation} unlock={unlock} plan={plan} transition={transition} projectResponse={projectResponse} fixtureVersion={demo.fixture_version} inspectorRef={inspectorRef} open={inspectorOpen} onOpenChange={workflow.setInspectorOpen} />
        <footer className="page-footer"><span><Info aria-hidden="true" size={15} weight="bold" /> Planning results remain bounded to this deterministic demo model. Collaboration spaces do not change its data.</span>{judgeProofMode ? <span className="mono">{transition ? `${transitionBaseStateId} to ${transition.successor_state.state_id}` : community.state_id}</span> : <span>Technical IDs stay in the Inspector.</span>}</footer>
      </main>
    </Theme>
  );
}
