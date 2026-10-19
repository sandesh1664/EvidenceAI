"use client";
import { useSyncExternalStore, useState } from "react";
import { useSession } from "@/lib/auth/session";
import { useResource } from "@/hooks/use-resource";
import type { User } from "@/types/api";
import { API_ORIGIN } from "@/lib/api/client";
import { Badge, ErrorBox, PageHeading, date } from "@/components/ui";
function themeSnapshot() {
  try {
    return (
      localStorage.getItem("evidenceai:theme") ||
      document.documentElement.dataset.theme ||
      "system"
    );
  } catch {
    return document.documentElement.dataset.theme || "system";
  }
}
function subscribe(callback: () => void) {
  window.addEventListener("evidenceai:theme", callback);
  return () => window.removeEventListener("evidenceai:theme", callback);
}
export function applyTheme(value: string) {
  try {
    localStorage.setItem("evidenceai:theme", value);
  } catch {
    /* Theme still applies when storage is unavailable. */
  }
  document.documentElement.dataset.theme = value;
  window.dispatchEvent(new Event("evidenceai:theme"));
}
export function Settings() {
  const { user } = useSession();
  const health = useResource<User>("/api/v1/auth/me", user?.id || "");
  const theme = useSyncExternalStore(subscribe, themeSnapshot, () => "system");
  const [copied, setCopied] = useState(false);
  return (
    <>
      <PageHeading
        eyebrow="ACCOUNT & PREFERENCES"
        title="Your settings"
        description="Your account, your display preferences and the connection behind your research."
      />
      <div className="settings-grid">
        <section className="panel">
          <h2>Profile</h2>
          {user && (
            <dl>
              <dt>Full name</dt>
              <dd>{user.display_name}</dd>
              <dt>Email</dt>
              <dd>{user.email}</dd>
              <dt>Account ID</dt>
              <dd>
                <code>{user.id}</code>{" "}
                <button
                  className="button small"
                  onClick={() =>
                    void navigator.clipboard
                      .writeText(user.id)
                      .then(() => setCopied(true))
                      .catch(() => setCopied(false))
                  }
                >
                  {copied ? "Copied" : "Copy ID"}
                </button>
              </dd>
              <dt>Member since</dt>
              <dd>{date(user.created_at)}</dd>
            </dl>
          )}
          <p className="hint">
            Share your account ID with a workspace manager to be added. Profile
            updates are not supported by the current API.
          </p>
        </section>
        <section className="panel">
          <h2>Appearance</h2>
          <p>Choose the theme that helps you focus.</p>
          <label>
            Theme
            <select
              value={theme}
              onChange={(event) => applyTheme(event.target.value)}
            >
              <option value="system">Use system setting</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <p className="hint">
            Only this non-sensitive preference is stored in your browser.
          </p>
        </section>
        <section className="panel">
          <div className="section-heading">
            <h2>API connection</h2>
            <button className="button small" onClick={health.refresh}>
              Check connection
            </button>
          </div>
          {health.error ? (
            <ErrorBox error={health.error} retry={health.refresh} />
          ) : (
            <Badge tone={health.data ? "green" : ""}>
              {health.data
                ? "Authenticated API reachable"
                : "Checking connection"}
            </Badge>
          )}
          <p>
            <code>{API_ORIGIN || "Same origin"}</code>
          </p>
          <p className="hint">
            The session endpoint is reachable. This does not prove worker or
            provider readiness.
          </p>
        </section>
        <section className="panel">
          <h2>Research providers</h2>
          <Badge>Configuration not exposed</Badge>
          <p>
            The current API does not offer a provider-settings endpoint.
            Availability is reported when search, indexing or generation is
            requested.
          </p>
          <p className="hint">
            Offline mock responses and fake embedding profiles are labeled in
            results. Model configuration and keys belong on the backend.
          </p>
        </section>
      </div>
    </>
  );
}
