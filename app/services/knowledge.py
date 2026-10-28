import re
from dataclasses import dataclass
from math import log1p

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeArticle

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from",
    "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "please",
    "the", "this", "to", "we", "what", "when", "where", "with", "you", "your",
}


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1 and token not in STOPWORDS]


@dataclass(frozen=True)
class RetrievedArticle:
    article: KnowledgeArticle
    score: float


def retrieve_articles(db: Session, query: str, limit: int = 3) -> list[RetrievedArticle]:
    """Transparent lexical retrieval baseline; replace with embeddings for scale."""
    query_terms = set(tokenize(query))
    if not query_terms:
        return []

    articles = db.scalars(select(KnowledgeArticle)).all()
    scored: list[RetrievedArticle] = []
    for article in articles:
        title_terms = set(tokenize(article.title))
        body_terms = set(tokenize(article.content))
        tag_terms = set(tokenize(" ".join(article.tags)))
        title_matches = query_terms & title_terms
        body_matches = query_terms & body_terms
        tag_matches = query_terms & tag_terms
        score = (3.0 * len(title_matches)) + (len(body_matches)) + (2.0 * len(tag_matches))
        if score > 0:
            # Normalize gently, prioritizing distinct query-term coverage.
            score = (score / (1 + log1p(len(body_terms)))) + 2.0 * len(query_terms & (title_terms | tag_terms))
            scored.append(RetrievedArticle(article=article, score=round(score, 4)))
    scored.sort(key=lambda item: (item.score, item.article.id), reverse=True)
    return scored[: max(1, min(limit, 10))]
