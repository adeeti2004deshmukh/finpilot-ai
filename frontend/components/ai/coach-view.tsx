"use client";

import { ArrowUp, Bot, LoaderCircle, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { ApiError, apiRequest } from "@/services/api";

type Provider = "demo" | "openai";
type Reply = { provider: Provider; message: string; conversation_id: string; tools_used: string[]; suggested_followups: string[]; warnings: string[] };
type Message = { role: "user" | "assistant"; text: string; reply?: Reply };
const questions = ["Where am I overspending?", "Why is my financial health score low?", "Can I afford an ₹80,000 phone?", "How much should I save for my goals?", "What should I prioritize this month?", "What investment categories could fit my goals?"];
const toolLabels: Record<string, string> = {
  get_financial_summary: "Reviewed your financial summary", get_spending_analysis: "Analyzed your spending",
  get_category_spending: "Checked category spending", get_budget_status: "Checked your budgets",
  get_financial_health: "Reviewed your financial health", get_emergency_fund_status: "Checked your emergency fund",
  get_goals: "Checked your goals", analyze_goal: "Analyzed your goal", get_financial_priorities: "Reviewed your priorities",
  get_monthly_plan: "Reviewed your monthly plan", get_investment_plan: "Reviewed your investment plan",
  compare_investment_categories: "Compared educational categories", analyze_affordability: "Analyzed your purchase scenario",
  run_what_if_scenario: "Simulated your scenario", simulate_sip: "Calculated a SIP illustration",
  simulate_rd: "Calculated an RD illustration", simulate_fd: "Calculated an FD illustration",
  simulate_goal: "Explored an unsaved goal scenario", delay_purchase: "Compared waiting to purchase",
};

export function CoachView() {
  const { user } = useAuth();
  return <Chat key={user?.id ?? "signed-out"} />;
}

function Chat() {
  const [provider, setProvider] = useState<Provider>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    const abort = new AbortController();
    apiRequest<{ provider: Provider }>("/api/ai/config", { signal: abort.signal })
      .then((config) => { if (!abort.signal.aborted) setProvider(config.provider); })
      .catch(() => { /* Chat requests still surface backend configuration errors. */ });
    return () => abort.abort();
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages, loading]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || pending.current) return;
    pending.current = true;
    setLoading(true); setError(""); setDraft("");
    setMessages((current) => [...current, { role: "user", text: message }]);
    controller.current = new AbortController();
    try {
      const reply = await apiRequest<Reply>("/api/ai/chat", { method: "POST", body: JSON.stringify({ message, conversation_id: conversationId }), signal: controller.current.signal });
      setConversationId(reply.conversation_id);
      setProvider(reply.provider);
      setMessages((current) => [...current, { role: "assistant", text: reply.message, reply }]);
    } catch (cause) {
      if (controller.current?.signal.aborted) return;
      setError(cause instanceof Error ? cause.message : "AI Coach is temporarily unavailable.");
      setDraft(message);
      if (cause instanceof ApiError && cause.status === 404) setConversationId(undefined);
    } finally { pending.current = false; setLoading(false); }
  }

  const followups = messages.at(-1)?.reply?.suggested_followups ?? [];
  return <div>
    <div className="page-heading"><div><p className="eyebrow">Your finances, explained</p><h2>FinPilot AI Coach</h2><p>Explore your spending, goals and options using verified FinPilot calculations.</p></div><button className="button button-light button-small" disabled={loading} onClick={() => { setMessages([]); setConversationId(undefined); setError(""); setDraft(""); }}><Plus size={15} /> New conversation</button></div>
    <section className="coach-shell panel" aria-label="FinPilot AI conversation">
      <div className="coach-topline"><span className="coach-mark"><Bot size={19} /></span><div><strong>FinPilot AI Coach</strong><small>{provider === "demo" ? "Demo AI Coach" : "Education and planning"}</small></div><span className="coach-lock"><ShieldCheck size={14} /> Your signed-in workspace</span></div>
      <p className="coach-privacy">{provider === "demo" ? "Uses FinPilot's deterministic financial tools. No external AI API calls." : provider === "openai" ? "Your question and relevant financial summaries are sent to OpenAI to prepare an answer." : "Provider information is loading; the backend controls how your question is processed."} Never share passwords, PINs, CVVs or OTPs. Conversation context expires after inactivity.</p>
      <div className="coach-chat-log" role="log" aria-label="Conversation" aria-live="polite" aria-busy={loading}>
        {messages.length === 0 && <><div className="coach-welcome"><span className="coach-welcome-mark"><Sparkles size={18} /></span><h3>What would you like to understand?</h3><p>Start with a question. FinPilot checks your data and runs calculations before explaining the results.</p></div><div className="coach-question-list">{questions.map((question) => <button className="question-chip" key={question} disabled={loading} onClick={() => void send(question)}>{question}</button>)}</div></>}
        {messages.map((message, index) => <article className={`coach-message coach-message-${message.role}`} key={index}><strong>{message.role === "user" ? "You" : "FinPilot"}</strong><p>{message.text}</p>{!!message.reply?.tools_used.length && <div className="coach-tool-labels">{message.reply.tools_used.map((tool) => <span key={tool}><ShieldCheck size={12} />{toolLabels[tool] ?? "Reviewed your plan"}</span>)}</div>}{message.reply?.warnings.map((warning, i) => <small className="coach-warning" key={i}>{warning}</small>)}</article>)}
        {loading && <p className="coach-loading" role="status"><LoaderCircle size={16} className="coach-spinner" /> Reviewing your question and FinPilot data…</p>}<div ref={end} />
      </div>
      {!loading && followups.length > 0 && <div className="coach-followups">{followups.map((question) => <button key={question} className="question-chip" onClick={() => void send(question)}>{question}</button>)}</div>}
      {error && <div className="coach-chat-error" role="alert"><strong>Coach unavailable</strong><p>{error}</p><small>Your question is ready to retry. Other FinPilot pages remain available.</small></div>}
      <form className="coach-input" onSubmit={(event) => { event.preventDefault(); void send(draft); }}><label className="sr-only" htmlFor="coach-prompt">Ask FinPilot AI Coach</label><input id="coach-prompt" className="input" placeholder="Ask about your finances…" value={draft} maxLength={2000} disabled={loading} onChange={(event) => setDraft(event.target.value)} /><button className="coach-send" type="submit" disabled={loading || !draft.trim()} aria-label="Send question"><ArrowUp size={16} /></button></form>
      <p className="coach-disclaimer">Educational guidance, not licensed financial advice. Simulations are estimates and returns are not guaranteed. FinPilot cannot execute transactions. Consider professional advice for major decisions.</p>
    </section>
  </div>;
}
