"use client";


import { BellRing } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/ui/states";
import { apiRequest } from "@/services/api";
interface Alert { id: number; title: string; message: string; severity: string; is_read: boolean }
export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { let cancelled = false; apiRequest<Alert[]>("/api/me/alerts").then((items) => { if (!cancelled) setAlerts(items); }).catch((reason: Error) => { if (!cancelled) setError(reason.message); }); return () => { cancelled = true; }; }, []);
  return <div><div className="page-heading"><div><p className="eyebrow">Stay informed</p><h2>Alerts</h2><p>Updates connected to your financial activity.</p></div></div><section className="panel alerts-panel"><div className="section-heading"><h3>Recent alerts</h3><BellRing size={18} /></div>{error ? <ErrorState message={error} /> : alerts === null ? <LoadingSkeleton /> : !alerts.length ? <EmptyState title="No alerts yet" message="Only alerts belonging to your account appear here." /> : alerts.map((alert) => <article className="section-block" key={alert.id}><strong>{alert.title}</strong><span className="status-pill status-neutral">{alert.severity}</span><p>{alert.message}</p></article>)}</section></div>;
}
