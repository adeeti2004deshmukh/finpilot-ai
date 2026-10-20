"use client";

import { ArrowRight, Calculator, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState, ErrorState } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { SimulationResult } from "@/types/api";
import { formatCurrency } from "@/utils/format";

type Mode = "sip" | "rd" | "fd" | "compound-growth";
interface ProjectionPoint { month: number; contributions: number; estimated: number }

const modes: { id: Mode; label: string }[] = [
  { id: "sip", label: "SIP" },
  { id: "rd", label: "RD" },
  { id: "fd", label: "FD" },
  { id: "compound-growth", label: "Compound growth" },
];

const modeCopy: Record<Mode, { title: string; subtitle: string; contributionLabel: string; initialRate: string }> = {
  sip: { title: "SIP projection", subtitle: "Monthly contributions with an illustrative monthly-compounding assumption.", contributionLabel: "Monthly contribution", initialRate: "10" },
  rd: { title: "Recurring deposit projection", subtitle: "Monthly deposits with quarterly interest crediting in the Phase 1 engine.", contributionLabel: "Monthly deposit", initialRate: "6.5" },
  fd: { title: "Fixed deposit projection", subtitle: "A lump sum with the selected compounding frequency.", contributionLabel: "Principal amount", initialRate: "7" },
  "compound-growth": { title: "Compound growth projection", subtitle: "A one-time amount compounded monthly at the rate entered below.", contributionLabel: "Initial amount", initialRate: "8" },
};

