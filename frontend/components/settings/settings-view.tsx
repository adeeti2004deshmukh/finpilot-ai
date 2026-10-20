"use client";

import { Check, Save } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { FinancialProfile, RiskTolerance, User } from "@/types/api";

interface ProfileForm {
  monthly_income: string;
  other_income: string;
  typical_essential_expenses: string;
  current_savings: string;
  emergency_savings: string;
  monthly_debt_payment: string;
  total_debt: string;
  dependents: string;
  risk_tolerance: RiskTolerance;
  emergency_fund_target_months: string;
}

export default function SettingsView() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [form, setForm] = useState<ProfileForm | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([financeApi.user(), financeApi.profile()]).then(([userData, profileData]) => {
      if (cancelled) return;
      setUser(userData);
      setProfile(profileData);
      setName(userData.name);
      setAge(userData.age === null ? "" : String(userData.age));
      setForm({
        monthly_income: String(profileData.monthly_income),
        other_income: String(profileData.other_income),
        typical_essential_expenses: String(profileData.typical_essential_expenses),
        current_savings: String(profileData.current_savings),
        emergency_savings: String(profileData.emergency_savings),
        monthly_debt_payment: String(profileData.monthly_debt_payment),
        total_debt: String(profileData.total_debt),
        dependents: String(profileData.dependents),
        risk_tolerance: profileData.risk_tolerance,
        emergency_fund_target_months: String(profileData.emergency_fund_target_months) as ProfileForm["emergency_fund_target_months"],
      });
    }).catch((reason: Error) => { if (!cancelled) setError(reason.message); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [retry]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const [userData, profileData] = await Promise.all([
        financeApi.updateUser({ name, ...(age ? { age: Number(age) } : {}) }),
        financeApi.updateProfile({
          monthly_income: form.monthly_income,
          other_income: form.other_income,
          typical_essential_expenses: form.typical_essential_expenses,
          current_savings: form.current_savings,
          emergency_savings: form.emergency_savings,
          monthly_debt_payment: form.monthly_debt_payment,
          total_debt: form.total_debt,
          dependents: Number(form.dependents),
          risk_tolerance: form.risk_tolerance,
          emergency_fund_target_months: Number(form.emergency_fund_target_months),
        }),
      ]);
      setUser(userData);
      setProfile(profileData);
      setMessage("Your profile has been updated.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save profile settings.");
    } finally { setSaving(false); }
  }

  if (loading) return <LoadingSkeleton rows={4} />;
  if (error && (!user || !profile || !form)) return <ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} />;
  if (!user || !profile || !form) return null;

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Your financial profile</p><h2>Settings</h2><p>Update the profile values used by FinPilot&apos;s dashboard calculations.</p></div></div>
    {message && <div className="success-banner" role="status"><Check size={15} />{message}</div>}
    {error && <div className="section-block"><ErrorState message={error} onRetry={() => setError("")} /></div>}
    <form className="settings-layout" onSubmit={save}>
      <section className="panel settings-card"><div className="section-heading"><div><h3>Personal details</h3><p>Your personal account details.</p></div></div><div className="form-grid">
        <div className="field"><label htmlFor="settings-name">Name</label><input id="settings-name" className="input" minLength={1} maxLength={120} required value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div className="field"><label htmlFor="settings-age">Age</label><input id="settings-age" className="input" type="number" min="18" max="100" value={age} onChange={(event) => setAge(event.target.value)} /></div>
        <div className="field form-wide"><label htmlFor="settings-email">Email</label><input id="settings-email" className="input" value={user.email} disabled /><span className="field-hint">Email changes are not supported by the current API.</span></div>
      </div></section>

      <section className="panel settings-card"><div className="section-heading"><div><h3>Financial profile</h3><p>Amounts are stored in INR. Changes flow through to your dashboard.</p></div></div><div className="form-grid">
        <NumberField id="profile-income" label="Monthly income" value={form.monthly_income} onChange={(value) => setForm({ ...form, monthly_income: value })} />
        <NumberField id="profile-essential" label="Typical essential expenses (reserve estimate)" value={form.typical_essential_expenses} onChange={(value) => setForm({ ...form, typical_essential_expenses: value })} />
        <NumberField id="profile-other-income" label="Other monthly income" value={form.other_income} onChange={(value) => setForm({ ...form, other_income: value })} />
        <NumberField id="profile-savings" label="Current savings" value={form.current_savings} onChange={(value) => setForm({ ...form, current_savings: value })} />
        <NumberField id="profile-emergency-savings" label="Emergency savings" value={form.emergency_savings} onChange={(value) => setForm({ ...form, emergency_savings: value })} />
        <NumberField id="profile-debt-payment" label="Monthly debt payment" value={form.monthly_debt_payment} onChange={(value) => setForm({ ...form, monthly_debt_payment: value })} />
        <NumberField id="profile-total-debt" label="Total debt" value={form.total_debt} onChange={(value) => setForm({ ...form, total_debt: value })} />
        <div className="field"><label htmlFor="profile-dependents">Dependents</label><input id="profile-dependents" className="input" type="number" min="0" max="30" required value={form.dependents} onChange={(event) => setForm({ ...form, dependents: event.target.value })} /></div>
        <div className="field"><label htmlFor="profile-risk">Risk tolerance</label><select id="profile-risk" className="select" value={form.risk_tolerance} onChange={(event) => setForm({ ...form, risk_tolerance: event.target.value as RiskTolerance })}><option value="LOW">Low</option><option value="MODERATE">Moderate</option><option value="HIGH">High</option></select></div>
        <div className="field"><label htmlFor="profile-emergency-target">Emergency fund target</label><input id="profile-emergency-target" className="input" type="number" min="1" max="24" required value={form.emergency_fund_target_months} onChange={(event) => setForm({ ...form, emergency_fund_target_months: event.target.value })} /></div>
      </div><div className="settings-actions"><span>Profile updated {new Date(profile.updated_at).toLocaleDateString("en-IN")}</span><button className="button button-primary" disabled={saving}><Save size={15} />{saving ? "Saving…" : "Save profile"}</button></div></section>
    </form>
  </div>;
}

function NumberField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return <div className="field"><label htmlFor={id}>{label} (INR)</label><input id={id} className="input" type="number" min="0" step="0.01" required value={value} onChange={(event) => onChange(event.target.value)} /></div>;
}