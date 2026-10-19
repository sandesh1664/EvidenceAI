"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { useSession } from "@/lib/auth/session";
import { ErrorBox } from "@/components/ui";
export function AuthForm({ register = false }: { register?: boolean }) {
  const router = useRouter();
  const session = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(undefined);
    const values = new FormData(event.currentTarget);
    try {
      const email = String(values.get("email")).trim();
      const password = String(values.get("password"));
      if (register)
        await api.register(email, password, String(values.get("name")).trim());
      await api.login(email, password);
      await session.refresh();
      const channel = new BroadcastChannel("evidenceai-session");
      channel.postMessage("changed");
      channel.close();
      router.replace("/workspaces");
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Link href="/" className="brand">
          <span className="brand-mark">E</span>EvidenceAI
        </Link>
        <div>
          <div className="eyebrow">YOUR EVIDENCE. IN FOCUS.</div>
          <h1>
            Find the signal.
            <br />
            Keep the source.
          </h1>
          <p>
            A considered space for documents, questions and research you can
            trace back to the evidence.
          </p>
        </div>
        <span>Built for careful research.</span>
      </section>
      <section className="auth-form">
        <div className="auth-card">
          <span className="eyebrow">WELCOME TO EVIDENCEAI</span>
          <h2>{register ? "Start your research" : "Welcome back"}</h2>
          <p>
            {register
              ? "Create an account to organize your evidence."
              : "Sign in to your private workspaces."}
          </p>
          <form onSubmit={submit}>
            {register && (
              <label>
                Full name
                <input
                  name="name"
                  autoComplete="name"
                  required
                  maxLength={200}
                />
              </label>
            )}
            <label>
              Email address
              <input
                name="email"
                type="email"
                autoComplete="email"
                required
                maxLength={320}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                required
                minLength={register ? 12 : 1}
                maxLength={128}
              />
            </label>
            {register && (
              <p className="hint">
                Use at least 12 characters. Keep your password private.
              </p>
            )}
            {!!error && <ErrorBox error={error} />}
            <button className="button primary full" disabled={busy}>
              {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
            </button>
          </form>
          <p>
            {register ? "Already have an account?" : "New to EvidenceAI?"}{" "}
            <Link href={register ? "/login" : "/register"}>
              {register ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
