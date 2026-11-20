"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icon";

const links: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Overview", icon: "overview" },
  { href: "/data", label: "Data Explorer", icon: "data" },
  { href: "/scenarios/new", label: "Scenario Builder", icon: "scenario" },
  { href: "/compare", label: "Comparison", icon: "compare" },
  { href: "/stress", label: "Stress Lab", icon: "activity" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const activeLink = links.find((link) => link.href === pathname);
  const label = activeLink?.label ?? (pathname.startsWith("/reports") ? "Evidence report" :
    pathname.startsWith("/runs") ? "Planning run" : "Planning workspace");
  return <div className="app-shell">
    <a className="skip-link" href="#content">Skip to content</a>
    <aside className="sidebar">
      <Link href="/" className="brand">
        <span className="brand-symbol"><Icon name="data" width="24" height="24" /></span>
        <span><strong>CIVITWIN<span className="brand-ai"> AI</span></strong>
          <small>Public service planning</small></span>
      </Link>
      <nav aria-label="Main navigation">
        {links.map((link) => <Link key={link.href} href={link.href}
          aria-current={pathname === link.href ? "page" : undefined}>
          <Icon name={link.icon} />{link.label}
        </Link>)}
      </nav>
      <div className="sidebar-footer"><span className="live-dot" /> Local demo workspace</div>
    </aside>
    <div className="app-body">
      <header className="topbar"><span><Icon name="pin" /> Bajaur <span className="top-divider">/</span> {label}</span>
        <Link href="/scenarios/new" className="button primary">New scenario <Icon name="arrow" /></Link>
      </header>
      <main id="content" className="content">
        <div className="demo-banner"><Icon name="database" />
          <strong>Synthetic demonstration</strong><span>Fictional data for one modeled week in Bajaur.</span>
        </div>
        {children}
      </main>
    </div>
  </div>;
}
