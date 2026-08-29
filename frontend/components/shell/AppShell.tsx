"use client";

import {
  Buildings,
  CaretDown,
  Check,
  Code,
  FolderOpen,
  Handshake,
  Heartbeat,
  House,
  Lightbulb,
  List,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button, DropdownMenu, Theme } from "@radix-ui/themes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

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
  const mobileMenuRef = useRef<HTMLDetailsElement>(null);
  const {
    demo, community, transition, verifiedResult, compile, selectedResult,
    explanation, unlock, plan, projectResponse, requestStates, requestErrors, liveStatus,
    inspectorOpen, judgeProofMode, preferences, inspectorRef, openInspector,
    setInspectorOpen, setJudgeProofMode,
  } = workflow;
  const highContrast = preferences.contrast === "high";
  const stateLabel = verifiedResult
    ? "Updated community verified"
    : transition
      ? "Updated community awaiting verification"
      : "Using the baseline demo community";
  const appearance = preferences.theme === "system" ? "inherit" : preferences.theme;
  const proofCapable = pathname.startsWith("/initiatives/") || pathname === "/projects/proof" || pathname === "/resilience";
  const navItems = useMemo(() => [
    { href: "/", label: "Overview", icon: House, active: pathname === "/" },
    { href: "/community", label: "Community", icon: Buildings, active: pathname === "/community" },
    { href: "/initiatives", label: "Initiatives", icon: Lightbulb, active: pathname === "/initiatives" || pathname.startsWith("/initiatives/") },
    { href: "/projects", label: "Projects", icon: FolderOpen, active: pathname === "/projects" || pathname.startsWith("/projects/") },
    { href: "/communities", label: "Collaboration", icon: Handshake, active: pathname === "/communities" || pathname.startsWith("/communities/") },
    { href: "/resilience", label: "Resilience", icon: Heartbeat, active: pathname === "/resilience" },
  ], [pathname]);
  const currentPage = navItems.find((item) => item.active)?.label ?? "Planning workspace";

  useEffect(() => {
    if (mobileMenuRef.current) mobileMenuRef.current.open = false;
  }, [pathname]);

  useEffect(() => {
    if (proofCapable) return;
    setInspectorOpen(false);
    setJudgeProofMode(false);
  }, [proofCapable, setInspectorOpen, setJudgeProofMode]);

  if (requestStates.demo === "loading" && !demo) {
    return <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell loading-shell"><header className="product-header"><div className="brand-lockup"><span aria-hidden="true" className="workbench-brand-mark"><span /><span /><span /></span><span>ASSEMBLE</span></div><span className="header-context">Civic capacity planner</span></header><div className="page-loading"><h1>Opening the community fixture</h1><p>Loading people, places and shared resources.</p><div className="loading-layout"><div className="loading-canvas"><InlineSkeleton lines={5} /></div><div className="loading-rail"><InlineSkeleton lines={7} /></div></div></div></main></Theme>;
  }
  if (!demo || !community) {
    const error = requestErrors.demo ?? { code: "SERVICE_UNAVAILABLE", message: "The community fixture could not be loaded." };
    return <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%"><main className="app-shell error-shell"><header className="product-header"><div className="brand-lockup"><span aria-hidden="true" className="workbench-brand-mark"><span /><span /><span /></span><span>ASSEMBLE</span></div></header><div className="fatal-state"><div className="empty-icon empty-icon-error"><WarningCircle aria-hidden="true" size={25} weight="fill" /></div><h1>We could not open the planning table.</h1><p>Check that the planning service is running, then try again.</p><ErrorNotice error={error} onRetry={() => void workflow.loadDemo()} retryLabel="Reload fixture" /></div></main></Theme>;
  }

  return (
    <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%">
      <main className={`app-shell modular-shell product-shell ${highContrast ? "contrast-high" : ""}`}>
        <ProductLiveRegion identityStatus={identity.liveStatus} workflowStatus={liveStatus} />
        <aside className="product-sidebar" aria-label="Product navigation">
          <Link className="sidebar-brand" href="/" aria-label="ASSEMBLE overview">
            <span aria-hidden="true" className="workbench-brand-mark"><span /><span /><span /></span>
            <span>ASSEMBLE</span>
          </Link>
          <nav className="sidebar-navigation" aria-label="Primary navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return <Link aria-current={item.active ? "page" : undefined} href={item.href} key={item.href}><Icon aria-hidden="true" size={19} weight={item.active ? "fill" : "duotone"} /><span>{item.label}</span></Link>;
            })}
          </nav>
        </aside>

        <div className="product-workspace">
          <header className="product-page-header">
            <details className="mobile-product-menu" ref={mobileMenuRef}>
              <summary aria-label="Open product navigation"><List aria-hidden="true" size={21} weight="bold" /><span>Menu</span></summary>
              <nav aria-label="Mobile product navigation">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return <Link aria-current={item.active ? "page" : undefined} href={item.href} key={item.href}><Icon aria-hidden="true" size={19} weight={item.active ? "fill" : "duotone"} /><span>{item.label}</span></Link>;
                })}
              </nav>
            </details>
            <div className="page-context">
              <strong>{currentPage}</strong>
              <span>{stateLabel}</span>
            </div>
            <div className="page-header-actions">
              {proofCapable ? (
                <DropdownMenu.Root>
                  <DropdownMenu.Trigger>
                    <Button className="proof-menu-trigger" size="2" variant="outline"><Code aria-hidden="true" size={17} /><span>View proof</span><CaretDown aria-hidden="true" size={13} weight="bold" /></Button>
                  </DropdownMenu.Trigger>
                  <DropdownMenu.Content align="end" size="2">
                    <DropdownMenu.Item onSelect={() => openInspector()}><Code aria-hidden="true" size={17} /> Technical inspector</DropdownMenu.Item>
                    <DropdownMenu.Item onSelect={() => setJudgeProofMode(!judgeProofMode)}>{judgeProofMode ? <Check aria-hidden="true" size={17} weight="bold" /> : <span aria-hidden="true" className="proof-menu-spacer" />} Judge proof mode {judgeProofMode ? "on" : "off"}</DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Root>
              ) : null}
              <AccountMenu />
            </div>
          </header>
          {requestErrors.demo ? <ErrorNotice error={requestErrors.demo} onRetry={() => void workflow.loadDemo()} retryLabel="Reload fixture" /> : null}
          <div className="product-content">{children}</div>
          {inspectorOpen ? (
            <aside className="product-proof-drawer" aria-label="Technical proof drawer">
              <TechnicalInspector compile={compile} selectedResult={verifiedResult ?? selectedResult} explanation={explanation} unlock={unlock} plan={plan} transition={transition} projectResponse={projectResponse} fixtureVersion={demo.fixture_version} inspectorRef={inspectorRef} open={inspectorOpen} onOpenChange={setInspectorOpen} />
            </aside>
          ) : null}
        </div>
      </main>
    </Theme>
  );
}
