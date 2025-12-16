# Docker Setup

## Prerequisites

- Docker
- Docker Compose
- `.env` file with your API keys

## Quick Start

### 1. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY or ANTHROPIC_API_KEY
```

### 2. Start services

```bash
docker-compose up -d
```

This will:
- Start PostgreSQL database on port 5432
- Start API service on port 8000
- Wait for database to be healthy before starting API
- Create necessary database tables automatically

### 3. Verify services are running

```bash
docker-compose ps
```

### 4. Check API

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Common Commands

### View logs

```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Database only
docker-compose logs -f db
```

### Stop services

```bash
docker-compose down
```

### Restart services

```bash
docker-compose down
docker-compose up -d
```

### Rebuild after code changes

```bash
docker-compose build
docker-compose up -d
docker-compose up -d --build  # one-shot rebuild + start
```

## Running Tests

### Run all tests

```bash
docker-compose --profile test up test --abort-on-container-exit
docker-compose --profile test down
```

### Run unit tests only

```bash
docker-compose --profile test run --rm test pytest -v -m unit
```

### Run integration tests only

```bash
docker-compose --profile test run --rm test pytest -v -m integration
```

## Database Access

### Connect to PostgreSQL

```bash
docker-compose exec db psql -U kaleidoscope -d kaleidoscope
```

### Run SQL queries

```bash
docker-compose exec db psql -U kaleidoscope -d kaleidoscope -c "SELECT * FROM targets;"
```

## Shell Access

### API container shell

```bash
docker-compose exec api /bin/bash
```

### Database shell

```bash
docker-compose exec db /bin/sh
```

## Development

The API container mounts your local `src/` and `tests/` directories, so:
- **Code changes are reflected immediately** (hot reload enabled)
- No need to rebuild for code changes
- Only rebuild if you change `requirements.txt`

## Cleanup

### Stop and remove containers

```bash
docker-compose down
```

### Remove volumes (database data)

```bash
docker-compose down -v
```

### Full cleanup

```bash
docker-compose down -v
docker system prune -f
```

## Troubleshooting

### Database connection errors

Check if database is healthy:
```bash
docker-compose ps
```

View database logs:
```bash
docker-compose logs db
```

### API not starting

View API logs:
```bash
docker-compose logs api
```

Common issues:
- Missing `OPENAI_API_KEY` in `.env`
- Database not ready (wait 5-10 seconds)

### Port conflicts

If ports 8000 or 5432 are already in use, edit `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # API on port 8001
  - "5433:5432"  # Database on port 5433
```

## Production Deployment

For production:

1. Change database password in `docker-compose.yml`
2. Update CORS settings in `src/main.py`
3. Use production database (not Docker)
4. Add proper secrets management
5. Use environment-specific `.env` files
