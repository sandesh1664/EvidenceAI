"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { ErrorBox } from "@/components/ui";

export default function VerifyEmail() {
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState<unknown>();
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const values = new FormData(event.currentTarget);
    const token = String(values.get("token") || "").trim() || new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    // Fragments are never transmitted in URLs/logs or stored in localStorage.
    window.history.replaceState(null, "", window.location.pathname);
    setBusy(true); setError(undefined);
    try { await api.verifyRegistration(token); setVerified(true); }
    catch (error) { setError(error); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><section className="auth-form"><div className="auth-card">
    <h1>Verify your email</h1>
    {verified ? <div role="status"><p>Registration verified. You can now sign in with your credentials.</p><Link href="/login">Sign in</Link></div> : <>
      <p>Open your verification link in the same browser that requested registration, or paste its token below. Existing account passwords are never changed.</p>
      <form onSubmit={submit}>
        <label>Verification token<input name="token" type="password" autoComplete="off" maxLength={43} /></label>
        {!!error && <ErrorBox error={error} />}
        <button className="button primary" disabled={busy}>{busy ? "Verifying…" : "Verify email"}</button>
      </form>
      <p>No link available? <Link href="/register">Request registration again</Link> or contact the administrator.</p>
    </>}
  </div></section></main>;
}
