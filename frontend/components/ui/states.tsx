import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-label="Loading" role="status" className="skeleton-stack">
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-line" key={index} />
      ))}
      <span className="sr-only"><LoaderCircle className="h-4 w-4 animate-spin" /> Loading data</span>
    </div>
  );
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <div className="empty-state">
      <span className="state-icon"><Inbox size={18} aria-hidden="true" /></span>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div><strong>Something went wrong</strong><p>{message}</p></div>
      {onRetry && <button className="button button-light button-small" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function ProgressBar({ value, tone = "green" }: { value: number; tone?: "green" | "amber" | "coral" | "ink" }) {
  const width = Math.max(0, Math.min(100, value));
  return (
    <div className={`progress-track progress-${tone}`} role="progressbar" aria-valuenow={Math.round(width)} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${width}%` }} />
    </div>
  );
}