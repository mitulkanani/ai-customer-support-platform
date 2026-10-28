from app.services.triage import classify_ticket
from app.services.knowledge import retrieve_articles
from app.models import KnowledgeArticle
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base


def test_normal_billing_question_is_not_marked_urgent() -> None:
    result = classify_ticket("Refund policy", "Please explain the refund policy for my purchase.")
    assert result.category == "billing"
    assert result.priority == "normal"
    assert result.assigned_team == "Billing Support"


def test_sensitive_phrase_requires_human_review() -> None:
    result = classify_ticket("Security concern", "My account has been hacked and compromised.")
    assert result.needs_human_review is True
    assert "sensitive" in result.tags
    assert result.priority == "urgent"


def test_retriever_returns_relevant_article_first() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            KnowledgeArticle(id="KB-A", title="Refund processing guide", content="Refunds return to the original payment method after approval.", tags=["refund", "billing"]),
            KnowledgeArticle(id="KB-B", title="Password reset guide", content="Reset the password using the sign in page.", tags=["account", "password"]),
        ])
        db.commit()
        matches = retrieve_articles(db, "refund original payment refund", limit=2)
    assert matches
    assert matches[0].article.id == "KB-A"
    assert matches[0].score > 0
