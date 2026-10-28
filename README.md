# AI Customer Support Platform

A full-stack demo of an **AI-assisted customer-support workflow**: ticket intake, triage, knowledge-grounded response drafting, human review, and a simulated send step.

The project complements the first two portfolio repos: it applies the safe workflow gates from `ai-agent-workflow-automation` and a knowledge-grounded response approach similar to `rag-knowledge-base-assistant`.

> **Honest scope:** the default AI provider is a deterministic template generator and the retriever is a transparent lexical baseline, so the app runs without API credentials. An optional OpenAI chat-completions provider is included for draft generation. No email is sent; the send endpoint only records a simulated send. This is a portfolio starter, not a production-ready support system.

## Features

- **Ticket intake:** create tickets through the dashboard or REST API.
- **Automated triage:** rule-based category, priority, sentiment, team routing, and escalation indicators.
- **Knowledge retrieval:** ranked retrieval over seeded and user-added help articles.
- **Grounded draft responses:** include source IDs in drafts; when no matching article is found, the template explicitly avoids inventing a policy answer and asks for human follow-up.
- **Human-in-the-loop workflow:** drafts must be reviewed before approval; only approved drafts can move to the simulated send step.
- **Escalation:** sensitive topics such as possible account compromise or legal threats are flagged for human review.
- **Persistent storage:** SQLAlchemy supports local SQLite and PostgreSQL.
- **Dashboard:** Next.js UI for ticket creation, search/filtering, triage inspection, source inspection, and review actions.
- **CI and containers:** pytest suite, GitHub Actions workflow, Dockerfiles, and Docker Compose.

## Architecture

```text
Next.js dashboard
       |
       v
FastAPI REST API ---------------------- /tickets, /knowledge, /health
       |
       +-- Triage service -------------- category / priority / sentiment / routing
       |
       +-- Knowledge retrieval -------- seeded and managed support articles
       |
       +-- Draft generator ------------- template mode or optional OpenAI provider
       |
       +-- Review state machine -------- approve / reject / escalate / simulated send
       |
       v
SQLAlchemy ---------------------------- SQLite locally / PostgreSQL in Compose
```

## Quick start: local backend

Python 3.11+ is recommended.

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

The API uses SQLite by default and creates `support.db` when it starts. The initial knowledge base is seeded automatically. Open the API explorer at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Run the full stack with Docker Compose

Docker Compose starts PostgreSQL, the FastAPI service, and the dashboard.

```bash
cp .env.example .env
# Optional: add OPENAI_API_KEY and set AI_PROVIDER=openai in .env

docker compose up --build
```

- Dashboard: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- PostgreSQL is published locally on port `5433` to avoid colliding with a local PostgreSQL server.

By default, `AI_PROVIDER=template` means no external API calls are required. For model-generated drafts, configure `AI_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL` in `.env`. Do not commit real keys to the repository. OpenAI provider errors are returned as a generic API error; inspect server logs for diagnostics.

## Example workflow through the API

Create a ticket:

```bash
curl -X POST http://localhost:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{"customer_name":"Alex Morgan","customer_email":"alex@example.com","subject":"How do I request a refund?","message":"Please explain refund eligibility and how a refund is processed for my purchase."}'
```

Use the returned `id` in the next calls:

```bash
# Retrieve relevant knowledge articles and generate a draft
curl -X POST http://localhost:8000/tickets/<ticket_id>/draft

# Inspect ticket state, draft, and source IDs
curl http://localhost:8000/tickets/<ticket_id>

# Approve the draft after human review
curl -X POST http://localhost:8000/tickets/<ticket_id>/review \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve","reviewer":"Support Agent","note":"Reviewed the cited policy source."}'

# Records a simulated send only. No email is sent.
curl -X POST http://localhost:8000/tickets/<ticket_id>/send
```

Use `"decision":"reject"` to reject a draft or `"decision":"escalate"` to route it for senior review. The API will return `409 Conflict` if a send is attempted before a draft is approved.

## REST API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health and provider mode |
| `GET` | `/tickets` | List tickets; supports `status` and `limit` query parameters |
| `POST` | `/tickets` | Create a ticket and run triage |
| `GET` | `/tickets/{id}` | Read ticket, triage, draft, review, and source metadata |
| `POST` | `/tickets/{id}/draft` | Retrieve knowledge and generate a response draft |
| `POST` | `/tickets/{id}/review` | Approve, reject, or escalate a draft |
| `POST` | `/tickets/{id}/send` | Record a simulated send for an approved draft |
| `GET` | `/knowledge` | List knowledge articles |
| `POST` | `/knowledge` | Add a knowledge article |

## Tests

```bash
python -m pip install -e ".[dev]"
pytest
```

The tests use a dedicated temporary SQLite database and the template provider, so they do not require a running PostgreSQL service or an OpenAI key.

## Security and production considerations

- Triage is **rule-based**, not a trained classifier. Validate thresholds on real, consented, representative examples before using it for staffing or SLAs.
- Lexical retrieval is simple and inspectable, but it is not vector search. A logical next step is to plug in the pgvector hybrid retrieval from the separate `rag-knowledge-base-assistant` project.
- An LLM can still produce incorrect or incomplete content. Source IDs are provenance hints, not proof that every claim is correct; human review remains mandatory before sending.
- No authentication, tenant isolation, abuse controls, rate limits, or role-based permissions are included. Add them before exposing this app to the internet or real customer data.
- The UI currently uses a demo reviewer identity. Replace it with an authenticated user identity before production use.
- The send action intentionally **does not contact an email provider**. Add an email adapter, idempotency, audit logs, and delivery-state reconciliation before enabling actual sends.
- Do not store passwords, payment details, access tokens, or other secrets in ticket text. Configure data retention and PII redaction for a real deployment.
- Production operation should use migrations instead of `Base.metadata.create_all`, structured logs, monitoring, a backup strategy, and a queue for long-running provider calls.

## Project layout

```text
app/
  main.py                   # FastAPI routes and application startup
  db.py                     # SQLAlchemy engine and session dependency
  models.py                 # Ticket and knowledge article tables
  schemas.py                # API request / response schemas
  services/
    triage.py               # Rule-based ticket classification
    knowledge.py            # Lexical article retrieval
    generation.py           # Template and optional OpenAI generation
    support.py              # Ticket lifecycle and seed knowledge base
frontend/
  app/page.tsx              # Dashboard and review workflow
  app/globals.css           # Responsive dashboard styling
  lib/api.ts                # Typed API client
 tests/
  test_api.py
  test_triage_and_retrieval.py
```

## Roadmap

- [ ] Replace keyword triage with an evaluated classification pipeline.
- [ ] Connect retrieval to pgvector and hybrid dense/sparse search.
- [ ] Add tenant-aware authentication and role-based review permissions.
- [ ] Add a real email-provider adapter behind a disabled-by-default flag.
- [ ] Add ticket-level audit history and reviewer identity from auth context.
- [ ] Add prompt and response evaluations plus latency/cost observability.
- [ ] Add a queue for async drafting, retries, and provider timeouts.

## License

MIT. See [LICENSE](LICENSE).
