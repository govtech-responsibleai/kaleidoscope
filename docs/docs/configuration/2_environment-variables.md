---
sidebar_position: 2
title: Environment Variables
---

# Environment Variables

Kaleidoscope is configured via a `.env` file in the project root. Copy `.env.example` to get started:

```bash
cp .env.example .env
```

## Database

```bash
DATABASE_URL=postgresql://kaleidoscope:kaleidoscope_dev_password@db:5432/kaleidoscope
```

When running with Docker, use `db` as the host (the container name). For local development without Docker, use `localhost`.

## Authentication

```bash
JWT_SECRET_KEY=dev-jwt-secret
ADMIN_API_KEY=dev-admin-key
```

`JWT_SECRET_KEY` is used for signing auth tokens and encrypting stored credentials. `ADMIN_API_KEY` is required to create user accounts via the API.

For local development, the defaults (`dev-jwt-secret` / `dev-admin-key`) work out of the box and you can sign in with `dev` / `dev`.

For production, generate strong random values:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Creating the first admin account

When deploying for the first time, create an admin account using your `ADMIN_API_KEY`:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{"username": "admin", "password": "your-password", "is_admin": true}'
```

Once signed in as an admin, you can create additional users from the UI.

## LLM Provider Keys

```bash
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
# etc.
```

Keys set here become shared credentials available to all users. See [LLM Providers](./1_providers.md) for the list of default providers and their environment variables.

## Extensions

```bash
KALEIDOSCOPE_EXTENSIONS=aibots
```

Comma-separated list of connector extensions to load at startup. Each extension registers an additional connector type that appears as an option when configuring a target's endpoint. Leave empty if you only need the built-in HTTP connector.

Extensions live in [`backend/src/extensions/`](https://github.com/govtech-responsibleai/kaleidoscope/tree/main/backend/src/extensions). Each extension is a Python module with a `register()` function that adds its connector to the registry. See the built-in [`aibots`](https://github.com/govtech-responsibleai/kaleidoscope/tree/main/backend/src/extensions/aibots) extension for a reference implementation of a custom connector.

## Langfuse (Observability)

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

When configured, all LLM calls made during scoring and generation are automatically traced in Langfuse. Optional - leave unset to disable.

## Log Level

```bash
LOG_LEVEL=INFO
```

Set to `DEBUG` to see per-call LLM request and response details. Useful for troubleshooting provider issues.

## Backend API URL

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

When running with Docker, the default `http://localhost:8000/api/v1` works for local development. For production, replace with your deployed backend URL (e.g. `https://api.your-domain.com/api/v1`).
