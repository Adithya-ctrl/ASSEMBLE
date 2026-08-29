"use client";

import { Sparkle } from "@phosphor-icons/react";
import { Theme } from "@radix-ui/themes";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAssembly } from "../../lib/workflow-context";
import { useIdentity } from "../../lib/identity-context";
import AccountMenu from "./AccountMenu";

export default function IdentityShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { preferences } = useAssembly();
  const identity = useIdentity();
  const appearance = preferences.theme === "system" ? "inherit" : preferences.theme;
  const highContrast = preferences.contrast === "high";
  const links = [
    { href: "/", label: "Planning demo", active: pathname === "/" },
    { href: "/communities", label: "Collaboration spaces", active: pathname.startsWith("/communities") },
    { href: "/settings", label: "Settings", active: pathname === "/settings" },
  ];

  return (
    <Theme appearance={appearance} accentColor="blue" grayColor="slate" panelBackground="solid" radius="medium" scaling="100%">
      <main className={`identity-shell ${highContrast ? "contrast-high identity-contrast-high" : ""}`}>
        <p className="sr-only identity-sr-only" aria-atomic="true" aria-live="polite">{identity.liveStatus}</p>
        <header className="identity-header">
          <Link aria-label="ASSEMBLE planning demo" className="identity-brand-lockup" href="/">
            <span className="identity-brand-mark"><Sparkle aria-hidden="true" size={18} weight="fill" /></span>
            <span>ASSEMBLE</span>
          </Link>
          <nav aria-label="Account navigation" className="identity-navigation">
            {links.map((link) => <Link aria-current={link.active ? "page" : undefined} href={link.href} key={link.href}>{link.label}</Link>)}
          </nav>
          <div className="identity-header-account"><AccountMenu /></div>
        </header>
        <nav aria-label="Mobile account navigation" className="identity-mobile-navigation">
          {links.map((link) => <Link aria-current={link.active ? "page" : undefined} href={link.href} key={link.href}>{link.label}</Link>)}
        </nav>
        <div className="identity-content">{children}</div>
      </main>
    </Theme>
  );
}
