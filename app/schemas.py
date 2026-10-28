from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: str = Field(
        min_length=6,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    subject: str = Field(min_length=4, max_length=200)
    message: str = Field(min_length=10, max_length=12000)


class KnowledgeArticleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=3, max_length=40)
    title: str = Field(min_length=5, max_length=200)
    content: str = Field(min_length=30, max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=30)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject", "escalate"]
    reviewer: str = Field(min_length=2, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_name: str
    customer_email: str
    subject: str
    message: str
    category: str
    priority: str
    sentiment: str
    assigned_team: str
    status: str
    tags: list[str]
    triage_reasons: list[str]
    needs_human_review: bool
    source_ids: list[str]
    response_draft: str | None
    draft_provider: str | None
    reviewer: str | None
    review_note: str | None
    response_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    content: str
    tags: list[str]
    updated_at: datetime


class TicketList(BaseModel):
    items: list[TicketRead]
    total: int


class HealthRead(BaseModel):
    status: str
    app: str
    ai_provider: str
