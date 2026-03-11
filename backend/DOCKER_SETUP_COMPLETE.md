# Docker Setup Complete ✅

## What Was Created

### Docker Files
- ✅ **`Dockerfile`** - API container definition
- ✅ **`docker-compose.yml`** - Multi-service orchestration (DB + API + Tests)
- ✅ **`.dockerignore`** - Optimized build context
- ✅ **`DOCKER.md`** - Comprehensive Docker usage guide

### Main API Entry Point
- ✅ **`src/main.py`** - Root API that includes all services
  - Currently includes: Query Generation (personas, questions)
  - Ready for: Scoring service, other future services
  - All services share same `/api/v1` prefix

### Docker Compose Services

1. **`db`** - PostgreSQL 16
   - Port: 5432
   - User: kaleidoscope
   - Database: kaleidoscope
   - Health check enabled
   - Persistent volume

2. **`api`** - Kaleidoscope API
   - Port: 8000
   - Auto-reloads on code changes
   - Mounts local `src/` and `tests/`
   - Waits for DB to be healthy

3. **`test`** - Test runner (profile: test)
   - Runs pytest in isolated environment
   - Uses same DB service

## Quick Start

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env: Add your API keys + JWT_SECRET_KEY + SERPER_API_KEY (see README.md for auth setup)

# 2. Start services
docker-compose up -d

# 3. Create a user (after services are running, requires ADMIN_API_KEY in .env)
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "X-Admin-Key: <your-admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"username": "<username>", "password": "<password>", "is_admin": false}'

# 4. Check status
docker-compose ps

# 5. View logs
docker-compose logs -f api
```

**API Available at:**
- http://localhost:8000
- http://localhost:8000/docs (Interactive API docs)

## Run Tests

```bash
# All tests
docker-compose --profile test up test --abort-on-container-exit
docker-compose --profile test down

# Unit tests only
docker-compose --profile test run --rm test pytest -v -m unit

# Integration tests only
docker-compose --profile test run --rm test pytest -v -m integration
```

## Architecture

```
┌─────────────────────────────────────────┐
│          Docker Compose                 │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────┐       ┌──────────┐      │
│  │   API    │◄──────┤    DB    │      │
│  │  :8000   │       │  :5432   │      │
│  └──────────┘       └──────────┘      │
│       │                                 │
│       │                                 │
│  ┌──────────┐                          │
│  │   Test   │                          │
│  │ (profile)│                          │
│  └──────────┘                          │
│                                         │
└─────────────────────────────────────────┘
```

## Features

✅ **Consistent API endpoint** - All services under `/api/v1`
✅ **Hot reload** - Code changes reflected immediately
✅ **Isolated database** - PostgreSQL in container
✅ **Health checks** - Proper service startup order
✅ **Test isolation** - Tests run in separate container
✅ **Volume persistence** - Database data persists across restarts
✅ **Easy cleanup** - `docker-compose down -v`

## Adding New Services

To add a new service module:

1. Create service in `src/<module_name>/`
2. Add routes in `src/<module_name>/api/routes/`
3. Import and include router in `src/main.py`:

```python
from src.<module_name>.api.routes import <resource>
app.include_router(<resource>.router, prefix=f"{settings.api_prefix}/<resource>", tags=["<Module>"])
```

That's it! No Docker changes needed - same container, same endpoint.

## Current Services

- **Query Generation**: Persona generation, question generation (with input style variants and web search context), similarity detection
- **Scoring**: Claim-based and response-level judge evaluation, QA job orchestration, annotations, metrics

## Next Steps

1. **Start services**: `docker-compose up -d`
2. **Run tests**: `docker-compose --profile test up test --abort-on-container-exit`
3. **Test API manually**: Use http://localhost:8000/docs

See [DOCKER.md](DOCKER.md) for all Docker commands.
