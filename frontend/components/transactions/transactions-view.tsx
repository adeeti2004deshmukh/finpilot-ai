"use client";

import { Check, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { financeApi } from "@/services/finance";
import type { Category, Transaction, TransactionInput, TransactionKind, TransactionList } from "@/types/api";
import { formatCurrency, formatDate, titleCase } from "@/utils/format";

const today = new Date();
const blankForm = (): TransactionInput => ({
  
  date: today.toISOString().slice(0, 10),
  merchant: "",
  description: "",
  amount: "",
  transaction_type: "EXPENSE",
  category_id: null,
  notes: "",
});

export default function TransactionsView() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<TransactionList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(1);
  const [merchant, setMerchant] = useState("");
  const [month, setMonth] = useState("");
  const [category, setCategory] = useState("");
  const [transactionType, setTransactionType] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [form, setForm] = useState<TransactionInput>(blankForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<Transaction | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    financeApi.categories().then(setCategories).catch(() => setCategories([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ page: String(page), page_size: "50" });
    if (merchant.trim()) params.set("merchant", merchant.trim());
    if (month) {
      const [year, monthNumber] = month.split("-");
      params.set("year", year);
      params.set("month", monthNumber);
    }
    if (category) params.set("category", category);
    if (transactionType) params.set("transaction_type", transactionType);
    financeApi.transactions(params)
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, merchant, month, category, transactionType, refresh, retry]);

  function updateFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  function openCreate() {
    setEditing(null);
    setForm(blankForm());
    setDialogOpen(true);
  }

  function openEdit(transaction: Transaction) {
    setEditing(transaction);
    setForm({
      date: transaction.date,
      merchant: transaction.merchant,
      description: transaction.description,
      amount: String(transaction.amount),
      transaction_type: transaction.transaction_type,
      category_id: transaction.category_id,
      notes: transaction.notes ?? "",
    });
    setDialogOpen(true);
  }

  async function submitTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const payload = { ...form, category_id: form.category_id || null, notes: form.notes || null };
      if (editing) await financeApi.updateTransaction(editing.id, payload);
      else await financeApi.createTransaction(payload);
      setDialogOpen(false);
      setMessage(editing ? "Transaction updated." : "Transaction added.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this transaction.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteTransaction() {
    if (!deleting) return;
    setSaving(true);
    try {
      await financeApi.deleteTransaction(deleting.id);
      setDeleting(null);
      setMessage("Transaction deleted.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete this transaction.");
      setDeleting(null);
    } finally {
      setSaving(false);
    }
  }

  const categoryName = new Map(categories.map((item) => [item.id, item.name]));
  const filteredCategories = categories.filter((item) => item.type === form.transaction_type);
  const canGoNext = Boolean(result && page * result.page_size < result.total);

  return (
    <div>
      <div className="page-heading"><div><p className="eyebrow">Your money activity</p><h2>Transactions</h2><p>Review and organize the activity recorded for your account.</p></div><button className="button button-primary" onClick={openCreate}><Plus size={16} /> Add transaction</button></div>
      {message && <div className="success-banner" role="status"><Check size={15} />{message}<button className="icon-button icon-button-small" aria-label="Dismiss message" onClick={() => setMessage("")}><X size={14} /></button></div>}
      <section className="panel transaction-panel">
        <div className="filter-bar transaction-filters">
          <div className="field filter-grow"><label htmlFor="merchant-search">Search merchant</label><div className="input-with-icon"><Search size={15} /><input id="merchant-search" className="input" value={merchant} onChange={(event) => updateFilter(setMerchant, event.target.value)} placeholder="Search transactions" /></div></div>
          <div className="field"><label htmlFor="month-filter">Month</label><input id="month-filter" className="input" type="month" value={month} onChange={(event) => updateFilter(setMonth, event.target.value)} /></div>
          <div className="field"><label htmlFor="category-filter">Category</label><select id="category-filter" className="select" value={category} onChange={(event) => updateFilter(setCategory, event.target.value)}><option value="">All categories</option>{categories.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
          <div className="field"><label htmlFor="type-filter">Type</label><select id="type-filter" className="select" value={transactionType} onChange={(event) => updateFilter(setTransactionType, event.target.value)}><option value="">All types</option><option value="EXPENSE">Expense</option><option value="INCOME">Income</option><option value="SAVINGS">Savings</option></select></div>
        </div>
        {error ? <div className="section-block"><ErrorState message={error} onRetry={() => { setError(""); setLoading(true); setRetry((value) => value + 1); }} /></div> : loading ? <div className="section-block"><LoadingSkeleton rows={4} /></div> : !result?.items.length ? <EmptyState title="No transactions match these filters" message="Clear a filter or add an activity to see it here." /> : <>
          <div className="table-wrap section-block"><table className="data-table"><thead><tr><th>Date</th><th>Merchant</th><th>Description</th><th>Category</th><th>Type</th><th className="amount-cell">Amount</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{result.items.map((transaction) => <tr key={transaction.id}><td>{formatDate(transaction.date)}</td><td><strong className="table-primary-text">{transaction.merchant}</strong></td><td>{transaction.description}</td><td>{transaction.category_id ? categoryName.get(transaction.category_id) ?? "Category" : "Uncategorized"}</td><td><span className={`type-chip type-${transaction.transaction_type.toLowerCase()}`}>{titleCase(transaction.transaction_type)}</span></td><td className={`amount-cell ${transaction.transaction_type === "INCOME" ? "text-positive" : ""}`}>{transaction.transaction_type === "INCOME" ? "+" : "−"}{formatCurrency(transaction.amount)}</td><td><div className="table-actions"><button className="icon-button icon-button-small" onClick={() => openEdit(transaction)} aria-label={`Edit ${transaction.description}`}><Pencil size={14} /></button><button className="icon-button icon-button-small danger-icon" onClick={() => setDeleting(transaction)} aria-label={`Delete ${transaction.description}`}><Trash2 size={14} /></button></div></td></tr>)}</tbody></table></div>
          <div className="pagination"><span>{result.total} recorded transactions</span><div><button className="button button-light button-small" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(result.total / result.page_size))}</span><button className="button button-light button-small" disabled={!canGoNext} onClick={() => setPage((value) => value + 1)}>Next</button></div></div>
        </>}
      </section>

      {dialogOpen && <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="transaction-dialog-title"><div className="modal-header"><div><h3 id="transaction-dialog-title">{editing ? "Edit transaction" : "Add transaction"}</h3><p>Merchant matching and category assignment are handled by FinPilot.</p></div><button className="icon-button" onClick={() => setDialogOpen(false)} aria-label="Close transaction form"><X size={17} /></button></div><form className="form-grid" onSubmit={submitTransaction}>
        <div className="field"><label htmlFor="transaction-date">Date</label><input id="transaction-date" className="input" type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></div>
        <div className="field"><label htmlFor="transaction-type">Transaction type</label><select id="transaction-type" className="select" value={form.transaction_type} onChange={(event) => setForm({ ...form, transaction_type: event.target.value as TransactionKind, category_id: null })}><option value="EXPENSE">Expense</option><option value="INCOME">Income</option><option value="SAVINGS">Savings</option></select></div>
        <div className="field"><label htmlFor="transaction-merchant">Merchant</label><input id="transaction-merchant" onBlur={() => {
          if (!form.merchant.trim() || form.category_id !== null) return;
          const merchant = form.merchant;
          financeApi.suggestCategory(merchant, form.transaction_type).then(({ category_id }) => setForm((previous) => previous.merchant === merchant && previous.category_id === null ? { ...previous, category_id } : previous)).catch(() => {});
        }} className="input" required maxLength={160} value={form.merchant} onChange={(event) => setForm({ ...form, merchant: event.target.value })} /></div>
        <div className="field"><label htmlFor="transaction-amount">Amount (INR)</label><input id="transaction-amount" className="input" type="number" min="0.01" step="0.01" required value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} /></div>
        <div className="field form-wide"><label htmlFor="transaction-description">Description</label><input id="transaction-description" className="input" required maxLength={240} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></div>
        <div className="field"><label htmlFor="transaction-category">Category (optional)</label><select id="transaction-category" className="select" value={form.category_id ?? ""} onChange={(event) => setForm({ ...form, category_id: event.target.value ? Number(event.target.value) : null })}><option value="">Auto assign by merchant</option>{filteredCategories.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></div>
        <div className="field"><label htmlFor="transaction-notes">Notes</label><input id="transaction-notes" className="input" value={form.notes ?? ""} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></div>
        <div className="form-actions"><button type="button" className="button button-light" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</button><button type="submit" className="button button-primary" disabled={saving}>{saving ? "Saving…" : editing ? "Save changes" : "Add transaction"}</button></div>
      </form></section></div>}
      {deleting && <ConfirmDialog title="Delete this transaction?" message={`${deleting.merchant} · ${formatCurrency(deleting.amount)}. This cannot be undone.`} busy={saving} onCancel={() => setDeleting(null)} onConfirm={deleteTransaction} />}
    </div>
  );
}