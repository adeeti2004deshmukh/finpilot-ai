"use client";

import { CheckCircle2, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";

import { EmptyState, ErrorState, LoadingSkeleton, ProgressBar } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { AffordabilityResult } from "@/types/api";
import { formatCurrency } from "@/utils/format";
import { useCurrentDateKey } from "@/utils/use-current-date";

type PaymentMethod = "CASH" | "EMI";

export default function AffordabilityView() {
  const currentDateKey = useCurrentDateKey();
  const [itemName, setItemName] = useState("");
  const [price, setPrice] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("CASH");
  const [downPayment, setDownPayment] = useState("");
  const [monthlyEmi, setMonthlyEmi] = useState("");
  const [tenure, setTenure] = useState("12");
  const [result, setResult] = useState<AffordabilityResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = {
        
        item_name: itemName,
        price,
        purchase_date: purchaseDate || currentDateKey.slice(0, 10),
        payment_method: paymentMethod,
        ...(paymentMethod === "EMI" ? { down_payment: downPayment, monthly_emi: monthlyEmi, tenure_months: Number(tenure) } : {}),
      };
      setResult(await financeApi.analyzeAffordability(payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not analyze this purchase.");
      setResult(null);
    } finally { setLoading(false); }
  }

  const scoreTone = result?.affordability_status === "COMFORTABLE" || result?.affordability_status === "MANAGEABLE" ? "green" : result?.affordability_status === "CAUTION" ? "amber" : "coral";

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Plan a purchase with context</p><h2>Can I afford this?</h2><p>Compare the purchase with current savings, monthly cash flow, debt, and goals.</p></div></div>
    <div className="affordability-layout">
      <section className="panel affordability-form-panel"><div className="section-heading"><div><h3>Purchase details</h3><p>Calculations use current recorded financial information.</p></div></div>
        <form className="form-grid" onSubmit={analyze}>
          <div className="field form-wide"><label htmlFor="purchase-item">What are you planning to buy?</label><input id="purchase-item" className="input" required maxLength={120} value={itemName} onChange={(event) => setItemName(event.target.value)} placeholder="Laptop, phone, course…" /></div>
          <div className="field"><label htmlFor="purchase-price">Price (INR)</label><input id="purchase-price" className="input" type="number" min="0.01" step="0.01" required value={price} onChange={(event) => setPrice(event.target.value)} /></div>
          <div className="field"><label htmlFor="purchase-date">Purchase date</label><input id="purchase-date" className="input" type="date" min={currentDateKey.slice(0, 10)} value={purchaseDate || currentDateKey.slice(0, 10)} onChange={(event) => setPurchaseDate(event.target.value)} required /></div>
          <fieldset className="payment-method-field form-wide"><legend>Payment method</legend><div className="simulator-tabs"><button type="button" className={`simulator-tab${paymentMethod === "CASH" ? " simulator-tab-active" : ""}`} aria-pressed={paymentMethod === "CASH"} onClick={() => setPaymentMethod("CASH")}>Cash</button><button type="button" className={`simulator-tab${paymentMethod === "EMI" ? " simulator-tab-active" : ""}`} aria-pressed={paymentMethod === "EMI"} onClick={() => setPaymentMethod("EMI")}>EMI</button></div></fieldset>
          {paymentMethod === "EMI" && <>
            <div className="field"><label htmlFor="purchase-down-payment">Down payment (INR)</label><input id="purchase-down-payment" className="input" type="number" min="0" step="0.01" required value={downPayment} onChange={(event) => setDownPayment(event.target.value)} /></div>
            <div className="field"><label htmlFor="purchase-emi">Monthly EMI (INR)</label><input id="purchase-emi" className="input" type="number" min="0.01" step="0.01" required value={monthlyEmi} onChange={(event) => setMonthlyEmi(event.target.value)} /></div>
            <div className="field"><label htmlFor="purchase-tenure">Tenure (months)</label><input id="purchase-tenure" className="input" type="number" min="1" max="600" required value={tenure} onChange={(event) => setTenure(event.target.value)} /></div>
          </>}
          <div className="form-actions"><button className="button button-primary" disabled={loading}>{loading ? "Analyzing…" : "Analyze affordability"}</button></div>
        </form>
        {error && <div className="section-block"><ErrorState message={error} /></div>}
      </section>

      <section className="panel affordability-result-panel"><div className="section-heading"><div><h3>Affordability assessment</h3><p>Deterministic planning estimate, not credit approval.</p></div></div>
        {loading ? <LoadingSkeleton rows={3} /> : !result ? <EmptyState title="Your assessment will appear here" message="Enter an item, price, date, and payment method to compare its impact with your current plan." /> : <>
          <div className={`afford-score-card afford-score-${scoreTone}`}><div><span>Affordability score</span><strong>{result.affordability_score}<small>/100</small></strong></div><span className={`status-pill ${result.affordability_status === "COMFORTABLE" || result.affordability_status === "MANAGEABLE" ? "status-on-track" : result.affordability_status === "CAUTION" ? "status-warning" : "status-over-budget"}`}>{result.affordability_status.replaceAll("_", " ")}</span><ProgressBar value={result.affordability_score} tone={scoreTone} /></div>
          <div className="before-after-grid"><div><p>Before purchase</p><strong>{formatCurrency(result.monthly_surplus_before)}</strong><span>Monthly surplus</span><strong>{formatCurrency(result.emergency_fund_before)}</strong><span>Emergency fund</span><strong>{Number(result.emergency_coverage_months_before).toFixed(1)} months</strong><span>Emergency coverage</span></div><div><p>After purchase</p><strong>{formatCurrency(result.monthly_surplus_after)}</strong><span>Monthly surplus</span><strong>{formatCurrency(result.emergency_fund_after)}</strong><span>Emergency fund</span><strong>{Number(result.emergency_coverage_months_after).toFixed(1)} months</strong><span>Emergency coverage</span></div></div>
          {Number(result.upfront_funding_shortfall) > 0 && <div className="afford-impact-row"><span>Unfunded upfront cash</span><strong>{formatCurrency(result.upfront_funding_shortfall)}</strong></div>}
          <div className="afford-impact-row"><span>Goal funding shortfall</span><strong>{formatCurrency(result.goal_impact)}/month</strong></div>
          {result.payment_method === "EMI" && <div className="afford-impact-row"><span>Debt burden after EMI</span><strong>{Number(result.debt_burden_after_percent).toFixed(1)}% of income</strong></div>}
          {result.warnings.length > 0 && <div className="afford-warning-list">{result.warnings.map((warning) => <p key={warning}><ShieldAlert size={14} />{warning}</p>)}</div>}
          <details className="why-details"><summary>Score breakdown and assumptions</summary>{Object.entries(result.score_components).map(([name, points]) => <p key={name}>{name.replaceAll("_", " ")}: {points}</p>)}{result.methodology.map((line) => <p key={line}>{line}</p>)}</details>
        </>}
      </section>
    </div>

    {result && <section className="section-block alternatives-section"><div className="section-heading"><div><h3>Alternatives to compare</h3><p>Save the cash amount without assuming returns or changes to current expenses.</p></div></div><div className="alternatives-grid">{result.alternative_scenarios.map((scenario) => <article className="panel alternative-card" key={scenario.name}><span className="eyebrow">Alternative scenario</span><h3>{scenario.name}</h3><strong>{formatCurrency(scenario.required_monthly_saving)}<small>/month</small></strong><p>Score: {scenario.affordability_score}/100 / {scenario.status.replaceAll("_", " ")}</p><p>Optional monthly capacity: {formatCurrency(scenario.available_monthly_saving)}. Saving shortfall: {formatCurrency(scenario.monthly_saving_shortfall)}.</p>{scenario.warnings.map((warning) => <p key={warning}>{warning}</p>)}<div className="goal-meta"><span>Emergency fund held</span><b>{formatCurrency(scenario.projected_emergency_fund)}</b></div></article>)}</div><p className="simulator-footnote">Waiting scenarios do not assume investment returns, future raises, price changes, taxes, or changes to other goals.</p></section>}
    <div className="afford-methodology section-block"><CheckCircle2 size={16} /><p>Score weights are shown in the API response. Cash uses non-emergency savings first; an EMI reduces monthly surplus and increases debt burden. A smaller EMI does not by itself make a purchase affordable.</p></div>
  </div>;
}
