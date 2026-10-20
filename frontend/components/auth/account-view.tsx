"use client";
import Link from "next/link";
import { useState, useSyncExternalStore, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";
import { apiRequest } from "@/services/api";
import type { AuthUser } from "@/components/auth/auth-provider";
import { announceAccountChange } from "@/services/auth-events";

const subscribeHydration = () => () => {};
export default function AccountView({ register = false }: { register?: boolean }) {
  const hydrated = useSyncExternalStore(subscribeHydration, () => true, () => false);
  const prefix = register ? "register" : "login";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const data = new FormData(event.currentTarget);
    const body = Object.fromEntries(data.entries());
    if (register && body.password !== body.confirm_password) { setError("Passwords do not match."); setBusy(false); return; }
    try {
      const user = await apiRequest<AuthUser>(register ? "/api/auth/register" : "/api/auth/login", { method: "POST", body: JSON.stringify(body) });
      announceAccountChange();
      window.location.assign(user.onboarding_completed ? "/" : "/onboarding");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to sign in."); setBusy(false); }
  }
  async function demo() {
    setError(""); setBusy(true);
    try {
      await apiRequest("/api/auth/demo", { method: "POST" });
      announceAccountChange();
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- Clear all previous account-scoped client state.
      window.location.assign("/");
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Demo unavailable."); setBusy(false); }
  }
  return <main className="auth-layout"><section className="auth-card panel"><Link href="/login" className="auth-brand"><ShieldCheck size={25} /> FinPilot <span>AI</span></Link><p className="eyebrow">Your money, in focus</p><h1>{register ? "Create your account" : "Welcome back"}</h1><p>{register ? "A personal space for your finances and goals." : "Sign in to your financial workspace."}</p>
    <form method="post" className="form-grid" onSubmit={submit} data-hydrated={hydrated}>
      {register && <div className="field form-wide"><label htmlFor={`${prefix}-name`}>Full Name</label><input id={`${prefix}-name`} name="name" className="input" autoComplete="name" required maxLength={120} /></div>}
      <div className="field form-wide"><label htmlFor={`${prefix}-email`}>Email</label><input id={`${prefix}-email`} name="email" className="input" type="email" autoComplete="email" required maxLength={254} /></div>
      <div className="field form-wide"><label htmlFor={`${prefix}-password`}>Password</label><input id={`${prefix}-password`} name="password" className="input" type="password" autoComplete={register ? "new-password" : "current-password"} required minLength={register ? 12 : 1} maxLength={128} />{register && <small>At least 12 characters, including letters and numbers.</small>}</div>
      {register && <div className="field form-wide"><label htmlFor={`${prefix}-confirm`}>Confirm Password</label><input id={`${prefix}-confirm`} name="confirm_password" className="input" type="password" autoComplete="new-password" required maxLength={128} /></div>}
      {error && <p className="auth-error form-wide" role="alert">{error}</p>}
      <button className="button button-primary form-wide" disabled={busy || !hydrated}>{busy ? "Please wait..." : register ? "Create Account" : "Sign In"}</button>
    </form>
    <p>{register ? "Already have an account? " : "Don't have an account? "}<Link className="section-link" href={register ? "/login" : "/register"}>{register ? "Sign In" : "Create one"}</Link></p>
    {!register && <button className="button button-light" disabled={busy || !hydrated} onClick={demo}>Explore Demo</button>}
    <p className="auth-footnote">Private to your account. Educational planning, with no guaranteed investment returns.</p>
  </section></main>;
}
