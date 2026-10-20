"use client";

import { ArrowDownRight, ArrowUpRight, RefreshCw } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { CategoryAmount, Goal, WhatIfResult, WhatIfType } from "@/types/api";
import { formatCurrency } from "@/utils/format";

const scenarioOptions: { value: WhatIfType; label: string; amountLabel: string }[] = [
  { value: "INCOME_INCREASE", label: "Income increases", amountLabel: "Monthly income change (INR)" },
  { value: "RENT_INCREASE", label: "Rent increases", amountLabel: "Monthly rent increase (INR)" },
  { value: "FOOD_SPENDING_REDUCTION", label: "Reduce food spending", amountLabel: "Monthly reduction (INR)" },
  { value: "SAVINGS_INCREASE", label: "Increase savings", amountLabel: "Additional savings (INR)" },
  { value: "GOAL_DELAY", label: "Delay a goal", amountLabel: "Delay duration" },
];

export default function WhatIfView() {
  const [foodCategory, setFoodCategory] = useState("");
  const [expenseCategories, setExpenseCategories] = useState<CategoryAmount[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [scenarioType, setScenarioType] = useState<WhatIfType>("INCOME_INCREASE");
  const [amount, setAmount] = useState("10000");
  const [goalId, setGoalId] = useState("");
  const [delayMonths, setDelayMonths] = useState("12");
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [goalsLoading, setGoalsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([financeApi.goals(), financeApi.dashboard()]).then(([items, dashboard]) => {
      if (cancelled) return;
      setGoals(items);
      setExpenseCategories(dashboard.expense_by_category);
      if (items.length) setGoalId(String(items[0].id));
    }).catch((reason: Error) => { if (!cancelled) setError(reason.message); }).finally(() => { if (!cancelled) setGoalsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function runScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = scenarioType === "GOAL_DELAY"
        ? { scenario_type: scenarioType, goal_id: Number(goalId), delay_months: Number(delayMonths) }
        : { scenario_type: scenarioType, amount, ...(scenarioType === "FOOD_SPENDING_REDUCTION" && foodCategory ? { category_ids: [Number(foodCategory)] } : {}) };
      setResult(await financeApi.whatIf(payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not calculate this scenario.");
      setResult(null);
    } finally { setLoading(false); }
  }

  const selectedOption = scenarioOptions.find((item) => item.value === scenarioType)!;

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Explore a change</p><h2>What-if planner</h2><p>Compare a single scenario with the current recorded financial picture.</p></div></div>
    <div className="what-if-layout">
      <section className="panel what-if-form"><div className="section-heading"><div><h3>Scenario inputs</h3><p>Results are deterministic and use current recorded values.</p></div></div><form className="form-grid" onSubmit={runScenario}>
        <div className="field form-wide"><label htmlFor="scenario-type">What would you like to change?</label><select id="scenario-type" className="select" value={scenarioType} onChange={(event) => { setScenarioType(event.target.value as WhatIfType); setResult(null); }}><option value="INCOME_INCREASE">What if income increases?</option><option value="RENT_INCREASE">What if rent increases?</option><option value="FOOD_SPENDING_REDUCTION">What if food spending decreases?</option><option value="SAVINGS_INCREASE">What if monthly savings increases?</option><option value="GOAL_DELAY">What if I delay a goal?</option></select></div>
        {scenarioType === "GOAL_DELAY" ? <><div className="field form-wide"><label htmlFor="scenario-goal">Goal</label><select id="scenario-goal" className="select" required value={goalId} onChange={(event) => setGoalId(event.target.value)} disabled={goalsLoading}><option value="">Select a goal</option>{goals.filter((goal) => goal.target_date).map((goal) => <option value={goal.id} key={goal.id}>{goal.name}</option>)}</select></div><div className="field form-wide"><label htmlFor="scenario-delay">Delay (months)</label><input id="scenario-delay" className="input" type="number" min="1" max="120" required value={delayMonths} onChange={(event) => setDelayMonths(event.target.value)} /></div></> : <div className="field form-wide"><label htmlFor="scenario-amount">{selectedOption.amountLabel}</label><input id="scenario-amount" className="input" type="number" min="0.01" step="0.01" required value={amount} onChange={(event) => setAmount(event.target.value)} /></div>}
        {scenarioType === "FOOD_SPENDING_REDUCTION" && <div className="field form-wide"><label htmlFor="food-category">Food category</label><select id="food-category" className="select" value={foodCategory} onChange={(event) => setFoodCategory(event.target.value)}><option value="">Detect categories named food</option>{expenseCategories.filter((category) => category.category_id !== null).map((category) => <option key={category.category_id} value={category.category_id!}>{category.category}</option>)}</select><small>Select the category you use for food when it has a different name.</small></div>}
        <div className="form-actions"><button className="button button-primary" disabled={loading || (scenarioType === "GOAL_DELAY" && !goalId)}>{loading ? <><RefreshCw size={14} className="spin-icon" /> Calculating…</> : "Compare scenario"}</button></div>
      </form>{error && <div className="section-block"><ErrorState message={error} /></div>}</section>
      <section className="panel what-if-results"><div className="section-heading"><div><h3>Current vs scenario</h3><p>Phase 1 calculations and Phase 4 priorities.</p></div></div>
        {loading ? <LoadingSkeleton rows={3} /> : !result ? <EmptyState title="Scenario comparison will appear here" message="Choose a change to see its effect on savings rate, monthly surplus, investable capacity, emergency coverage, and goal feasibility." /> : <>
          <div className="what-if-compare-grid"><ScenarioColumn label="Current" snapshot={result.current} /><ScenarioColumn label="Scenario" snapshot={result.projected} /></div>
          <div className="scenario-deltas">{compareMetric("Monthly surplus", result.current.monthly_surplus, result.projected.monthly_surplus)}{compareMetric("Investable surplus", result.current.investable_surplus, result.projected.investable_surplus)}{compareMetric("Savings rate", result.current.savings_rate, result.projected.savings_rate, "%")}</div>
          {result.warnings.map((warning) => <p className="simulator-footnote" key={warning}>{warning}</p>)}
        </>}
      </section>
    </div>
  </div>;
}

function ScenarioColumn({ label, snapshot }: { label: string; snapshot: WhatIfResult["current"] }) {
  return <div className="scenario-column"><p>{label}</p><div><span>Income</span><strong>{formatCurrency(snapshot.monthly_income)}</strong></div><div><span>Expenses</span><strong>{formatCurrency(snapshot.monthly_expenses)}</strong></div><div><span>Actual savings</span><strong>{formatCurrency(snapshot.actual_monthly_savings)}</strong></div><div><span>Surplus</span><strong>{formatCurrency(snapshot.monthly_surplus)}</strong></div><div><span>Investable</span><strong>{formatCurrency(snapshot.investable_surplus)}</strong></div><div><span>Emergency coverage</span><strong>{Number(snapshot.emergency_fund_months).toFixed(1)} months</strong></div><div><span>Goals on track</span><strong>{snapshot.goal_feasibility.filter((goal) => goal.funding_status === "ON_TRACK").length}/{snapshot.goal_feasibility.length}</strong></div></div>;
}

function compareMetric(label: string, beforeValue: string | number, afterValue: string | number, suffix = "") {
  const before = Number(beforeValue);
  const after = Number(afterValue);
  const improves = after >= before;
  const Icon = improves ? ArrowUpRight : ArrowDownRight;
  const format = (value: number) => suffix === "%" ? `${value.toFixed(1)}%` : formatCurrency(value);
  return <div className="scenario-delta" key={label}><span>{label}</span><strong>{format(before)} <Icon size={13} className={improves ? "delta-positive" : "delta-negative"} /> {format(after)}</strong></div>;
}