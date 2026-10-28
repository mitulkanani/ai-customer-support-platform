"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, NewTicket, Ticket } from "@/lib/api";

const EMPTY_FORM: NewTicket = { customer_name: "", customer_email: "", subject: "", message: "" };

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortId(id: string) {
  return id.split("-")[0].toUpperCase();
}

export default function Home() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState<NewTicket>(EMPTY_FORM);
  const [showCreate, setShowCreate] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async (preferredId?: string) => {
    const response = await api.listTickets();
    setTickets(response.items);
    setSelectedId((current) => {
      const desired = preferredId || current;
      return desired && response.items.some((ticket) => ticket.id === desired)
        ? desired
        : response.items[0]?.id || null;
    });
  }, []);

  useEffect(() => {
    api.listTickets()
      .then((response) => {
        setTickets(response.items);
        setSelectedId(response.items[0]?.id || null);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load tickets."))
      .finally(() => setLoading(false));
  }, []);

  const selected = tickets.find((ticket) => ticket.id === selectedId) || null;
  const filtered = useMemo(() => tickets.filter((ticket) => {
    const matchesStatus = statusFilter === "all"
      || (statusFilter === "review" && (ticket.needs_human_review || ["draft_ready", "needs_human_review"].includes(ticket.status)))
      || (statusFilter === "escalation" && (ticket.status === "escalated" || ticket.priority === "urgent"))
      || ticket.status === statusFilter;
    const query = search.trim().toLowerCase();
    const matchesSearch = !query || [ticket.subject, ticket.customer_name, ticket.customer_email, ticket.message]
      .some((value) => value.toLowerCase().includes(query));
    return matchesStatus && matchesSearch;
  }), [tickets, statusFilter, search]);

  const counts = useMemo(() => ({
    open: tickets.filter((ticket) => !["sent", "rejected"].includes(ticket.status)).length,
    review: tickets.filter((ticket) => ticket.needs_human_review || ["draft_ready", "needs_human_review"].includes(ticket.status)).length,
    escalated: tickets.filter((ticket) => ticket.status === "escalated" || ticket.priority === "urgent").length,
  }), [tickets]);

  async function runAction(action: () => Promise<Ticket>, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await action();
      await refresh(updated.id);
      setNotice(message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submitTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api.createTicket(form);
      setForm(EMPTY_FORM);
      setShowCreate(false);
      await refresh(created.id);
      setNotice("Ticket received and triaged. Generate a draft when you're ready.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create ticket.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">S</div>
          <div><div className="brand-name">SupportFlow</div><div className="brand-caption">AI SUPPORT DESK</div></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="nav-item active"><span className="nav-icon">▤</span> Inbox <span className="nav-count">{tickets.length}</span></button>
        <button className="nav-item" onClick={() => setStatusFilter("review")}><span className="nav-icon">◎</span> Human review</button>
        <button className="nav-item" onClick={() => setStatusFilter("escalation")}><span className="nav-icon">↗</span> Escalations</button>
        <div className="sidebar-bottom">
          <div className="online-dot" /> <span>Demo workspace</span>
          <p>AI drafts are reviewed by a person before sending.</p>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div><div className="eyebrow">CUSTOMER OPERATIONS</div><h1>Support inbox</h1></div>
          <div className="topbar-actions"><span className="provider-pill"><span className="tiny-dot" /> Knowledge-grounded AI</span><button className="primary-button" onClick={() => setShowCreate(true)}>＋ New ticket</button></div>
        </header>

        <section className="metric-row">
          <article className="metric-card"><div className="metric-label">ACTIVE TICKETS</div><div className="metric-value">{counts.open.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="metric-symbol">↗</span> In the support queue</div></article>
          <article className="metric-card"><div className="metric-label">NEEDS REVIEW</div><div className="metric-value">{counts.review.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="review-dot" /> Awaiting a human decision</div></article>
          <article className="metric-card"><div className="metric-label">ESCALATED / URGENT</div><div className="metric-value">{counts.escalated.toString().padStart(2, "0")}</div><div className="metric-foot"><span className="metric-symbol amber">!</span> Priority attention</div></article>
        </section>

        {notice && <div className="notice success-notice">✓ {notice}<button onClick={() => setNotice("")}>×</button></div>}
        {error && <div className="notice error-notice">{error}<button onClick={() => setError("")}>×</button></div>}

        <section className="inbox-layout">
          <div className="ticket-column panel">
            <div className="panel-heading"><div><h2>All tickets</h2><span>{filtered.length} conversations</span></div><span className="inbox-badge">INBOX</span></div>
            <div className="ticket-controls">
              <div className="search-box"><span>⌕</span><input aria-label="Search tickets" placeholder="Search conversations..." value={search} onChange={(event) => setSearch(event.target.value)} /></div>
              <select aria-label="Filter tickets by status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option><option value="review">Human review queue</option><option value="escalation">Escalations / urgent</option><option value="triaged">Triaged</option><option value="draft_ready">Draft ready</option><option value="needs_human_review">Needs review</option><option value="approved">Approved</option><option value="escalated">Escalated</option><option value="sent">Sent</option><option value="rejected">Rejected</option>
              </select>
            </div>
            <div className="ticket-list">
              {loading ? <div className="empty-state">Loading tickets…</div> : filtered.length === 0 ? <div className="empty-state"><div className="empty-icon">✳</div><strong>No conversations here</strong><span>Create a ticket to try triage and response drafting.</span></div> : filtered.map((ticket) => (
                <button key={ticket.id} className={`ticket-item ${ticket.id === selectedId ? "selected" : ""}`} onClick={() => setSelectedId(ticket.id)}>
                  <div className="ticket-avatar">{ticket.customer_name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase()}</div>
                  <div className="ticket-item-main"><div className="ticket-item-top"><strong>{ticket.customer_name}</strong><span className="ticket-time">{new Date(ticket.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span></div><div className="ticket-subject">{ticket.subject}</div><div className="ticket-item-bottom"><span className={`status-chip status-${ticket.status}`}>{labelize(ticket.status)}</span><span className={`priority-label priority-${ticket.priority}`}>{ticket.priority}</span></div></div>
                </button>
              ))}
            </div>
          </div>

          <div className="detail-column panel">
            {!selected ? <div className="empty-state detail-empty"><div className="empty-icon">✳</div><strong>Select a conversation</strong><span>Ticket details and AI actions will appear here.</span></div> : <>
              <div className="detail-head"><div><div className="eyebrow">TICKET {shortId(selected.id)}</div><h2>{selected.subject}</h2><div className="detail-meta"><span>{selected.customer_name}</span><span>·</span><span>{selected.customer_email}</span></div></div><span className={`priority-badge priority-${selected.priority}`}>{selected.priority} priority</span></div>
              <div className="detail-tags"><span className="category-chip">{labelize(selected.category)}</span><span className="status-chip status-plain">{labelize(selected.status)}</span>{selected.needs_human_review && <span className="human-chip">Human review required</span>}</div>
              <div className="conversation-block"><div className="message-label"><span className="customer-avatar">{selected.customer_name.slice(0, 1).toUpperCase()}</span><div><strong>{selected.customer_name}</strong><span>Customer message</span></div></div><p className="customer-message">{selected.message}</p></div>

              <div className="triage-card"><div className="section-title"><span className="sparkle">✦</span><h3>AI triage summary</h3><span className="confidence-pill">Rule-based baseline</span></div><div className="triage-grid"><div><span>ROUTED TEAM</span><strong>{selected.assigned_team}</strong></div><div><span>SENTIMENT</span><strong className={`sentiment-${selected.sentiment}`}>{labelize(selected.sentiment)}</strong></div></div><ul className="reason-list">{selected.triage_reasons.map((reason, index) => <li key={`${reason}-${index}`}>{reason}</li>)}</ul></div>

              <div className="draft-section"><div className="section-title"><span className="draft-icon">✎</span><h3>Suggested response</h3>{selected.draft_provider && <span className="draft-provider">{selected.draft_provider}</span>}</div>
                {selected.response_draft ? <div className="draft-content">{selected.response_draft.split("\n").map((line, index) => line ? <p key={index}>{line}</p> : <div key={index} className="draft-line-gap" />)}</div> : <div className="draft-placeholder"><div className="placeholder-sparkle">✦</div><div><strong>No draft yet</strong><span>Use the knowledge base to prepare a response with cited sources.</span></div></div>}
                {selected.source_ids.length > 0 && <div className="sources-row"><span>GROUNDED IN</span>{selected.source_ids.map((source) => <span className="source-chip" key={source}>{source}</span>)}</div>}
                {selected.status === "sent" && <div className="sent-notice">✓ Simulated send recorded. No email was actually sent.</div>}
                <div className="action-row">
                  {!selected.response_draft && <button className="primary-button" disabled={busy} onClick={() => runAction(() => api.draft(selected.id), "Response draft generated from the knowledge base.")}>✦ Generate draft</button>}
                  {selected.response_draft && ["draft_ready", "needs_human_review", "rejected", "escalated"].includes(selected.status) && <>
                    <button className="primary-button" disabled={busy} onClick={() => runAction(() => api.review(selected.id, "approve"), "Draft approved. Sending remains a separate step.")}>✓ Approve draft</button>
                    <button className="secondary-button" disabled={busy} onClick={() => runAction(() => api.review(selected.id, "reject"), "Draft rejected for revision.")}>Reject</button>
                    <button className="text-button" disabled={busy} onClick={() => runAction(() => api.review(selected.id, "escalate"), "Ticket escalated to a senior support queue.")}>Escalate ↗</button>
                  </>}
                  {selected.status === "approved" && <button className="primary-button" disabled={busy} onClick={() => runAction(() => api.send(selected.id), "Simulated send recorded. No email was sent.")}>Send (simulate) →</button>}
                  {busy && <span className="busy-label">Working…</span>}
                </div>
                <p className="safety-footnote">AI drafts are suggestions. Review facts, policy, and customer context before approval. Sending is simulated in this demo.</p>
              </div>
            </>}
          </div>
        </section>
        <footer className="page-footer"><span>SupportFlow <b>·</b> Portfolio demo</span><span>Human-in-the-loop by design</span></footer>
      </section>

      {showCreate && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowCreate(false); }}><section className="create-modal" role="dialog" aria-modal="true" aria-labelledby="create-title"><div className="modal-head"><div><div className="eyebrow">INBOX</div><h2 id="create-title">Create support ticket</h2><p>Incoming tickets are triaged automatically. Drafts are generated separately.</p></div><button className="close-button" aria-label="Close dialog" onClick={() => setShowCreate(false)}>×</button></div><form onSubmit={submitTicket} className="create-form"><label>Customer name<input required minLength={2} value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} placeholder="Alex Morgan" /></label><label>Customer email<input required type="email" value={form.customer_email} onChange={(event) => setForm({ ...form, customer_email: event.target.value })} placeholder="alex@example.com" /></label><label>Subject<input required minLength={4} value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} placeholder="I need help with my order" /></label><label>Customer message<textarea required minLength={10} rows={5} value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} placeholder="Describe the issue as the customer reported it…" /></label><div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setShowCreate(false)}>Cancel</button><button className="primary-button" type="submit" disabled={busy}>{busy ? "Creating…" : "Create and triage"}</button></div></form></section></div>}
    </main>
  );
}
