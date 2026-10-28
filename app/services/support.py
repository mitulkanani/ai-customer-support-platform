from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeArticle, SupportTicket
from app.schemas import KnowledgeArticleCreate, TicketCreate
from app.services.generation import generate_draft
from app.services.knowledge import retrieve_articles
from app.services.triage import classify_ticket


STARTER_ARTICLES = [
    {
        "id": "KB-001",
        "title": "Reset your password",
        "content": (
            "To reset your password, open the sign-in page and choose 'Forgot password'. "
            "Enter the email address associated with your account and follow the link in the "
            "password-reset email. The reset link expires after 30 minutes. If the email does not "
            "arrive, check your spam folder and confirm that you entered the correct email address. "
            "Support agents should never ask customers to share their passwords or one-time codes."
        ),
        "tags": ["account", "password", "login", "sign in", "reset"],
    },
    {
        "id": "KB-002",
        "title": "Refund eligibility and processing",
        "content": (
            "Customers may request a refund within 30 days of the original purchase if the order "
            "meets the applicable purchase terms. Once a refund is approved, it is returned to the "
            "original payment method. Banks and card providers control the final posting time, which "
            "can vary. Agents must verify the order and current policy before promising eligibility "
            "or a posting date. Never tell a customer that a refund has been issued before the payment "
            "system confirms it."
        ),
        "tags": ["billing", "refund", "payment", "charge", "invoice", "subscription"],
    },
    {
        "id": "KB-003",
        "title": "Troubleshoot application errors",
        "content": (
            "If the application displays an error, ask the customer to record the error message, "
            "the approximate time it occurred, and the browser or app version. They can try refreshing "
            "the page and checking the service-status page. Do not ask the customer to share passwords, "
            "access tokens, payment card details, or other secrets. If the error persists or affects "
            "multiple users, escalate the ticket to Technical Support with the error details and impact."
        ),
        "tags": ["technical", "error", "bug", "crash", "api", "timeout", "application"],
    },
    {
        "id": "KB-004",
        "title": "Find an order and track delivery",
        "content": (
            "Customers can find their order number in the order confirmation email. When a tracking "
            "number is available, use the order page to open the carrier tracking link. Tracking events "
            "may not appear immediately after a parcel is scanned. If tracking has not changed for an "
            "extended period, verify the order details and refer the case to Order Support. Do not promise "
            "a delivery date that is not confirmed by the carrier."
        ),
        "tags": ["shipping", "delivery", "tracking", "package", "shipment", "order"],
    },
    {
        "id": "KB-005",
        "title": "Protect a potentially compromised account",
        "content": (
            "If a customer suspects unauthorized account access, route the case to Trust & Security "
            "for review. Do not ask the customer to send passwords, verification codes, recovery codes, "
            "or payment details in a support conversation. Ask them to use the official account recovery "
            "flow if they can still access the account. Do not promise that an account is secure until "
            "the security review is complete. Security-related cases require human review."
        ),
        "tags": ["security", "hacked", "fraud", "unauthorized", "compromised", "account"],
    },
]


def seed_knowledge_base(db: Session) -> None:
    if db.scalar(select(KnowledgeArticle.id).limit(1)) is not None:
        return
    for article in STARTER_ARTICLES:
        db.add(KnowledgeArticle(**article))
    db.commit()


def list_articles(db: Session) -> list[KnowledgeArticle]:
    return list(db.scalars(select(KnowledgeArticle).order_by(KnowledgeArticle.id)).all())


def add_article(db: Session, payload: KnowledgeArticleCreate) -> KnowledgeArticle:
    article_id = payload.id or f"KB-{uuid4().hex[:8].upper()}"
    if db.get(KnowledgeArticle, article_id) is not None:
        raise ValueError(f"Knowledge article '{article_id}' already exists.")
    article = KnowledgeArticle(
        id=article_id,
        title=payload.title,
        content=payload.content,
        tags=[tag.strip().lower() for tag in payload.tags if tag.strip()],
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def create_ticket(db: Session, payload: TicketCreate) -> SupportTicket:
    triage = classify_ticket(payload.subject, payload.message)
    ticket = SupportTicket(
        customer_name=payload.customer_name.strip(),
        customer_email=payload.customer_email.lower().strip(),
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        category=triage.category,
        priority=triage.priority,
        sentiment=triage.sentiment,
        assigned_team=triage.assigned_team,
        status="triaged",
        tags=triage.tags,
        triage_reasons=triage.reasons,
        needs_human_review=triage.needs_human_review,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: str) -> SupportTicket | None:
    return db.get(SupportTicket, ticket_id)


def list_tickets(db: Session, status: str | None, limit: int) -> tuple[list[SupportTicket], int]:
    query = select(SupportTicket)
    count_query = select(SupportTicket.id)
    if status:
        query = query.where(SupportTicket.status == status)
        count_query = count_query.where(SupportTicket.status == status)
    total = len(db.scalars(count_query).all())
    tickets = db.scalars(
        query.order_by(SupportTicket.created_at.desc()).limit(limit)
    ).all()
    return list(tickets), total


def draft_ticket_response(db: Session, ticket: SupportTicket) -> SupportTicket:
    if ticket.status == "sent":
        raise ValueError("A response has already been sent for this ticket.")
    query = f"{ticket.subject}\n{ticket.message}\n{ticket.category}"
    sources = retrieve_articles(db, query, limit=3)
    draft, provider = generate_draft(
        customer_name=ticket.customer_name,
        category=ticket.category,
        subject=ticket.subject,
        message=ticket.message,
        sources=sources,
    )
    ticket.response_draft = draft
    ticket.draft_provider = provider
    ticket.source_ids = [item.article.id for item in sources]
    if not sources:
        ticket.needs_human_review = True
        reason = "No relevant knowledge-base article was found; verify the answer manually."
        if reason not in ticket.triage_reasons:
            ticket.triage_reasons.append(reason)
    ticket.status = "needs_human_review" if ticket.needs_human_review else "draft_ready"
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return ticket


def review_ticket(
    db: Session, ticket: SupportTicket, decision: str, reviewer: str, note: str | None
) -> SupportTicket:
    allowed = {"draft_ready", "needs_human_review", "rejected", "escalated"}
    if ticket.status not in allowed:
        raise ValueError(f"Ticket must have a draft awaiting review; current status is '{ticket.status}'.")
    if not ticket.response_draft:
        raise ValueError("Generate a response draft before reviewing this ticket.")
    ticket.reviewer = reviewer.strip()
    ticket.review_note = note.strip() if note else None
    if decision == "approve":
        ticket.status = "approved"
    elif decision == "reject":
        ticket.status = "rejected"
    elif decision == "escalate":
        ticket.status = "escalated"
        ticket.assigned_team = "Trust & Security" if ticket.category == "security" else "Senior Support"
    else:
        raise ValueError("Unsupported review decision.")
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return ticket


def simulate_send(db: Session, ticket: SupportTicket) -> SupportTicket:
    if ticket.status != "approved":
        raise ValueError("Only an approved draft can be sent.")
    # Deliberately records a simulated send; no email provider is contacted.
    ticket.status = "sent"
    ticket.response_sent_at = datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return ticket
