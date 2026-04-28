# Kaleidoscope — Agent Guide

Guide for AI agents working on this repository.

**Who this is for**: coding agents (Codex, Cursor, etc.) and any agent helping a non-developer get Kaleidoscope running.

---

## Project Overview

Kaleidoscope is an automated LLM evaluation platform. It runs systematic evals: generate diverse questions across user personas → collect target responses → score with LLM judges → annotate for ground truth → measure judge reliability.

---

## Project Structure

```
kaleidoscope/
├── backend/        FastAPI + SQLAlchemy + LiteLLM (Python 3.13, uv)
├── frontend/       Next.js 16 + React 19 + MUI v7 (TypeScript)
├── docker-compose.yml
└── .env.example
```

### Backend

```
backend/src/
  common/
    auth/           JWT auth (dependencies, routes, utils)
    connectors/     Base HTTP connector + registry
    database/
      models.py     SQLAlchemy ORM models
      repositories/ All DB CRUD — only layer allowed to touch DB
      migrations/   Local test helper scripts
    llm/            LiteLLM wrapper, CostTracker, provider_catalog.yaml
    models/         Pydantic request/response schemas
    prompts/
      templates/    Jinja2 Markdown prompt templates
  extensions/       Optional connectors (e.g. aibots/)
  query_generation/ Personas, questions, KB, web search
  scoring/          Claims, judge scoring, metrics, QA jobs
```

### Frontend

```
frontend/
  lib/
    api.ts          All API calls — never use fetch() directly
    types.ts        TypeScript interfaces (mirror backend Pydantic models)
    theme.tsx       MUI theme
    modelIcons.ts   Provider logo mapping
  app/              Next.js App Router pages
  components/       Reusable React components
```

---

## Setup Walkthrough (Non-Developer)

Follow these steps to get Kaleidoscope running locally. If you're an AI agent helping a user, guide them through each step.

1. **Check prerequisites** — Docker Desktop must be installed and running.

2. **Clone the repo**
   ```bash
   git clone https://github.com/govtech-responsibleai/kaleidoscope.git
   cd kaleidoscope
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

   > **Agent**: At this point, stop. Tell the user which keys they need to fill in, then ask them for the values before continuing.
   >
   > Minimum required: one LLM API key (e.g. `GEMINI_API_KEY`).
   > Optional but useful: `SERPER_API_KEY` (web search context for question generation), Langfuse keys (observability).
   > See [`.env.example`](.env.example) for the full list.

4. **Start services**
   ```bash
   docker compose up -d
   ```

   > For Docker troubleshooting, rebuild steps, and dev-mode setup, see [`DOCKER.md`](DOCKER.md).

5. **Open the app** — `http://localhost:3000` — log in with `dev` / `dev`.

---

## Dev Mode Entry Point

If you're an agent helping a developer:

1. Read the Project Structure section above.
2. Read the [Backend README](backend/README.md) and [Frontend README](frontend/README.md).
3. Ask the user: **"What do you want to change today?"**

### Running the Stack for Development

Run DB and backend in Docker, frontend locally — recommended for hot reload on both sides:

```bash
docker compose up -d db backend   # db + backend in Docker (backend hot-reloads via bind mount)
cd frontend && npm run dev         # frontend locally with hot reload
```

Frontend: `http://localhost:3000` — Backend: `http://localhost:8000`

See [`DOCKER.md`](DOCKER.md) for rebuild workflows and full Docker reference.

---

## Build Commands

### Backend
```bash
cd backend
uv sync --extra test          # install dependencies
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest tests/
uv add <package>              # add a dependency
```

### Frontend
```bash
cd frontend
npm install
npm run dev
npm run lint
npm run build
```

### Full stack
```bash
docker compose up -d              # non-dev: runs db + backend + frontend
docker compose logs -f backend
docker compose build --no-cache
```

### Dev mode (recommended)
```bash
docker compose up -d db backend   # db + backend in Docker (backend hot-reloads)
cd frontend && npm run dev         # frontend locally with hot reload
```

For Docker setup, rebuild workflow, and debugging, see [`DOCKER.md`](DOCKER.md).

---

## Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions.

---

## Dev Rules

### Backend
- **Always use `uv`, not `pip`** — `pip install` will not respect the project's lockfile
- All DB operations go through `backend/src/common/database/repositories/` — no raw SQL in routes
- LLM calls: use `generate_structured()` with a Pydantic response model
- Track LLM costs with `CostTracker`; update `job.prompt_tokens` and `job.total_cost`
- Store prompts as Markdown in `backend/src/common/prompts/templates/`, render via `render_template()`
- Type hints on every function; Google-style docstrings
- **Nemotron**: the first call to sample Nemotron personas downloads ~148K rows and caches to `~/.cache/huggingface/`. Slow + uses disk on first run. Warn the user before triggering it.

### Backend — Testing
- Before writing a new test, check `backend/tests/conftest.py` for existing fixtures — add shared fixtures there, not in individual test files
- Don't make tests too granular — test meaningful behaviours, not every internal function call. Strike a balance between coverage and maintainability.
- Unit tests: `backend/tests/unit/` — mock LLM calls with `@patch`
- Integration tests: `backend/tests/integration/` — in-memory SQLite + FastAPI `TestClient`

### Frontend
- No `fetch()` calls — use `frontend/lib/api.ts`
- No global state — local `useState` + callback props only
- Always return cleanup from `useEffect` intervals: `return () => clearInterval(id)`
- MUI `sx` prop with theme vars — no inline colors; check `frontend/lib/theme.tsx` for existing colour tokens before adding new styles
- For design guidance or UI pattern questions, refer to [Vercel Design Guidelines](https://vercel.com/design/guidelines)

---

## Git Rules

- Never push directly to `main`
- Never use `--force` (or `--force-with-lease` without explicit user confirmation)
- Conventional commit prefixes scoped by area:
  - `feat(backend):`, `feat(frontend):`
  - `fix(backend):`, `fix(frontend):`
  - `chore:`, `refactor(backend):`, `refactor(frontend):`, `docs:`
- All changes go through pull requests

---

## Issue Tracking (Beads)

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and available commands.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

Use `bd` for task tracking. Do not use markdown TODO lists.

---

## If Anything Is Unclear

Ask the user via your host's clarification mechanism — **never guess**.

## Tone

Speak concisely. Avoid jargon. If explaining something technical, use plain language and short sentences.
