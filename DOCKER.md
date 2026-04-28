# Docker

## Services

| Service | Image | Port |
|---------|-------|------|
| `db` | postgres:16-alpine | 5432 |
| `backend` | built from `backend/Dockerfile` | 8000 |
| `frontend` | built from `frontend/Dockerfile` | 3000 |

## Common Commands

```bash
docker compose up -d                  # start all services
docker compose down                   # stop and remove containers
docker compose down -v                # also wipe the postgres volume

docker compose logs -f backend        # stream backend logs
docker compose build --no-cache       # rebuild images from scratch

docker compose exec backend bash      # shell into backend container
docker compose exec db psql -U kaleidoscope kaleidoscope  # postgres shell
```

## Environment Variables

Copy `.env.example` → `.env` before starting. The compose file reads `.env` for LLM API keys and secrets. `DATABASE_URL` is injected directly by compose and does not need to be set in `.env`.

## Dev Mode

For active development, run only the infra in Docker and the frontend locally:

```bash
docker compose up -d db backend   # db + backend in Docker (backend hot-reloads via bind mount)
cd frontend && npm run dev         # frontend locally with full hot reload
```

Frontend at `http://localhost:3000`, backend at `http://localhost:8000`.

## Rebuilding After Code Changes

Backend source is bind-mounted (`./backend/src:/app/src`) — Python changes reload automatically.

Frontend is **not** bind-mounted in the Docker service — use dev mode above for frontend changes. Full image rebuild otherwise:

```bash
docker compose build frontend
docker compose up -d frontend
```

Backend dependency changes (`pyproject.toml` / `uv.lock`) require a rebuild:

```bash
docker compose build backend
docker compose up -d backend
```

## Production

Rotate the default dev secrets before deploying:

```bash
# Run twice — once for JWT_SECRET_KEY, once for ADMIN_API_KEY
cd backend && uv run python scripts/generate_secret.py
```

Set the outputs as `JWT_SECRET_KEY` and `ADMIN_API_KEY` in your deployment environment.
