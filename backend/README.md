# Kaleidoscope Backend

FastAPI + SQLAlchemy + LiteLLM service for LLM evaluation — query generation, scoring, annotation, and metrics.

## Project Structure

```
backend/src/
  common/
    auth/           JWT auth (dependencies, routes, utils)
    config.py       Settings from environment variables
    connectors/     Base HTTP connector + registry
    database/
      connection.py SQLAlchemy setup
      models.py     ORM models
      repositories/ All DB CRUD — only layer allowed to touch the DB
      migrations/   Manual migration scripts (local test helpers only)
    llm/
      client.py     LiteLLM wrapper
      cost_tracker.py
      instrumentation.py  Langfuse OTEL callback
      provider_catalog.yaml  Provider + model definitions
    models/         Pydantic request/response schemas
    prompts/
      templates/    Jinja2 Markdown prompt templates
    services/       Shared services (export, rubric classification)
  extensions/       Optional connectors (e.g. aibots/)
  query_generation/ Personas, questions, answers, KB, web search
  scoring/          Claims, judge scoring, metrics, QA jobs
```

## API Reference

Full interactive docs at **http://localhost:8000/docs**.

## Authentication

- User logs in → receives a JWT token (expires after 3 days)
- Every request (except `/auth/login`, `/health`, `/docs`) requires `Authorization: Bearer <token>`
- Only holders of `ADMIN_API_KEY` can create users via `/auth/admin/create-user`

| Key | Purpose |
|-----|---------|
| `JWT_SECRET_KEY` | Signs and validates tokens (never leaves server) |
| `ADMIN_API_KEY` | Authorises user creation (sent as `X-Admin-Key` header) |

Local dev defaults (`dev-jwt-secret` / `dev-admin-key`) are set in `docker-compose.yml`. Rotate before deploying to production.

**Create a user:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "X-Admin-Key: <ADMIN_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "pass123", "is_admin": false}'
```

## LLM Providers

Default model: `gemini/gemini-3.1-flash-lite-preview` (set in `src/common/config.py`).

**Override via env** (applies to all requests):
```bash
DEFAULT_LLM_MODEL=openai/gpt-5-mini
```

**Override per request**: pass `"model_used": "openai/gpt-5-mini"` in the request body.

Supported providers and their required env vars are in [`src/common/llm/provider_catalog.yaml`](src/common/llm/provider_catalog.yaml). Add your own provider entry there.

| Provider | Env var(s) |
|----------|-----------|
| Gemini | `GEMINI_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Azure OpenAI | `AZURE_API_KEY` + `AZURE_API_BASE` |
| AWS Bedrock | `AWS_BEARER_TOKEN_BEDROCK` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Fireworks | `FIREWORKS_AI_API_KEY` |

## Observability (Langfuse)

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to automatically trace all LLM calls via LiteLLM's OTEL callback. Set `LANGFUSE_BASE_URL` for a self-hosted instance, or leave unset for Langfuse cloud.

## Tests

```bash
cd backend
uv run pytest tests/
uv run pytest tests/unit/ -m unit
uv run pytest tests/ --cov=src --cov-report=html
```
