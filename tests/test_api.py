import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def create_ticket(client: TestClient, *, subject: str, message: str) -> dict:
    response = client.post(
        "/tickets",
        json={
            "customer_name": "Alex Morgan",
            "customer_email": "alex@example.com",
            "subject": subject,
            "message": message,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_root(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["ai_provider"] == "template"
    assert client.get("/").json()["docs"] == "/docs"


def test_seeded_knowledge_base_is_available(client: TestClient) -> None:
    response = client.get("/knowledge")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} >= {"KB-001", "KB-002", "KB-003", "KB-004", "KB-005"}


def test_ticket_creation_classifies_billing_and_assigns_team(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="Question about my invoice",
        message="Could you explain this invoice line item on my monthly subscription?",
    )
    assert ticket["category"] == "billing"
    assert ticket["assigned_team"] == "Billing Support"
    assert ticket["status"] == "triaged"
    assert ticket["priority"] in {"normal", "low"}


def test_security_ticket_is_urgent_and_requires_human_review(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="My account may be compromised",
        message="I noticed unauthorized access and think my account has been hacked.",
    )
    assert ticket["category"] == "security"
    assert ticket["priority"] == "urgent"
    assert ticket["assigned_team"] == "Trust & Security"
    assert ticket["needs_human_review"] is True


def test_draft_uses_knowledge_sources_and_requests_review(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="How do I request a refund?",
        message="Please explain refund eligibility and how a refund is processed for a purchase.",
    )
    response = client.post(f"/tickets/{ticket['id']}/draft")
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["response_draft"]
    assert "KB-002" in updated["source_ids"]
    assert "KB-002" in updated["response_draft"]
    assert updated["draft_provider"] == "template"
    assert updated["status"] in {"draft_ready", "needs_human_review"}


def test_send_is_blocked_until_approved(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="Question about password reset",
        message="I need instructions for resetting the password on my account.",
    )
    assert client.post(f"/tickets/{ticket['id']}/draft").status_code == 200
    response = client.post(f"/tickets/{ticket['id']}/send")
    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()


def test_approved_draft_can_be_simulated_as_sent(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="How can I reset my password?",
        message="Please help me understand the password reset steps for my account.",
    )
    assert client.post(f"/tickets/{ticket['id']}/draft").status_code == 200
    review = client.post(
        f"/tickets/{ticket['id']}/review",
        json={"decision": "approve", "reviewer": "Support Agent", "note": "Checked policy source."},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"
    assert review.json()["reviewer"] == "Support Agent"

    sent = client.post(f"/tickets/{ticket['id']}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["response_sent_at"] is not None


def test_review_can_reject_a_draft(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="Help tracking my order",
        message="Can you explain where I can find the shipment tracking for my recent order?",
    )
    assert client.post(f"/tickets/{ticket['id']}/draft").status_code == 200
    response = client.post(
        f"/tickets/{ticket['id']}/review",
        json={"decision": "reject", "reviewer": "Sam Reviewer", "note": "Needs a more specific answer."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_review_can_escalate_ticket(client: TestClient) -> None:
    ticket = create_ticket(
        client,
        subject="Unexpected account activity",
        message="I see a suspicious login and believe my account has been compromised.",
    )
    assert client.post(f"/tickets/{ticket['id']}/draft").status_code == 200
    response = client.post(
        f"/tickets/{ticket['id']}/review",
        json={"decision": "escalate", "reviewer": "Security Agent", "note": "Please investigate."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "escalated"
    assert response.json()["assigned_team"] == "Trust & Security"


def test_ticket_status_filter_works(client: TestClient) -> None:
    response = client.get("/tickets?status=triaged&limit=10")
    assert response.status_code == 200
    assert response.json()["total"] == len(response.json()["items"])
    assert all(item["status"] == "triaged" for item in response.json()["items"])


def test_unknown_ticket_returns_404(client: TestClient) -> None:
    response = client.get("/tickets/not-a-real-ticket")
    assert response.status_code == 404


def test_ticket_validation_rejects_bad_email_and_extra_fields(client: TestClient) -> None:
    bad_email = client.post(
        "/tickets",
        json={"customer_name": "Alex Morgan", "customer_email": "bad", "subject": "Question", "message": "Long enough customer message", "extra": "no"},
    )
    assert bad_email.status_code == 422


def test_knowledge_article_can_be_added_and_duplicate_is_rejected(client: TestClient) -> None:
    payload = {
        "id": "KB-TEST-99",
        "title": "Test knowledge article title",
        "content": "This is a sufficiently long knowledge article body for testing inserts.",
        "tags": ["test", "article"],
    }
    created = client.post("/knowledge", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["id"] == "KB-TEST-99"
    duplicate = client.post("/knowledge", json=payload)
    assert duplicate.status_code == 409
