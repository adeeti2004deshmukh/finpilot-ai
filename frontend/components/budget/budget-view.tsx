"use client";

import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, LoadingSkeleton, ProgressBar } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { BudgetInput, BudgetStatus, Category, DashboardData } from "@/types/api";
import { formatCurrency, percent, titleCase } from "@/utils/format";
import { dateFromKey, useCurrentDateKey } from "@/utils/use-current-date";

interface BudgetForm {
  category_id: number;
  monthly_limit: string;
}

export default function BudgetView() {
  const currentDateKey = useCurrentDateKey();
  const now = dateFromKey(currentDateKey);
  const currentMonth = now.getMonth() + 1;
  const currentYear = now.getFullYear();
  const [statusRows, setStatusRows] = useState<BudgetStatus[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<BudgetStatus | null>(null);
  const [form, setForm] = useState<BudgetForm>({ category_id: 0, monthly_limit: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<BudgetStatus | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      financeApi.budgetStatus(currentMonth, currentYear),
      financeApi.categories("EXPENSE"),
      financeApi.dashboard(),
    ])
      .then(([statusData, categoryData, dashboardData]) => {
        if (cancelled) return;
        setStatusRows(statusData);
        setCategories(categoryData);
        setDashboard(dashboardData);
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [currentMonth, currentYear, refresh, retry]);

  function openCreate() {
    setEditing(null);
    const alreadyBudgeted = new Set(statusRows.map((row) => row.category_id));
    setForm({ category_id: categories.find((item) => !alreadyBudgeted.has(item.id))?.id ?? categories[0]?.id ?? 0, monthly_limit: "" });
    setFormOpen(true);
  }

  function openEdit(row: BudgetStatus) {
    setEditing(row);
    setForm({ category_id: row.category_id, monthly_limit: String(row.monthly_limit) });
    setFormOpen(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload: BudgetInput = {  category_id: Number(form.category_id), monthly_limit: form.monthly_limit, month: now.getMonth() + 1, year: now.getFullYear() };
      if (editing) await financeApi.updateBudget(editing.budget_id, { category_id: payload.category_id, monthly_limit: payload.monthly_limit });
      else await financeApi.createBudget(payload);
      setFormOpen(false);
      setMessage(editing ? "Budget updated." : "Budget created.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this budget.");
    } finally {
      setSaving(false);
    }
  }

  async function removeBudget() {
    if (!deleting) return;
    setSaving(true);
    try {
      await financeApi.deleteBudget(deleting.budget_id);
      setDeleting(null);
      setMessage("Budget deleted.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete this budget.");
      setDeleting(null);
    } finally { setSaving(false); }
  }

  if (loading) return <LoadingSkeleton rows={5} />;
  if (error && !statusRows.length) return <ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} />;

  const totalBudget = statusRows.reduce((sum, row) => sum + Number(row.monthly_limit), 0);
  const totalSpent = statusRows.reduce((sum, row) => sum + Number(row.amount_spent), 0);
  const remaining = totalBudget - totalSpent;
  const unbudgetedCategories = categories.filter((category) => !statusRows.some((row) => row.category_id === category.id));

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Plan the month</p><h2>Budget</h2><p>Compare category limits with spending recorded for {new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric" }).format(now)}.</p></div><button className="button button-primary" onClick={openCreate} disabled={!unbudgetedCategories.length}><Plus size={16} /> Add budget</button></div>
    {message && <div className="success-banner" role="status"><Check size={15} />{message}<button className="icon-button icon-button-small" aria-label="Dismiss message" onClick={() => setMessage("")}><X size={14} /></button></div>}
    {error && <div className="section-block"><ErrorState message={error} onRetry={() => { setError(""); setRetry((value) => value + 1); }} /></div>}
    <section className="budget-summary-grid">
      <SummaryBlock label="Monthly income" value={formatCurrency(dashboard?.monthly_income ?? 0)} note="From dashboard calculations" />
      <SummaryBlock label="Total budget" value={formatCurrency(totalBudget)} note={`${statusRows.length} category limits`} />
      <SummaryBlock label="Spent" value={formatCurrency(totalSpent)} note="Recorded expenses this month" />
      <SummaryBlock label="Remaining" value={formatCurrency(remaining)} note={remaining < 0 ? "Over the combined limits" : "Across active budgets"} tone={remaining < 0 ? "coral" : "green"} />
    </section>
    <div className="section-heading section-block"><div><h3>Category budgets</h3><p>Spending status is calculated from transaction data.</p></div><span className="status-pill status-neutral">{statusRows.length} active this month</span></div>
    {statusRows.length === 0 ? <div className="panel"><EmptyState title="No budgets set for this month" message="Add a category limit to compare real transactions against a monthly plan." /></div> : <section className="budget-card-grid">{statusRows.map((row) => <BudgetCard key={row.budget_id} row={row} onEdit={() => openEdit(row)} onDelete={() => setDeleting(row)} />)}</section>}
    {formOpen && <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="budget-form-title"><div className="modal-header"><div><h3 id="budget-form-title">{editing ? "Edit budget" : "Create budget"}</h3><p>Applies to {now.toLocaleDateString("en-IN", { month: "long", year: "numeric" })}.</p></div><button className="icon-button" aria-label="Close budget form" onClick={() => setFormOpen(false)}><X size={17} /></button></div><form className="form-grid" onSubmit={submit}><div className="field form-wide"><label htmlFor="budget-category">Category</label><select id="budget-category" className="select" required value={form.category_id || ""} onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })} disabled={Boolean(editing)}><option value="" disabled>Select a category</option>{categories.filter((item) => editing?.category_id === item.id || !statusRows.some((row) => row.category_id === item.id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><div className="field form-wide"><label htmlFor="budget-limit">Monthly limit (INR)</label><input id="budget-limit" className="input" type="number" min="0" step="0.01" required value={form.monthly_limit} onChange={(event) => setForm({ ...form, monthly_limit: event.target.value })} /></div><div className="form-actions"><button type="button" className="button button-light" onClick={() => setFormOpen(false)}>Cancel</button><button className="button button-primary" disabled={saving || !form.category_id}>{saving ? "Saving…" : editing ? "Save changes" : "Create budget"}</button></div></form></section></div>}
    {deleting && <ConfirmDialog title="Delete this budget?" message={`${deleting.category} · ${formatCurrency(deleting.monthly_limit)} monthly limit.`} busy={saving} onCancel={() => setDeleting(null)} onConfirm={removeBudget} />}
  </div>;
}

function SummaryBlock({ label, value, note, tone = "ink" }: { label: string; value: string; note: string; tone?: string }) {
  return <article className="panel summary-block"><span>{label}</span><strong className={`summary-value summary-${tone}`}>{value}</strong><small>{note}</small></article>;
}

function BudgetCard({ row, onEdit, onDelete }: { row: BudgetStatus; onEdit: () => void; onDelete: () => void }) {
  const tone = row.status === "OVER_BUDGET" ? "coral" : row.status === "WARNING" ? "amber" : "green";
  return <article className="panel budget-card"><div className="budget-card-title"><div><p className="eyebrow">Monthly category</p><h3>{row.category}</h3></div><span className={`status-pill status-${row.status.toLowerCase().replaceAll("_", "-")}`}>{titleCase(row.status)}</span></div><div className="budget-card-amount"><strong>{formatCurrency(row.amount_spent)}</strong><span>spent of {formatCurrency(row.monthly_limit)}</span></div><ProgressBar value={percent(row.percentage_used)} tone={tone} /><div className="budget-card-meta"><span>{Number(row.percentage_used).toFixed(1)}% used</span><span className={Number(row.remaining_budget) < 0 ? "text-negative" : ""}>{formatCurrency(row.remaining_budget)} remaining</span></div><div className="budget-card-actions"><button className="button button-light button-small" onClick={onEdit}><Pencil size={13} /> Edit</button><button className="icon-button icon-button-small danger-icon" onClick={onDelete} aria-label={`Delete ${row.category} budget`}><Trash2 size={14} /></button></div></article>;
}