from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.schemas import (
    HealthRead,
    KnowledgeArticleCreate,
    KnowledgeArticleRead,
    ReviewRequest,
    TicketCreate,
    TicketList,
    TicketRead,
)
from app.services.generation import ProviderConfigurationError
from app.services.support import (
    add_article,
    create_ticket,
    draft_ticket_response,
    get_ticket,
    list_articles,
    list_tickets,
    review_ticket,
    seed_knowledge_base,
    simulate_send,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_knowledge_base(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Customer-support triage, knowledge-grounded draft replies, explicit human review, "
        "and a simulated send workflow."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthRead, tags=["meta"])
def health() -> HealthRead:
    return HealthRead(status="ok", app=settings.app_name, ai_provider=settings.ai_provider)


@app.get("/tickets", response_model=TicketList, tags=["tickets"])
def tickets_list(
    ticket_status: str | None = Query(default=None, alias="status", max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TicketList:
    items, total = list_tickets(db, ticket_status, limit)
    return TicketList(items=items, total=total)


@app.post("/tickets", response_model=TicketRead, status_code=status.HTTP_201_CREATED, tags=["tickets"])
def tickets_create(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketRead:
    return create_ticket(db, payload)


@app.get("/tickets/{ticket_id}", response_model=TicketRead, tags=["tickets"])
def ticket_detail(ticket_id: str, db: Session = Depends(get_db)) -> TicketRead:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


@app.post("/tickets/{ticket_id}/draft", response_model=TicketRead, tags=["tickets"])
def ticket_draft(ticket_id: str, db: Session = Depends(get_db)) -> TicketRead:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    try:
        return draft_ticket_response(db, ticket)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid returning provider payloads or credentials to callers.
        raise HTTPException(status_code=502, detail="Draft generation failed. Check server logs and provider configuration.") from exc


@app.post("/tickets/{ticket_id}/review", response_model=TicketRead, tags=["tickets"])
def ticket_review(ticket_id: str, payload: ReviewRequest, db: Session = Depends(get_db)) -> TicketRead:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    try:
        return review_ticket(db, ticket, payload.decision, payload.reviewer, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/tickets/{ticket_id}/send", response_model=TicketRead, tags=["tickets"])
def ticket_send(ticket_id: str, db: Session = Depends(get_db)) -> TicketRead:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    try:
        return simulate_send(db, ticket)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/knowledge", response_model=list[KnowledgeArticleRead], tags=["knowledge base"])
def knowledge_list(db: Session = Depends(get_db)) -> list[KnowledgeArticleRead]:
    return list_articles(db)


@app.post(
    "/knowledge",
    response_model=KnowledgeArticleRead,
    status_code=status.HTTP_201_CREATED,
    tags=["knowledge base"],
)
def knowledge_create(payload: KnowledgeArticleCreate, db: Session = Depends(get_db)) -> KnowledgeArticleRead:
    try:
        return add_article(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
