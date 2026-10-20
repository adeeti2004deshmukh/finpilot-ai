"use client";

import {
  ArrowRight,
  Banknote,
  ChartNoAxesCombined,
  CircleDollarSign,
  HeartPulse,
  Info,
  PiggyBank,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState, ErrorState, LoadingSkeleton, ProgressBar } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { BudgetStatus, DashboardData, FinancialHealth, FinancialInsights, FinancialProfile, InvestmentPlan, MonthlyActionPlan, User } from "@/types/api";
import { formatCurrency, formatMonth, percent, titleCase } from "@/utils/format";
import { dateFromKey, useCurrentDateKey } from "@/utils/use-current-date";

const chartColors = ["#2d785d", "#e39a4d", "#5e8a9c", "#c76c5b", "#83a65b", "#9b8c73", "#4f7065"];

export default function DashboardView() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [profile, setProfile] = useState<FinancialProfile | null>(null);
  const [health, setHealth] = useState<FinancialHealth | null>(null);
  const [investmentPlan, setInvestmentPlan] = useState<InvestmentPlan | null>(null);
  const [monthlyPlan, setMonthlyPlan] = useState<MonthlyActionPlan | null>(null);
  const [insights, setInsights] = useState<FinancialInsights | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const currentDateKey = useCurrentDateKey();

  useEffect(() => {
    let cancelled = false;
    const now = dateFromKey(currentDateKey);
    Promise.all([
      financeApi.dashboard(),
      financeApi.budgetStatus(now.getMonth() + 1, now.getFullYear()),
      financeApi.profile(),
      financeApi.user(),
      financeApi.financialHealth(),
      financeApi.investmentPlan(),
      financeApi.monthlyActionPlan(),
      financeApi.financialInsights(),
    ])
      .then(([dashboardData, budgetData, profileData, userData, healthData, investmentData, actionPlanData, insightsData]) => {
        if (cancelled) return;
        setDashboard(dashboardData);
        setBudgets(budgetData);
        setProfile(profileData);
        setUser(userData);
        setHealth(healthData);
        setInvestmentPlan(investmentData);
        setMonthlyPlan(actionPlanData);
        setInsights(insightsData);
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [currentDateKey, retry]);

  if (loading) return <div className="dashboard-loading"><LoadingSkeleton rows={6} /></div>;
  if (error) return <ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} />;
  if (!dashboard || !profile || !user || !health || !investmentPlan || !monthlyPlan || !insights) {
    return <EmptyState title="Dashboard data is unavailable" message="Your financial profile or dashboard data could not be found." />;
  }

  const score = dashboard.financial_health_score;
  const scoreLabel = score >= 80 ? "Strong" : score >= 60 ? "Steady" : "Building";
  const emergencyTarget = Number(dashboard.emergency_fund.target_amount);
  const coveredMonths = emergencyTarget > 0
    ? Math.min(profile.emergency_fund_target_months, Number(dashboard.emergency_fund.current_amount) / emergencyTarget * profile.emergency_fund_target_months)
    : profile.emergency_fund_target_months;
  const budgetTotal = budgets.reduce((sum, budget) => sum + Number(budget.monthly_limit), 0);
  const budgetSpent = budgets.reduce((sum, budget) => sum + Number(budget.amount_spent), 0);
  const savingsRate = Number(dashboard.savings_rate);
  const emergencyCoverage = Number(dashboard.emergency_fund.coverage_percentage);
  const monthlyAction = monthlyPlan.allocations.find(
    (line) => Number(line.amount) > 0 && !["EXISTING_COMMITMENTS", "SAFETY_BUFFER"].includes(line.reason_code),
  ) ?? monthlyPlan.allocations.find((line) => Number(line.amount) > 0);
  const hour = currentDateKey ? dateFromKey(currentDateKey).getHours() : 12;
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="dashboard-page">
      <section className="dashboard-welcome">
        <div>
          <p className="eyebrow">Your money, in focus</p>
          <h2>{greeting}, {user.name.split(" ")[0]}</h2>
          <p>Here&apos;s your financial overview.</p>
        </div>
        <div className="welcome-date"><span className="live-dot" /> Your personal financial overview</div>
      </section>

      {dashboard.expense_by_category.length === 0 && <section className="panel section-block"><h3>Make FinPilot yours</h3><p>Your dashboard uses only your records. Start with income or an expense.</p><div className="planner-bottom-actions"><Link className="button button-primary" href="/transactions">Add your first transaction</Link>{budgets.length === 0 && <Link className="button button-light" href="/budget">Create your first budget</Link>}{dashboard.goals.length === 0 && <Link className="button button-light" href="/goals">Create your first financial goal</Link>}</div></section>}

      <section className="metric-grid" aria-label="Monthly financial summary">
        <MetricCard label="Monthly income" value={dashboard.monthly_income} detail="Salary and other income" icon={<Banknote size={17} />} accent="green" />
        <MetricCard label="Monthly expenses" value={dashboard.monthly_expenses_excluding_debt} detail="Essential & discretionary · debt separate" icon={<Wallet size={17} />} accent="coral" help="Recorded essential and discretionary expense transactions. Monthly debt payments are separate and subtracted when calculating monthly surplus." />
        <MetricCard label="Monthly savings" value={dashboard.monthly_savings} detail={`${savingsRate.toFixed(1)}% of income`} icon={<PiggyBank size={17} />} accent="amber" help="Savings transactions actually recorded this month; not estimated leftover cash." />
        <MetricCard label="Monthly surplus" value={dashboard.monthly_surplus} detail="After expenses and debt" icon={<CircleDollarSign size={17} />} accent="blue" help="Income minus essential expenses, discretionary expenses, and debt obligations; calculated before savings transfers." />
        <MetricCard label="Savings rate" value={`${savingsRate.toFixed(1)}%`} detail="From recorded savings" icon={<ChartNoAxesCombined size={17} />} accent="blue" />
        <MetricCard label="Investable surplus" value={investmentPlan.investable_surplus} detail="After priorities and reserves" icon={<CircleDollarSign size={17} />} accent="ink" help="Potential longer-term allocation after recorded savings, existing goal commitments, safety buffer, debt and emergency-fund priorities, near-term goals, and an unallocated reserve." />
        <MetricCard label="Financial health" value={`${score} / 100`} detail={`${scoreLabel} financial position`} icon={<HeartPulse size={17} />} accent="green" progress={score} />
      </section>

      <section className="overview-grid section-block">
        <div className="panel health-panel">
          <div className="section-heading">
            <div><h3>Financial health</h3><p>A deterministic view of this month&apos;s numbers</p></div>
            <span className={`health-badge health-${scoreLabel.toLowerCase()}`}><span />{scoreLabel}</span>
          </div>
          <div className="health-score-row">
            <div className="health-score">{score}<span>/100</span></div>
            <div className="health-score-caption">Your score is calculated from income, expenses, savings, debt, and emergency fund coverage.</div>
          </div>
          <ProgressBar value={score} tone={score >= 75 ? "green" : score >= 50 ? "amber" : "coral"} />
          <div className="health-factors">
            {health.components.map((component) => <div key={component.name}><span>{component.name}</span><strong>{component.points}/{component.maximum_points}</strong><ProgressBar value={component.maximum_points ? component.points / component.maximum_points * 100 : 0} tone={component.status === "REVIEW" || component.status === "BUILDING" ? "amber" : "green"} /></div>)}
          </div>
          <div className="health-insights">
            <div><strong>What&apos;s helping your score</strong>{health.strengths.map((item) => <p key={item}>{item}</p>)}</div>
            <div><strong>What&apos;s hurting your score</strong>{health.areas_to_improve.length ? health.areas_to_improve.map((item) => <p key={item}>{item}</p>) : <p>No score component is currently below half of its available points.</p>}</div>
          </div>
          <p className="health-goal-context">{health.goal_progress_context}</p>
          <details className="health-action-details"><summary>How can I improve my score?</summary>{health.deterministic_actions.map((action) => <p key={action}>{action}</p>)}</details>
        </div>

        <div className="panel emergency-panel">
          <div className="section-heading"><div><h3>Emergency fund</h3><p>Accessible savings for unexpected costs</p></div><span className="emergency-icon"><ShieldCheck size={18} /></span></div>
          <div className="emergency-amounts"><strong>{formatCurrency(dashboard.emergency_fund.current_amount)}</strong><span>of {formatCurrency(dashboard.emergency_fund.target_amount)}</span></div>
          <div className="emergency-percent"><strong>{emergencyCoverage.toFixed(0)}%</strong><span>of target</span></div>
          <ProgressBar value={emergencyCoverage} />
          <div className="emergency-foot"><span>{coveredMonths.toFixed(1)} months covered</span><span>Target: {profile.emergency_fund_target_months} months</span></div>
          <div className="emergency-remaining"><span>Remaining to target</span><strong>{formatCurrency(dashboard.emergency_fund.remaining_amount)}</strong></div>
          <Link className="section-link" href="/goals">View emergency goal <ArrowRight size={14} /></Link>
        </div>
      </section>

      <section className="priority-action-strip section-block" aria-label="This month's financial priority and action">
        <div><span className="priority-strip-label">Top financial priority</span><strong>{investmentPlan.financial_priorities[0]?.purpose ?? "Maintain your plan"}</strong><p>{investmentPlan.financial_priorities[0]?.action ?? "Review your financial priorities."}</p></div>
        <div><span className="priority-strip-label">Monthly action</span><strong>{monthlyAction?.purpose ?? "Keep current commitments on track"}</strong><p>{monthlyAction?.reason_code.replaceAll("_", " ") ?? "No additional allocation is available this month."}</p></div>
      </section>

      <details className="panel section-block why-details"><summary>Full monthly action plan</summary><p>Income: {formatCurrency(monthlyPlan.monthly_income)}. Expenses: {formatCurrency(monthlyPlan.essential_expenses)} essential + {formatCurrency(monthlyPlan.discretionary_expenses)} discretionary. Debt: {formatCurrency(monthlyPlan.debt_obligations)}.</p><div className="table-wrap"><table className="data-table"><thead><tr><th>Monthly action or reserve</th><th>Amount</th></tr></thead><tbody>{monthlyPlan.allocations.map((line, index) => <tr key={`${line.reason_code}-${index}`}><td>{line.purpose}</td><td>{formatCurrency(line.amount)}</td></tr>)}</tbody><tfoot><tr><th>Allocation total</th><td>{formatCurrency(monthlyPlan.allocation_total)}</td></tr></tfoot></table></div>{monthlyPlan.warnings.map((warning) => <p key={warning}>{warning}</p>)}</details>

      <section className="chart-grid section-block" aria-label="Financial charts">
        <ChartPanel title="Expense breakdown" subtitle="By recorded category">
          {dashboard.expense_by_category.length === 0 ? <EmptyState title="No expenses recorded" message="Expense categories will appear once transactions are recorded." /> : <>
              <div className="donut-wrap"><ResponsiveContainer width="100%" height={190}><PieChart><Pie data={dashboard.expense_by_category} dataKey="amount" nameKey="category" innerRadius={57} outerRadius={82} paddingAngle={3} stroke="none">{dashboard.expense_by_category.map((entry, index) => <Cell key={`${entry.category}-${index}`} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip content={<MoneyTooltip />} /></PieChart></ResponsiveContainer><div className="donut-total"><strong>{formatCompact(dashboard.monthly_expenses_excluding_debt)}</strong><span>expenses · debt separate</span></div></div>
            <div className="chart-legend">{dashboard.expense_by_category.slice(0, 5).map((entry, index) => <span className="legend-item" key={`${entry.category}-${index}`}><i className="legend-dot" style={{ background: chartColors[index % chartColors.length] }} />{entry.category}</span>)}</div>
          </>}
        </ChartPanel>

        <ChartPanel title="Income vs expenses" subtitle="Monthly comparison · last 6 months">
          {dashboard.income_vs_expenses.length === 0 ? <EmptyState title="No monthly history" message="Income and expense history will show here." /> : <ResponsiveContainer width="100%" height={230}><BarChart data={dashboard.income_vs_expenses} margin={{ top: 8, right: 3, left: -18, bottom: 0 }} barGap={5}><CartesianGrid vertical={false} stroke="#edf0ed" /><XAxis dataKey="month" tickFormatter={formatMonth} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 10 }} /><YAxis tickFormatter={shortCurrency} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><Tooltip content={<MoneyTooltip />} /><Bar dataKey="income" name="Income" fill="#2d785d" radius={[4, 4, 0, 0]} maxBarSize={24} /><Bar dataKey="expenses" name="Expenses" fill="#e5a35f" radius={[4, 4, 0, 0]} maxBarSize={24} /></BarChart></ResponsiveContainer>}
        </ChartPanel>

        <ChartPanel title="Savings trend" subtitle="Recorded monthly savings">
          {dashboard.monthly_savings_trend.length === 0 ? <EmptyState title="No savings history" message="Savings transactions will appear here." /> : <ResponsiveContainer width="100%" height={230}><LineChart data={dashboard.monthly_savings_trend} margin={{ top: 12, right: 8, left: -17, bottom: 0 }}><CartesianGrid vertical={false} stroke="#edf0ed" /><XAxis dataKey="month" tickFormatter={formatMonth} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 10 }} /><YAxis tickFormatter={shortCurrency} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><Tooltip content={<MoneyTooltip />} /><Line type="monotone" dataKey="savings" name="Savings" stroke="#438b68" strokeWidth={2.5} dot={{ r: 3, fill: "#438b68", stroke: "#fff", strokeWidth: 2 }} activeDot={{ r: 5 }} /></LineChart></ResponsiveContainer>}
        </ChartPanel>

        <ChartPanel title="Top spending categories" subtitle="Highest spend this month">
          {dashboard.top_spending_categories.length === 0 ? <EmptyState title="Nothing to rank yet" message="Category rankings will appear as expenses are recorded." /> : <ResponsiveContainer width="100%" height={230}><BarChart data={dashboard.top_spending_categories} layout="vertical" margin={{ top: 4, right: 12, left: 2, bottom: 0 }}><CartesianGrid horizontal={false} stroke="#edf0ed" /><XAxis type="number" tickFormatter={shortCurrency} tickLine={false} axisLine={false} tick={{ fill: "#89948d", fontSize: 9 }} /><YAxis type="category" dataKey="category" width={91} tickLine={false} axisLine={false} tick={{ fill: "#68756d", fontSize: 10 }} /><Tooltip content={<MoneyTooltip />} /><Bar dataKey="amount" name="Spent" fill="#5e8a9c" radius={[0, 4, 4, 0]} maxBarSize={17} /></BarChart></ResponsiveContainer>}
        </ChartPanel>
      </section>

      <section className="dashboard-lower-grid section-block">
        <div className="panel budget-overview">
          <div className="section-heading"><div><h3>Budget vs actual</h3><p>{budgets.length ? `${formatCurrency(budgetSpent)} spent of ${formatCurrency(budgetTotal)} planned` : "Monthly category limits"}</p></div><Link className="section-link" href="/budget">Manage budgets <ArrowRight size={14} /></Link></div>
          {budgets.length === 0 ? <EmptyState title="No budgets for this month" message="Create a category budget to track this month's spending." /> : <div className="budget-mini-list">{budgets.slice(0, 5).map((budget) => <BudgetMini key={budget.budget_id} budget={budget} />)}</div>}
        </div>

        <div className="panel goals-overview">
          <div className="section-heading"><div><h3>Your goals</h3><p>Progress from your saved goal plans</p></div><Link className="section-link" href="/goals">View all goals <ArrowRight size={14} /></Link></div>
          {dashboard.goals.length === 0 ? <EmptyState title="No goals set yet" message="Add a savings goal to make your next milestone visible." /> : <div className="goal-mini-list">{dashboard.goals.slice(0, 3).map((goal) => <div className="goal-mini" key={goal.id}><div className="goal-mini-top"><div><strong>{goal.name}</strong><span>{titleCase(goal.goal_type)}</span></div><b>{Number(goal.progress_percentage).toFixed(0)}%</b></div><ProgressBar value={percent(goal.progress_percentage)} tone={goal.goal_type === "EMERGENCY_FUND" ? "green" : "ink"} /><div className="goal-meta"><span>{formatCurrency(goal.current_amount)} saved</span><span>{formatCurrency(goal.target_amount)} target</span></div></div>)}</div>}
        </div>
      </section>

      <section className="section-block dashboard-insights">
        <div className="section-heading"><div><p className="eyebrow">From recorded financial data</p><h3>FinPilot Insights</h3></div><span className="status-pill status-neutral">Deterministic · No AI</span></div>
        <p className="simulator-footnote">{insights.coverage_note}</p>
        {insights.insights.length === 0 ? <div className="insight-placeholder"><span className="insight-icon"><ChartNoAxesCombined size={17} /></span><div><strong>No insights for this period</strong><p>Insights appear when the recorded data meets a deterministic comparison rule.</p></div></div> : <div className="deterministic-insight-list">{insights.insights.slice(0, 3).map((item) => <article className="deterministic-insight" key={`${item.reason_code}-${item.metric}`}><span className={`insight-severity insight-${item.severity.toLowerCase()}`} /><div><span>{titleCase(item.type)} · {item.reason_code.replaceAll("_", " ")}</span><strong>{item.title}</strong><p>{item.message}</p></div></article>)}</div>}
      </section>

      <section className="section-block afford-placeholder">
        <div><p className="eyebrow">Compare before you commit</p><h3>Can I afford this?</h3><p>See how a cash purchase or EMI may affect emergency reserves, monthly surplus, and goals.</p></div>
        <Link className="button button-light" href="/affordability">Analyze a purchase <ArrowRight size={14} /></Link>
      </section>

      <div className="dashboard-invest-link"><span>Want a clearer view of what could be allocated?</span><Link className="button button-primary" href="/investments">View investable surplus <ArrowRight size={15} /></Link></div>
    </div>
  );
}

