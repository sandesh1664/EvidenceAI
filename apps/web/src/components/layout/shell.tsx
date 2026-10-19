"use client";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/lib/auth/session";
import { useResource } from "@/hooks/use-resource";
import type { Workspace } from "@/types/api";
import { ErrorBox, Loading } from "@/components/ui";
export function PrivateShell({ children }: { children: React.ReactNode }) {
  const { user, loading, error, refresh, signOut } = useSession();
  const router = useRouter();
  const params = useParams<{ workspaceId?: string }>();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [logoutError, setLogoutError] = useState<unknown>();
  const workspaces = useResource<Workspace[]>(
    user ? "/api/v1/workspaces/?limit=100" : null,
    user?.id || "",
  );
  useEffect(() => {
    if (!loading && !user && !error) router.replace("/login");
  }, [user, loading, error, router]);
  if (loading) return <Loading label="Checking your session…" />;
  if (error)
    return (
      <main className="auth-form">
        <ErrorBox error={error} retry={() => void refresh()} />
      </main>
    );
  if (!user) return <Loading label="Opening sign in…" />;
  const root = params.workspaceId ? `/workspaces/${params.workspaceId}` : null;
  const navigation = [
    { href: "/workspaces", label: "Workspaces", icon: "▦" },
    ...(root
      ? [
          { href: root, label: "Overview", icon: "◫" },
          { href: root + "/documents", label: "Documents", icon: "▤" },
          { href: root + "/research", label: "Research", icon: "✧" },
          { href: root + "/conversations", label: "Conversations", icon: "☷" },
          { href: root + "/search", label: "Search", icon: "⌕" },
          { href: root + "/members", label: "Members", icon: "♧" },
        ]
      : []),
    { href: "/settings", label: "Settings", icon: "⚙" },
  ];
  async function logout() {
    setLogoutError(undefined);
    try {
      await signOut();
      router.replace("/login");
    } catch (error) {
      setLogoutError(error);
    }
  }
  return (
    <div
      className={
        "app-shell " +
        (collapsed ? "collapsed " : "") +
        (open ? "nav-open" : "")
      }
      key={user.id}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {open && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside className="sidebar" aria-label="Main navigation">
        <Link className="brand" href="/workspaces">
          <span className="brand-mark">E</span>
          <span className="nav-label">EvidenceAI</span>
        </Link>
        <div className="sidebar-caption nav-label">RESEARCH WORKSPACE</div>
        <label className="workspace-switch nav-label">
          Current workspace
          <select
            aria-label="Switch workspace"
            value={params.workspaceId || ""}
            onChange={(event) => {
              setOpen(false);
              router.push(
                event.target.value
                  ? "/workspaces/" + event.target.value
                  : "/workspaces",
              );
            }}
          >
            <option value="">All workspaces</option>
            {params.workspaceId &&
              !workspaces.data?.some((w) => w.id === params.workspaceId) && (
                <option value={params.workspaceId}>Current workspace</option>
              )}
            {workspaces.data?.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>
        <nav>
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              prefetch={false}
              title={item.label}
              className={pathname === item.href ? "active" : ""}
              aria-current={pathname === item.href ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              <span aria-hidden="true">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note nav-label">
            <strong>Grounded in your sources</strong>
            <p>Every answer starts with the evidence.</p>
          </div>
          <div className="account">
            <span className="avatar" aria-hidden="true">
              {user.display_name.slice(0, 1).toUpperCase()}
            </span>
            <div className="nav-label">
              <strong>{user.display_name}</strong>
              <span>Private account</span>
            </div>
          </div>
          <button className="sidebar-button" onClick={() => void logout()}>
            ↪ <span className="nav-label">Sign out</span>
          </button>
          {!!logoutError && <ErrorBox error={logoutError} />}
          <button
            className="sidebar-button desktop-collapse"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? "→" : "←"} <span className="nav-label">Collapse</span>
          </button>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <button
            className="button small mobile-menu"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            ☰
          </button>
          <span>
            Workspace <span className="breadcrumb-slash">/</span>{" "}
            <strong>
              {navigation.find((item) => item.href === pathname)?.label ||
                "Research history"}
            </strong>
          </span>
          <Link href="/settings" className="topbar-account">
            {user.display_name}
          </Link>
        </header>
        <main
          id="main"
          className="main-content"
          key={user.id + ":" + (params.workspaceId || "")}
        >
          {children}
        </main>
        <footer className="app-footer">
          EvidenceAI <span>Private research. Traceable sources.</span>
        </footer>
      </div>
    </div>
  );
}
