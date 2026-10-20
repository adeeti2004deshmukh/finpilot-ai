"use client";
import { useState, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { apiRequest } from "@/services/api";
import { formatCurrency } from "@/utils/format";
import { announceAccountChange } from "@/services/auth-events";

const steps = ["About you", "Monthly finances", "Financial priorities", "First goal", "Ready to begin"];
export default function OnboardingView() {
  const { user, logout } = useAuth();
  const [step, setStep] = useState(0);
  const [name, setName] = useState<string | null>(null);
  const displayName = name ?? user?.name ?? "";
  const [age, setAge] = useState("");
  const [income, setIncome] = useState("0");
  const [essential, setEssential] = useState("0");
  const [savings, setSavings] = useState("0");
  const [emergency, setEmergency] = useState("0");
  const [debt, setDebt] = useState("0");
  const [payment, setPayment] = useState("0");
  const [months, setMonths] = useState("6");
  const [custom, setCustom] = useState("9");
  const [risk, setRisk] = useState("MODERATE");
  const [skipGoal, setSkipGoal] = useState(true);
  const [goalName, setGoalName] = useState("");
  const [goalKind, setGoalKind] = useState("OTHER");
  const [target, setTarget] = useState("");
  const [current, setCurrent] = useState("0");
  const [date, setDate] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    if (step === 1 && Number(emergency) > Number(savings)) { setError("Emergency savings must be included in current savings."); return; }
    if (step < 4) { setStep(step + 1); return; }
    setBusy(true);
    try {
      await apiRequest("/api/auth/onboarding", { method: "POST", body: JSON.stringify({ name: displayName, age: age ? Number(age) : null,
        monthly_income: income, typical_essential_expenses: essential, current_savings: savings, emergency_savings: emergency,
        total_debt: debt, monthly_debt_payment: payment, emergency_fund_target_months: Number(months === "custom" ? custom : months), risk_tolerance: risk,
        first_goal: skipGoal ? null : { name: goalName, goal_type: goalKind, target_amount: target, current_amount: current, target_date: date || null, monthly_contribution: "0", priority: 3 },
      }) });
      announceAccountChange();
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- Reload the updated authentication and onboarding context.
      window.location.assign("/");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to complete onboarding."); setBusy(false); }
  }
  const amount = (id: string, label: string, value: string, setter: (value: string) => void) => <div className="field" key={id}><label htmlFor={id}>{label}</label><input id={id} className="input" type="number" min="0" max="999999999999.99" step="0.01" required value={value} onChange={(event) => setter(event.target.value)} /></div>;
  return <main className="auth-layout"><section className="auth-card onboarding-card panel"><div className="auth-brand"><ShieldCheck /> FinPilot AI</div><p className="eyebrow">Step {step + 1} of 5</p><div className="onboarding-progress">{steps.map((label, index) => <span key={label} className={index <= step ? "onboarding-step active" : "onboarding-step"}>{label}</span>)}</div><h1>{steps[step]}</h1>
    <form method="post" className="form-grid" onSubmit={submit}>
      {step === 0 && <><p className="form-wide">Tell us how you would like to be addressed. Age is optional.</p><div className="field form-wide"><label htmlFor="onboard-name">Name</label><input id="onboard-name" className="input" required maxLength={120} value={displayName} onChange={(event) => setName(event.target.value)} /></div><div className="field"><label htmlFor="onboard-age">Age (optional)</label><input id="onboard-age" className="input" type="number" min="18" max="100" value={age} onChange={(event) => setAge(event.target.value)} /></div></>}
      {step === 1 && <><p className="form-wide">Amounts in INR. Estimates are separate from recorded expenses; emergency funds are included in total current savings.</p>{amount("onboard-income", "Monthly take-home income", income, setIncome)}{amount("onboard-essential", "Typical essential monthly expenses", essential, setEssential)}{amount("onboard-savings", "Current savings", savings, setSavings)}{amount("onboard-emergency", "Emergency fund amount", emergency, setEmergency)}{amount("onboard-debt", "Total debt (optional)", debt, setDebt)}{amount("onboard-payment", "Monthly debt payment (optional)", payment, setPayment)}</>}
      {step === 2 && <><div className="field"><label htmlFor="onboard-months">Emergency fund target</label><select id="onboard-months" className="select" value={months} onChange={(event) => setMonths(event.target.value)}><option value="3">3 months</option><option value="6">6 months</option><option value="custom">Custom</option></select></div>{months === "custom" && <div className="field"><label htmlFor="onboard-custom">Target months (1-24)</label><input id="onboard-custom" className="input" type="number" min="1" max="24" required value={custom} onChange={(event) => setCustom(event.target.value)} /></div>}<div className="field"><label htmlFor="onboard-risk">Risk tolerance</label><select id="onboard-risk" className="select" value={risk} onChange={(event) => setRisk(event.target.value)}><option value="LOW">Conservative</option><option value="MODERATE">Moderate</option><option value="HIGH">Aggressive</option></select></div><p className="form-wide">Risk tolerance is used for educational category comparisons. It does not guarantee returns or recommend specific funds or stocks.</p></>}
      {step === 3 && <><label className="form-wide"><input type="checkbox" checked={skipGoal} onChange={(event) => setSkipGoal(event.target.checked)} /> Skip for now</label>{!skipGoal && <><div className="field form-wide"><label htmlFor="onboard-goal-example">Goal inspiration</label><select id="onboard-goal-example" className="select" onChange={(event) => { setGoalName(event.target.value); setGoalKind(event.target.value === "Emergency Fund" ? "EMERGENCY_FUND" : event.target.value === "Travel" ? "TRAVEL" : "OTHER"); }}><option value="">Custom goal</option>{["Emergency Fund", "Travel", "Wedding", "Car", "Home", "Education", "Retirement"].map((value) => <option key={value}>{value}</option>)}</select></div><div className="field form-wide"><label htmlFor="onboard-goal-name">Goal name</label><input id="onboard-goal-name" className="input" required maxLength={120} value={goalName} onChange={(event) => setGoalName(event.target.value)} /></div>{amount("onboard-target", "Target amount", target, setTarget)}{amount("onboard-current", "Current amount", current, setCurrent)}<div className="field"><label htmlFor="onboard-date">Target date</label><input id="onboard-date" className="input" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></div></>}</>}
      {step === 4 && <div className="form-wide"><p>Your workspace is ready, {displayName}. No demo transactions will be added.</p><dl className="onboarding-summary"><dt>Monthly income assumption</dt><dd>{formatCurrency(income)}</dd><dt>Typical essential expenses</dt><dd>{formatCurrency(essential)}</dd><dt>Current / emergency savings</dt><dd>{formatCurrency(savings)} / {formatCurrency(emergency)}</dd><dt>Emergency target</dt><dd>{months === "custom" ? custom : months} months</dd><dt>Risk tolerance</dt><dd>{risk}</dd><dt>First goal</dt><dd>{skipGoal ? "Add later" : goalName}</dd></dl><p>Recorded expenses start at zero. Record salary under Salary to replace the take-home income assumption, without counting it twice.</p></div>}
      {error && <p className="auth-error form-wide" role="alert">{error}</p>}<div className="form-actions form-wide">{step > 0 && <button type="button" className="button button-light" disabled={busy} onClick={() => setStep(step - 1)}>Back</button>}<button className="button button-primary" disabled={busy}>{busy ? "Saving..." : step === 4 ? "Go to my dashboard" : "Continue"}</button></div>
    </form><button className="section-link" onClick={() => logout().catch((reason: Error) => setError(reason.message))}>Sign Out</button>
  </section></main>;
}
