"use client";

import {
  Bell,
  ChartNoAxesCombined,
  ChevronDown,
  CircleHelp,
  CreditCard,
  Gauge,
  Goal,
  LayoutDashboard,
  Menu,
  ShoppingBag,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  WalletCards,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth, type AuthUser } from "@/components/auth/auth-provider";
import { dateFromKey, useCurrentDateKey } from "@/utils/use-current-date";

const navigation = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/transactions", label: "Transactions", icon: CreditCard },
  { href: "/budget", label: "Budget", icon: WalletCards },
  { href: "/goals", label: "Goals", icon: Goal },
  { href: "/affordability", label: "Can I afford this?", icon: ShoppingBag },
  { href: "/what-if", label: "What-if planner", icon: SlidersHorizontal },
  { href: "/investments", label: "Investment planner", icon: ChartNoAxesCombined },
  { href: "/simulator", label: "Simulator", icon: Gauge },
  { href: "/ai-coach", label: "AI Coach", icon: CircleHelp },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings2 },
];

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/transactions": "Transactions",
  "/budget": "Budget",
  "/goals": "Goals",
  "/affordability": "Can I afford this?",
  "/what-if": "What-if planner",
  "/investments": "Investment planner",
  "/simulator": "Simulator",
  "/ai-coach": "AI Coach",
  "/alerts": "Alerts",
  "/settings": "Settings",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { user, logout } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const currentDateKey = useCurrentDateKey();
  const monthLabel = currentDateKey ? new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(dateFromKey(currentDateKey)) : "";

  if (["/login", "/register", "/onboarding"].includes(pathname)) return <>{children}</>;

  const navigationLinks = (
    <nav className="sidebar-nav" aria-label="Main navigation">
      <p className="nav-label">Workspace</p>
      {navigation.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link className={`nav-link${active ? " nav-link-active" : ""}`} href={href} key={href} aria-current={active ? "page" : undefined} onClick={() => setDrawerOpen(false)}>
            <Icon size={18} strokeWidth={active ? 2.2 : 1.8} aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="app-frame">
      <aside className="sidebar-desktop">
        <Brand />
        {navigationLinks}
        <UserBadge user={user} />
      </aside>

      {drawerOpen && <button className="drawer-scrim" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />}
      <aside className={`sidebar-mobile${drawerOpen ? " sidebar-mobile-open" : ""}`} aria-label="Mobile navigation">
        <div className="mobile-brand-row"><Brand /><button className="icon-button" onClick={() => setDrawerOpen(false)} aria-label="Close menu"><X size={19} /></button></div>
        {navigationLinks}
        <UserBadge user={user} />
      </aside>

      <main className="main-column">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu-button" onClick={() => setDrawerOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <div><p className="topbar-kicker">FinPilot workspace</p><h1>{pageTitles[pathname] ?? "FinPilot"}</h1></div>
          </div>
          <div className="topbar-actions">
            <button className="button button-light button-small" onClick={() => logout().catch((error: Error) => setLogoutError(error.message))}>Sign Out</button>
            {monthLabel && <span className="month-chip">{monthLabel}</span>}
            <Link className="icon-button notification-button" href="/alerts" aria-label="Open alerts"><Bell size={18} /></Link>
            <Link className="top-user" href="/settings" aria-label="Open profile settings">
              <span className="avatar avatar-small">{user?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("") ?? "--"}</span>
              <span className="top-user-name">{user?.name ?? "Loading profile"}</span><ChevronDown size={15} />
            </Link>
          </div>
        </header>
        <div className="page-content">{user?.is_demo && <div className="demo-banner">DEMO ACCOUNT - Read-only. Sign out to create your own account.</div>}{logoutError && <p role="alert">{logoutError}</p>}{children}</div>
        <footer className="app-footer">FinPilot provides educational financial information and planning tools. Investment returns are not guaranteed. Consider professional advice for major financial decisions.</footer>
      </main>
    </div>
  );
}

function Brand() {
  return <Link className="brand" href="/" aria-label="FinPilot dashboard"><span className="brand-mark"><ShieldCheck size={19} /></span><span>FinPilot<span className="brand-ai">AI</span></span></Link>;
}

function UserBadge({ user }: { user: AuthUser | null }) {
  const initials = user?.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("") ?? "--";
  return (
    <div className="sidebar-user">
      <span className="avatar">{initials}</span>
      <span className="sidebar-user-copy"><strong>{user?.name ?? "Your account"}</strong><small>{user?.is_demo ? "DEMO ACCOUNT" : "Personal account"}</small></span>
      <span className="online-dot" aria-label="Account active" />
    </div>
  );
}
