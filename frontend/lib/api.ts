export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type TicketStatus =
  | "triaged"
  | "draft_ready"
  | "needs_human_review"
  | "approved"
  | "rejected"
  | "escalated"
  | "sent";

export type Ticket = {
  id: string;
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
  category: string;
  priority: string;
  sentiment: string;
  assigned_team: string;
  status: TicketStatus;
  tags: string[];
  triage_reasons: string[];
  needs_human_review: boolean;
  source_ids: string[];
  response_draft: string | null;
  draft_provider: string | null;
  reviewer: string | null;
  review_note: string | null;
  response_sent_at: string | null;
  created_at: string;
  updated_at: string;
};

export type NewTicket = {
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Keep the generic HTTP message when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listTickets: () => request<{ items: Ticket[]; total: number }>("/tickets?limit=100"),
  createTicket: (ticket: NewTicket) => request<Ticket>("/tickets", { method: "POST", body: JSON.stringify(ticket) }),
  draft: (id: string) => request<Ticket>(`/tickets/${id}/draft`, { method: "POST" }),
  review: (id: string, decision: "approve" | "reject" | "escalate") =>
    request<Ticket>(`/tickets/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, reviewer: "Support Agent", note: "Reviewed in the demo dashboard." }),
    }),
  send: (id: string) => request<Ticket>(`/tickets/${id}/send`, { method: "POST" }),
};
