"use client";

import { ArrowRight, BookOpenCheck, Landmark, LineChart, ShieldCheck, WalletCards } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState, ErrorState, LoadingSkeleton, ProgressBar } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { Goal, GoalComparison, InvestmentCategoryGuidance, InvestmentPlan } from "@/types/api";
import { formatCurrency, percent, titleCase } from "@/utils/format";

export default function InvestmentsView() {
  const [plan, setPlan] = useState<InvestmentPlan | null>(null);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [categories, setCategories] = useState<InvestmentCategoryGuidance[]>([]);
  const [comparison, setComparison] = useState<GoalComparison | null>(null);
  const [selectedGoal, setSelectedGoal] = useState("");
  const [loading, setLoading] = useState(true);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [error, setError] = useState("");
  const [comparisonError, setComparisonError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([financeApi.investmentPlan(), financeApi.goals(), financeApi.investmentCategories()])
      .then(([planData, goalData, categoryData]) => {
        if (cancelled) return;
        setPlan(planData);
        setGoals(goalData);
        setCategories(categoryData);
        setSelectedGoal(goalData.length ? String(goalData[0].id) : "");
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [retry]);

  useEffect(() => {
    if (!selectedGoal) {
      return;
    }
    let cancelled = false;
    financeApi.compareGoal(Number(selectedGoal))
      .then((result) => { if (!cancelled) setComparison(result); })
      .catch((reason: Error) => { if (!cancelled) setComparisonError(reason.message); })
      .finally(() => { if (!cancelled) setComparisonLoading(false); });
    return () => { cancelled = true; };
  }, [selectedGoal]);

  if (loading) return <LoadingSkeleton rows={4} />;
  if (error) return <ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} />;
  if (!plan) return <EmptyState title="Investment plan is unavailable" message="The backend did not return a planning result for your profile." />;

  const capacity = [
    { label: "Monthly income", value: plan.monthly_income, hint: "Take-home income plus other recorded income.", icon: WalletCards },
    { label: "Monthly expenses", value: plan.monthly_expenses, hint: "Essential and discretionary expenses; debt is subtracted separately.", icon: Landmark },
    { label: "Monthly savings", value: plan.actual_monthly_savings, hint: "Savings transactions actually recorded this month.", icon: ShieldCheck },
    { label: "Monthly surplus", value: plan.monthly_surplus, hint: "Income minus expenses and debt obligations; before savings transfers.", icon: LineChart },
    { label: "Safety buffer", value: plan.safety_buffer, hint: `Reserved this month toward a target of ${formatCurrency(plan.safety_buffer_target)}.`, icon: ShieldCheck },
    { label: "Investable surplus", value: plan.investable_surplus, hint: "Remaining longer-term allocation capacity after current priorities and the unallocated reserve.", icon: BookOpenCheck },
  ];
  const chartData = plan.allocations.filter((allocation) => Number(allocation.amount) > 0).map((allocation) => ({ purpose: allocation.purpose, amount: Number(allocation.amount) }));

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Education before allocation</p><h2>Investment planner</h2><p>Purpose allocation first. Educational category guidance second.</p></div><Link className="button button-light" href="/simulator">Open simulator <ArrowRight size={14} /></Link></div>

    <section className="investment-capacity">
      <div className="section-heading"><div><h3>Your monthly financial capacity</h3><p>Every figure is calculated from your profile and recorded transactions.</p></div><span className="status-pill status-neutral">INR · Monthly</span></div>
      <div className="capacity-grid">{capacity.map(({ label, value, hint, icon: Icon }) => <article className="capacity-item" key={label} title={hint}><div><span>{label}</span><Icon size={15} aria-hidden="true" /></div><strong>{formatCurrency(value)}</strong><small>{hint}</small></article>)}</div>
    </section>

    <section className="panel section-block">
      <details className="why-details"><summary>Monthly funding ledger and goal feasibility</summary>
        <p>Scheduled goals: {formatCurrency(plan.scheduled_goal_contributions)}. Funded non-emergency goals: {formatCurrency(plan.goal_contributions)}. Emergency contribution: {formatCurrency(plan.emergency_fund_contribution)}. Unallocated buffer: {formatCurrency(plan.unallocated_buffer)}.</p>
        <p>Recorded savings overlap existing goal funding by {formatCurrency(plan.savings_goal_overlap)}. These descriptive totals overlap; add only the ledger rows below.</p>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Cash use</th><th>Amount</th></tr></thead><tbody>{plan.funding_ledger.length === 0 && <tr><td colSpan={2}>No cash is currently reserved or allocated.</td></tr>}{plan.funding_ledger.map((line, index) => <tr key={`${line.reason_code}-${index}`}><td>{line.purpose}</td><td>{formatCurrency(line.amount)}</td></tr>)}</tbody><tfoot><tr><th>Total reserved or allocated</th><td>{formatCurrency(plan.allocation_total)}</td></tr></tfoot></table></div>
        <div className="table-wrap section-block"><table className="data-table"><thead><tr><th>Goal</th><th>Horizon</th><th>Required / month</th><th>Funded / month</th><th>Status</th></tr></thead><tbody>{plan.goal_analysis.length === 0 && <tr><td colSpan={5}>No saved goals to analyze.</td></tr>}{plan.goal_analysis.map((goal) => <tr key={goal.goal_id}><td>{goal.name}</td><td>{titleCase(goal.goal_horizon)}</td><td>{goal.remaining_months === null ? "Set a target date" : formatCurrency(goal.required_monthly_contribution)}</td><td>{formatCurrency(goal.funded_monthly_contribution)}</td><td>{titleCase(goal.funding_status)}</td></tr>)}</tbody></table></div>
      </details>
    </section>

    <section className="section-block priority-section">
      <div className="section-heading"><div><h3>Financial priorities</h3><p>Current commitments are evaluated before long-term allocation.</p></div></div>
      <div className="priority-list">{plan.financial_priorities.length === 0 && <p>No financial priorities were returned for this period.</p>}{plan.financial_priorities.map((priority, index) => <article className="priority-row" key={`${priority.reason_code}-${priority.related_goal_id ?? "base"}`}><span className={`priority-number priority-${priority.priority_level.toLowerCase()}`}>{index + 1}</span><div className="priority-copy"><div><strong>{priority.purpose}</strong><span className={`priority-pill priority-pill-${priority.priority_level.toLowerCase()}`}>{priority.priority_level} PRIORITY</span></div><p>{priority.action}</p><small>{priority.reason}</small></div></article>)}</div>
    </section>

    <section className="allocation-section section-block">
      <div className="section-heading"><div><h3>Suggested purpose allocation</h3><p>Amounts are capped by cash remaining after recorded savings and current commitments.</p></div><span className="allocation-total">{formatCurrency(plan.investable_surplus)} long-term capacity</span></div>
      {plan.allocations.length === 0 ? <div className="panel"><EmptyState title="No new allocation is available" message="Current expenses, savings, safety buffer, emergency needs, and goal commitments use the available monthly surplus." /></div> : <div className="allocation-layout">
        <div className="panel allocation-chart-panel">{chartData.length ? <ResponsiveContainer width="100%" height={Math.max(190, chartData.length * 50)}><BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 20, left: 4, bottom: 4 }}><CartesianGrid horizontal={false} stroke="#edf0ed" /><XAxis type="number" tickFormatter={(value: number) => value >= 1000 ? `₹${(value / 1000).toFixed(0)}k` : `₹${value}`} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><YAxis type="category" dataKey="purpose" width={125} tickLine={false} axisLine={false} tick={{ fill: "#68756d", fontSize: 9 }} /><Tooltip formatter={(value) => formatCurrency(Number(value))} contentStyle={{ borderRadius: 7, borderColor: "#e6eae5", fontSize: 10 }} /><Bar dataKey="amount" name="Monthly allocation" fill="#2d785d" radius={[0, 4, 4, 0]} maxBarSize={19} /></BarChart></ResponsiveContainer> : <EmptyState title="No allocation amounts" message="No cash is currently available to allocate." />}</div>
        <div className="allocation-list">{plan.allocations.map((allocation) => <article className="allocation-row" key={`${allocation.purpose}-${allocation.reason_code}`}><div className="allocation-row-top"><div><strong>{allocation.purpose}</strong><span>{allocation.reason_code.replaceAll("_", " ")}</span></div><b>{formatCurrency(allocation.amount)}</b></div><div className="allocation-bar"><ProgressBar value={percent(allocation.percentage)} tone={allocation.reason_code === "SAFETY_BUFFER" ? "amber" : "green"} /><span>{Number(allocation.percentage).toFixed(1)}%</span></div><details className="why-details"><summary>Why this?</summary><p>{allocation.reason}</p>{allocation.categories_to_explore.length > 0 && <div className="category-chips">{allocation.categories_to_explore.map((category) => <span key={category.name}>{category.name}</span>)}</div>}</details></article>)}</div>
      </div>}
      <div className="planner-methodology section-block"><strong>How capacity is calculated</strong><p>{plan.methodology.join(" ")}</p></div>
      {plan.warnings.length > 0 && <div className="planner-warnings">{plan.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
    </section>

    <section className="section-block goal-comparison-section">
      <div className="section-heading"><div><h3>Compare categories for a goal</h3><p>Relevance scores are planning heuristics, not return forecasts or guarantees.</p></div></div>
      {goals.length === 0 ? <div className="panel"><EmptyState title="No saved goals" message="Create a goal to compare educational category relevance against its date and funding gap." /></div> : <div className="panel goal-compare-panel">
        <div className="goal-compare-select"><div className="field"><label htmlFor="compare-goal">What is your goal?</label><select id="compare-goal" className="select" value={selectedGoal} onChange={(event) => { setComparisonLoading(true); setComparisonError(""); setComparison(null); setSelectedGoal(event.target.value); }}>{goals.map((goal) => <option value={goal.id} key={goal.id}>{goal.name} · {goal.target_date ?? "No target date"}</option>)}</select></div>{comparison && <div className="goal-compare-summary"><span>{titleCase(comparison.goal.goal_horizon)}</span><span>{comparison.goal.remaining_months ?? "—"} months</span><span>{formatCurrency(comparison.goal.required_monthly_contribution)}/mo required</span></div>}</div>
        {comparisonError ? <ErrorState message={comparisonError} /> : comparisonLoading || (Boolean(selectedGoal) && !comparison) ? <LoadingSkeleton rows={2} /> : comparison ? <div className="table-wrap section-block"><table className="data-table relevance-table"><thead><tr><th>Category to explore</th><th>Relevance</th><th>Risk</th><th>Liquidity</th><th>Why</th></tr></thead><tbody>{comparison.categories_to_explore.length === 0 && <tr><td colSpan={5}>No category relevance data is available for this goal.</td></tr>}{comparison.categories_to_explore.map((category) => <tr key={category.name}><td><strong>{category.name}</strong><small className="table-subtext">{category.market_linked ? "Market-linked" : "Not market-linked"}</small></td><td><span className={`status-pill ${category.relevance_score && category.relevance_score >= 80 ? "status-on-track" : category.relevance_score && category.relevance_score >= 60 ? "status-warning" : "status-neutral"}`}>{category.relevance_level} · {category.relevance_score}</span></td><td>{titleCase(category.risk_level)}</td><td>{titleCase(category.liquidity)}</td><td>{category.relevance_reason}</td></tr>)}</tbody></table></div> : null}
        {comparison && <p className="comparison-methodology">{comparison.methodology}</p>}
      </div>}
    </section>

    <section className="section-block category-knowledge-section"><div className="section-heading"><div><h3>Category knowledge</h3><p>Broad educational categories only. No individual products are recommended.</p></div></div><div className="category-knowledge-grid">{categories.length === 0 && <p>No educational category information is available.</p>}{categories.map((category) => <article className="category-knowledge-row" key={category.name}><strong>{category.name}</strong><span>{category.risk_level}</span><p>{category.description}</p><small>{category.capital_guarantee_explanation}</small></article>)}</div></section>

    <section className="planner-bottom-actions section-block"><Link className="button button-primary" href="/affordability">Can I afford this? <ArrowRight size={14} /></Link><Link className="button button-light" href="/what-if">Explore a what-if scenario <ArrowRight size={14} /></Link></section>
    <p className="financial-disclaimer">FinPilot provides educational financial information and planning tools. Investment returns are not guaranteed. Consider qualified professional advice for major financial decisions.</p>
  </div>;
}