function MetricCard({ label, value, detail, icon, accent, progress, help }: { label: string; value: string | number; detail: string; icon: React.ReactNode; accent: string; progress?: number; help?: string }) {
  const formatted = typeof value === "string" && (value.includes("/") || value.endsWith("%")) ? value : formatCurrency(value);
  return <article className="metric-card"><div className="metric-card-top"><span className="metric-label">{label}{help && <button type="button" className="metric-help" title={help} aria-label={`${label}: ${help}`}><Info size={12} /></button>}</span><span className={`metric-icon metric-${accent}`}>{icon}</span></div><strong className="metric-value">{formatted}</strong><div className="metric-detail">{progress !== undefined ? <ProgressBar value={progress} tone={progress >= 75 ? "green" : "amber"} /> : <span className="metric-detail-dot" />}{detail}</div></article>;
}

function ChartPanel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <article className="panel chart-panel"><div className="section-heading"><div><h3>{title}</h3><p>{subtitle}</p></div></div>{children}</article>;
}

function BudgetMini({ budget }: { budget: BudgetStatus }) {
  const tone = budget.status === "OVER_BUDGET" ? "coral" : budget.status === "WARNING" ? "amber" : "green";
  return <div className="budget-mini"><div className="budget-mini-head"><strong>{budget.category}</strong><span className={`status-pill status-${budget.status.toLowerCase().replaceAll("_", "-")}`}>{titleCase(budget.status)}</span></div><div className="budget-mini-values"><span>{formatCurrency(budget.amount_spent)} spent</span><span>{formatCurrency(budget.monthly_limit)} limit</span></div><ProgressBar value={percent(budget.percentage_used)} tone={tone} /></div>;
}

function MoneyTooltip({ active, payload, label }: { active?: boolean; payload?: { name?: string; value?: number | string; color?: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label ? formatMonth(label) : payload[0].name}</strong>{payload.map((entry) => <div key={entry.name} style={{ color: entry.color }}>{entry.name}: {formatCurrency(entry.value ?? 0)}</div>)}</div>;
}

function formatCompact(value: string | number): string {
  const amount = Number(value);
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  return formatCurrency(amount);
}

function shortCurrency(value: number): string {
  if (value >= 100000) return `₹${(value / 100000).toFixed(0)}L`;
  if (value >= 1000) return `₹${(value / 1000).toFixed(0)}k`;
  return `₹${value}`;
}