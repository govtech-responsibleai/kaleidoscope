---
sidebar_position: 3
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
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=change-me
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
ALLOWED_EMAIL_DOMAINS=gov.sg,tech.gov.sg
```

`JWT_SECRET_KEY` signs auth tokens and encrypts stored credentials. `ADMIN_API_KEY` protects the admin API. `SEED_ADMIN_USERNAME` and `SEED_ADMIN_PASSWORD` can create the first admin user on startup. Google Sign-In is optional and requires both backend and frontend client ID variables plus `ALLOWED_EMAIL_DOMAINS`.

For production, generate strong random values:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

For full setup, including first login, Google Sign-In, creating users, and demo target seeding, see [Authentication](./2_authentication.md).

## Demo Target Seed

```bash
DEMO_TARGET_NAME=Demo Chatbot
DEMO_TARGET_AGENCY=GovTech Singapore
DEMO_TARGET_PURPOSE=A short description of what this demo chatbot helps users do.
DEMO_TARGET_TARGET_USERS=Describe the intended users for this demo chatbot.
DEMO_TARGET_ENDPOINT=https://example.com/chat
DEMO_TARGET_RESPONSE_PATH=answer
DEMO_TARGET_RETRIEVED_CONTEXT_PATH=sources
DEMO_TARGET_BODY_TEMPLATE={"question":"{{prompt}}"}
DEMO_TARGET_HEADERS={"Content-Type":"application/json","X-API-Key":"<secret-from-private-env>"}
```

These variables configure the optional starter target created for new Google-auth users. They only apply when `DEMO_TARGET_ENDPOINT` is set. See [Authentication](./2_authentication.md#initial-demo-target-for-google-users) for details.

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
