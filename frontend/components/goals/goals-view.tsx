"use client";

import { Check, Pencil, Plus, Target, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, LoadingSkeleton, ProgressBar } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { Goal, GoalInput, GoalKind } from "@/types/api";
import { formatCurrency, formatDate, percent, titleCase } from "@/utils/format";

const newGoal = (): GoalInput => ({  name: "", goal_type: "OTHER", target_amount: "", current_amount: "0", target_date: null, monthly_contribution: "0", priority: 3 });

export default function GoalsView() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [form, setForm] = useState<GoalInput>(newGoal);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Goal | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    financeApi.goals().then((data) => { if (!cancelled) setGoals(data); }).catch((reason: Error) => { if (!cancelled) setError(reason.message); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refresh, retry]);

  function create() {
    setEditing(null);
    setForm(newGoal());
    setFormOpen(true);
  }

  function edit(goal: Goal) {
    setEditing(goal);
    setForm({ name: goal.name, goal_type: goal.goal_type, target_amount: String(goal.target_amount), current_amount: String(goal.current_amount), target_date: goal.target_date, monthly_contribution: String(goal.monthly_contribution), priority: goal.priority });
    setFormOpen(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (editing) {
        const payload = { ...form } as Partial<GoalInput>;
        if (!payload.target_date) delete payload.target_date;
        delete payload.user_id;
        await financeApi.updateGoal(editing.id, payload);
      } else {
        await financeApi.createGoal({ ...form, target_date: form.target_date || null });
      }
      setFormOpen(false);
      setMessage(editing ? "Goal updated." : "Goal created.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this goal.");
    } finally { setSaving(false); }
  }

  async function remove() {
    if (!deleting) return;
    setSaving(true);
    try {
      await financeApi.deleteGoal(deleting.id);
      setDeleting(null);
      setMessage("Goal deleted.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete this goal.");
      setDeleting(null);
    } finally { setSaving(false); }
  }

  if (loading) return <LoadingSkeleton rows={4} />;
  if (error && !goals.length) return <ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} />;

  return <div>
    <div className="page-heading"><div><p className="eyebrow">Small steps, clear milestones</p><h2>Goals</h2><p>Track what you&apos;re building toward using your saved goal plans.</p></div><button className="button button-primary" onClick={create}><Plus size={16} /> Create goal</button></div>
    {message && <div className="success-banner" role="status"><Check size={15} />{message}<button className="icon-button icon-button-small" aria-label="Dismiss message" onClick={() => setMessage("")}><X size={14} /></button></div>}
    {error && <div className="section-block"><ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} /></div>}
    {goals.length === 0 ? <div className="panel"><EmptyState title="No goals saved yet" message="Create a goal to give your next financial milestone a target and timeline." /></div> : <section className="goal-card-grid">{goals.map((goal) => <GoalCard key={goal.id} goal={goal} onEdit={() => edit(goal)} onDelete={() => setDeleting(goal)} />)}</section>}
    <div className="inline-note section-block"><strong>Goal planning</strong><br />Required monthly contributions and progress percentages are calculated by the backend from each goal&apos;s stored values and target date.</div>

    {formOpen && <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="goal-form-title"><div className="modal-header"><div><h3 id="goal-form-title">{editing ? "Edit goal" : "Create a goal"}</h3><p>Set the target, timeline, and monthly amount.</p></div><button className="icon-button" onClick={() => setFormOpen(false)} aria-label="Close goal form"><X size={17} /></button></div><form className="form-grid" onSubmit={submit}>
      <div className="field form-wide"><label htmlFor="goal-name">Goal name</label><input id="goal-name" className="input" required maxLength={120} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></div>
      <div className="field"><label htmlFor="goal-type">Goal type</label><select id="goal-type" className="select" value={form.goal_type} onChange={(event) => setForm({ ...form, goal_type: event.target.value as GoalKind })}><option value="EMERGENCY_FUND">Emergency fund</option><option value="TRAVEL">Travel</option><option value="LONG_TERM_WEALTH">Long-term wealth</option><option value="OTHER">Other</option></select></div>
      <div className="field"><label htmlFor="goal-priority">Priority</label><select id="goal-priority" className="select" value={form.priority} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })}><option value="1">1 · Highest</option><option value="2">2</option><option value="3">3 · Standard</option><option value="4">4</option><option value="5">5 · Lowest</option></select></div>
      <div className="field"><label htmlFor="goal-target">Target amount (INR)</label><input id="goal-target" className="input" type="number" min="0.01" step="0.01" required value={form.target_amount} onChange={(event) => setForm({ ...form, target_amount: event.target.value })} /></div>
      <div className="field"><label htmlFor="goal-current">Current amount (INR)</label><input id="goal-current" className="input" type="number" min="0" step="0.01" required value={form.current_amount} onChange={(event) => setForm({ ...form, current_amount: event.target.value })} /></div>
      <div className="field"><label htmlFor="goal-date">Target date</label><input id="goal-date" className="input" type="date" min={new Date().toISOString().slice(0, 10)} value={form.target_date ?? ""} onChange={(event) => setForm({ ...form, target_date: event.target.value || null })} /></div>
      <div className="field"><label htmlFor="goal-monthly">Monthly contribution (INR)</label><input id="goal-monthly" className="input" type="number" min="0" step="0.01" required value={form.monthly_contribution} onChange={(event) => setForm({ ...form, monthly_contribution: event.target.value })} /></div>
      <div className="form-actions"><button type="button" className="button button-light" onClick={() => setFormOpen(false)}>Cancel</button><button className="button button-primary" disabled={saving}>{saving ? "Saving…" : editing ? "Save changes" : "Create goal"}</button></div>
    </form></section></div>}
    {deleting && <ConfirmDialog title="Delete this goal?" message={`${deleting.name} · ${formatCurrency(deleting.target_amount)} target.`} busy={saving} onCancel={() => setDeleting(null)} onConfirm={remove} />}
  </div>;
}

function GoalCard({ goal, onEdit, onDelete }: { goal: Goal; onEdit: () => void; onDelete: () => void }) {
  const progress = percent(goal.progress_percentage);
  return <article className="panel goal-card"><div className="goal-card-title"><span className="goal-icon"><Target size={17} /></span><div><h3>{goal.name}</h3><span>{titleCase(goal.goal_type)}</span></div><span className="priority-mark">P{goal.priority}</span></div><div className="goal-card-progress"><div><strong>{formatCurrency(goal.current_amount)}</strong><span>of {formatCurrency(goal.target_amount)}</span></div><b>{Number(goal.progress_percentage).toFixed(1)}%</b></div><ProgressBar value={progress} tone={goal.goal_type === "EMERGENCY_FUND" ? "green" : "ink"} /><div className="goal-card-stats"><div><span>Remaining</span><strong>{formatCurrency(goal.remaining_amount)}</strong></div><div><span>Required monthly</span><strong>{formatCurrency(goal.required_monthly_contribution)}</strong></div><div><span>Target date</span><strong>{formatDate(goal.target_date)}</strong></div></div><div className="goal-card-actions"><button className="button button-light button-small" onClick={onEdit}><Pencil size={13} /> Edit</button><button className="icon-button icon-button-small danger-icon" onClick={onDelete} aria-label={`Delete ${goal.name}`}><Trash2 size={14} /></button></div></article>;
}