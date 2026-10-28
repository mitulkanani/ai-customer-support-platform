import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TriageResult:
    category: str
    priority: str
    sentiment: str
    assigned_team: str
    tags: list[str]
    reasons: list[str]
    needs_human_review: bool


CATEGORY_RULES: dict[str, tuple[str, ...]] = {
    "billing": ("refund", "invoice", "charged", "charge", "payment", "billing", "subscription", "receipt", "price"),
    "technical": ("error", "bug", "crash", "not working", "broken", "timeout", "slow", "failed", "failure", "api", "integration"),
    "account": ("login", "log in", "password", "account", "locked out", "sign in", "verification", "2fa"),
    "shipping": ("shipping", "delivery", "tracking", "package", "shipment", "courier", "arrived", "order"),
    "security": ("hacked", "unauthorized", "compromised", "breach", "stolen", "suspicious login", "fraud"),
}

URGENT_TERMS = (
    "data breach", "account compromised", "account hacked", "fraud", "payment stolen",
    "production outage", "service down", "security incident", "unauthorized access",
)
HIGH_TERMS = (
    "charged twice", "cannot access", "can't access", "locked out", "not working",
    "refund urgently", "business is blocked", "outage", "lost access",
)
NEGATIVE_TERMS = ("angry", "furious", "frustrated", "unacceptable", "terrible", "scam", "disappointed", "upset")
POSITIVE_TERMS = ("thank you", "thanks", "great service", "appreciate", "helpful")
HUMAN_REVIEW_TERMS = (
    "lawyer", "legal action", "lawsuit", "chargeback", "data breach", "hacked",
    "compromised", "fraud", "regulator", "threaten", "self harm", "suicide",
)


def _contains(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def classify_ticket(subject: str, message: str) -> TriageResult:
    combined = f"{subject}\n{message}".lower()
    category_scores = {
        category: [term for term in terms if term in combined]
        for category, terms in CATEGORY_RULES.items()
    }
    category, category_hits = max(category_scores.items(), key=lambda item: len(item[1]))
    security_hits = category_scores["security"]
    # Security indicators take precedence over a generic account/login match.
    if security_hits:
        category, category_hits = "security", security_hits
    if not category_hits:
        category = "other"

    urgent_hits = _contains(combined, URGENT_TERMS)
    high_hits = _contains(combined, HIGH_TERMS)
    if urgent_hits or category == "security":
        priority = "urgent"
    elif high_hits:
        priority = "high"
    elif category in {"billing", "account", "technical"}:
        priority = "normal"
    else:
        priority = "low"

    if _contains(combined, NEGATIVE_TERMS):
        sentiment = "negative"
    elif _contains(combined, POSITIVE_TERMS):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    team_by_category = {
        "billing": "Billing Support",
        "technical": "Technical Support",
        "account": "Account Support",
        "shipping": "Order Support",
        "security": "Trust & Security",
        "other": "Customer Support",
    }
    risk_hits = _contains(combined, HUMAN_REVIEW_TERMS)
    reasons: list[str] = []
    if category_hits:
        reasons.append(f"Category matched: {category_hits[0]}.")
    else:
        reasons.append("No category keyword matched; routed to general support.")
    if urgent_hits:
        reasons.append(f"Urgent phrase detected: {urgent_hits[0]}.")
    elif high_hits:
        reasons.append(f"High-priority phrase detected: {high_hits[0]}.")
    if risk_hits:
        reasons.append(f"Sensitive issue requires human review: {risk_hits[0]}.")
    if sentiment == "negative":
        reasons.append("Negative customer sentiment detected.")

    tags = [category, priority]
    if sentiment == "negative":
        tags.append("negative-sentiment")
    if risk_hits:
        tags.append("sensitive")
    if category == "security":
        tags.append("security")

    return TriageResult(
        category=category,
        priority=priority,
        sentiment=sentiment,
        assigned_team=team_by_category[category],
        tags=tags,
        reasons=reasons,
        needs_human_review=bool(risk_hits) or priority in {"high", "urgent"},
    )