export default function SimulatorView({ initialMode = "sip" }: { initialMode?: Mode }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [contribution, setContribution] = useState("10000");
  const [rate, setRate] = useState("10");
  const [months, setMonths] = useState("60");
  const [compoundFrequency, setCompoundFrequency] = useState("4");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [trajectory, setTrajectory] = useState<ProjectionPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasRun, setHasRun] = useState(false);

  function selectMode(nextMode: Mode) {
    setMode(nextMode);
    setRate(modeCopy[nextMode].initialRate);
    setResult(null);
    setTrajectory([]);
    setError("");
  }

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setHasRun(true);
    const duration = Number(months);
    const amount = Number(contribution);
    const annualRate = Number(rate);
    const milestoneMonths = Array.from(new Set([1, Math.ceil(duration * 0.2), Math.ceil(duration * 0.4), Math.ceil(duration * 0.6), Math.ceil(duration * 0.8), duration])).filter((value) => value > 0 && value <= duration).sort((a, b) => a - b);
    const bodyFor = (period: number) => mode === "sip" || mode === "rd"
      ? { monthly_contribution: amount, annual_rate_percent: annualRate, months: period }
      : mode === "fd"
        ? { principal: amount, annual_rate_percent: annualRate, months: period, compounds_per_year: Number(compoundFrequency) }
        : { principal: amount, annual_rate_percent: annualRate, months: period };
    try {
      const results = await Promise.all(milestoneMonths.map((period) => financeApi.simulate(mode, bodyFor(period))));
      const finalResult = results.at(-1);
      if (!finalResult) throw new Error("The simulation returned no result.");
      setResult(finalResult);
      setTrajectory(results.map((item, index) => ({ month: milestoneMonths[index], contributions: Number(item.invested_amount), estimated: Number(item.maturity_value) })));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The simulation could not be completed.");
      setResult(null);
      setTrajectory([]);
    } finally { setLoading(false); }
  }

  const isRecurring = mode === "sip" || mode === "rd";
  const copy = modeCopy[mode];
  const contributionLabel = mode === "sip" || mode === "rd" ? "Monthly contribution" : mode === "fd" ? "Principal amount" : "Initial amount";

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Illustrative calculations</p><h2>Investment simulator</h2><p>Explore how amount, duration, and stated rate affect the engine&apos;s projection.</p></div><Link className="button button-light" href="/investments">Compare approaches <ArrowRight size={14} /></Link></div>
    <div className="simulator-tabs" role="tablist" aria-label="Simulation type">{modes.map((item) => <button key={item.id} role="tab" aria-selected={mode === item.id} className={`simulator-tab${mode === item.id ? " simulator-tab-active" : ""}`} onClick={() => selectMode(item.id)}>{item.label}</button>)}</div>
    <div className="simulator-layout section-block">
      <section className="panel simulator-form-panel"><div className="section-heading"><div><h3>{copy.title}</h3><p>{copy.subtitle}</p></div><span className="simulator-icon"><Calculator size={17} /></span></div>
        <form className="simulator-form" onSubmit={calculate}>
          <div className="field"><label htmlFor="simulation-contribution">{contributionLabel} (INR)</label><input id="simulation-contribution" className="input" type="number" min="0" step="0.01" required value={contribution} onChange={(event) => setContribution(event.target.value)} /></div>
          <div className="field"><label htmlFor="simulation-duration">Duration (months)</label><input id="simulation-duration" className="input" type="number" min="1" max="1200" step="1" required value={months} onChange={(event) => setMonths(event.target.value)} /><span className="field-hint">{months && Number(months) > 0 ? `${(Number(months) / 12).toFixed(1)} years` : "1 to 1,200 months"}</span></div>
          <div className="field"><label htmlFor="simulation-rate">Illustrative annual rate (%)</label><input id="simulation-rate" className="input" type="number" min="0" max="100" step="0.01" required value={rate} onChange={(event) => setRate(event.target.value)} /><span className="field-hint">An editable scenario assumption, not a forecast.</span></div>
          {mode === "fd" && <div className="field"><label htmlFor="simulation-frequency">Compounding</label><select id="simulation-frequency" className="select" value={compoundFrequency} onChange={(event) => setCompoundFrequency(event.target.value)}><option value="1">Yearly</option><option value="2">Half-yearly</option><option value="4">Quarterly</option><option value="12">Monthly</option></select></div>}
          <button className="button button-primary simulator-submit" disabled={loading}>{loading ? <><RefreshCw size={14} className="spin-icon" /> Calculating…</> : <><Calculator size={14} /> Calculate scenario</>}</button>
        </form>
        {mode === "sip" || mode === "compound-growth" ? <div className="disclaimer simulator-disclaimer">Illustrative scenario only. Actual market returns may be higher or lower and are not guaranteed.</div> : <p className="simulator-footnote">Projection follows the Phase 1 deposit assumptions and does not reflect provider-specific terms, taxes, or penalties.</p>}
      </section>

      <section className="panel simulator-results"><div className="section-heading"><div><h3>Projection</h3><p>Calculated by the existing Phase 1 engine</p></div></div>
        {error ? <ErrorState message={error} /> : !result ? <EmptyState title={hasRun ? "No projection available" : "Your scenario will appear here"} message={hasRun ? "Review the inputs and try the calculation again." : "Enter an amount, duration, and rate to see the illustrative result."} /> : <>
          <div className="result-total"><span>Estimated maturity value</span><strong>{formatCurrency(result.maturity_value)}</strong></div>
          <div className="result-metrics"><div><span>{isRecurring ? "Total contributions" : "Initial amount"}</span><strong>{formatCurrency(result.invested_amount)}</strong></div><div><span>Estimated growth</span><strong className="text-positive">{formatCurrency(result.estimated_interest)}</strong></div></div>
          {trajectory.length ? <div className="trajectory-chart"><ResponsiveContainer width="100%" height={250}><LineChart data={trajectory} margin={{ top: 10, right: 13, left: -14, bottom: 0 }}><CartesianGrid vertical={false} stroke="#edf0ed" /><XAxis dataKey="month" tickFormatter={(value: number) => value % 12 === 0 ? `${value / 12}y` : `${value}m`} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><YAxis tickFormatter={compactCurrency} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><Tooltip content={<ProjectionTooltip />} /><Legend wrapperStyle={{ fontSize: 10 }} /><Line type="monotone" dataKey="contributions" name={isRecurring ? "Contributions" : "Initial amount"} stroke="#84988b" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="estimated" name="Estimated value" stroke="#2d785d" strokeWidth={2.5} dot={{ r: 3, fill: "#2d785d" }} /></LineChart></ResponsiveContainer></div> : null}
          <div className="projection-caption">{isRecurring ? "Each point uses a result returned by the API at that duration." : "Each point uses a result returned by the API for that elapsed duration."}</div>
        </>}
      </section>
    </div>
    <section className="afford-placeholder section-block"><div><p className="eyebrow">Coming in the next phase</p><h3>Can I afford this?</h3><p>No purchase or EMI affordability endpoint exists in the current backend.</p></div><div className="afford-fields"><span>What are you planning to buy?</span><span>Price</span><button className="button button-light" disabled>Coming next phase</button></div></section>
    <p className="financial-disclaimer">FinPilot provides educational financial information and planning tools. Investment returns are not guaranteed. Consider professional advice for major financial decisions.</p>
  </div>;
}

function ProjectionTooltip({ active, payload, label }: { active?: boolean; payload?: { name?: string; value?: number; color?: string }[]; label?: number }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>Month {label}</strong>{payload.map((item) => <div key={item.name} style={{ color: item.color }}>{item.name}: {formatCurrency(item.value ?? 0)}</div>)}</div>;
}

function compactCurrency(value: number): string {
  return value >= 100000 ? `₹${(value / 100000).toFixed(0)}L` : value >= 1000 ? `₹${(value / 1000).toFixed(0)}k` : `₹${value}`;
}