import type { Money } from "@/types/api";

const currencyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export function formatCurrency(value: Money): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? currencyFormatter.format(amount) : "--";
}

export function formatCompactCurrency(value: Money): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "--";
  if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(1)}Cr`;
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  return formatCurrency(amount);
}

export function formatMonth(value: string): string {
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  return new Intl.DateTimeFormat("en-IN", { month: "short" }).format(parsed);
}

export function formatDate(value: string | null): string {
  if (!value) return "No target date";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00`));
}

export function percent(value: Money): number {
  const amount = Number(value);
  return Number.isFinite(amount) ? Math.max(0, Math.min(100, amount)) : 0;
}

export function titleCase(value: string): string {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}