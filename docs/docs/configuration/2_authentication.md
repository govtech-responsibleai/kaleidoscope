---
sidebar_position: 2
title: Authentication
---

# Authentication

Kaleidoscope supports password login for local development and team deployments. Google Sign-In is optional.

## First login

For local development, the default secrets create an admin user on first startup:

```bash
JWT_SECRET_KEY=dev-jwt-secret
ADMIN_API_KEY=dev-admin-key
```

Sign in at [http://localhost:3000](http://localhost:3000) with:

```bash
Username: dev
Password: dev
```

For production, do not use the dev defaults. Set strong values for `JWT_SECRET_KEY` and `ADMIN_API_KEY`, then seed the first admin user:

```bash
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=change-me
```

Both seed variables must be set. The seed is idempotent: if the username already exists, Kaleidoscope does not recreate it or change its password.

You can also create the first admin account with the admin API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{"username": "admin", "password": "your-password", "is_admin": true}'
```

## Google Sign-In

Google Sign-In is optional. To enable it, create an OAuth 2.0 Client ID in Google Cloud Console, then set the same client ID for the backend and frontend:

```bash
GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
ALLOWED_EMAIL_DOMAINS=gov.sg,tech.gov.sg
```

`ALLOWED_EMAIL_DOMAINS` is required for Google Sign-In. It uses exact domain matching, so `gov.sg` does not include `agency.gov.sg`. Leave it empty to reject all Google sign-ins.

When Google auth is not configured, password login still works. The frontend hides the Google Sign-In button when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is empty, and the backend rejects direct Google login calls when no allowed domains or backend client ID are configured.

Google-auth users are created on first successful sign-in. These accounts do not have passwords, so they must continue signing in with Google unless an admin creates a separate password-based account.

## Creating users

After signing in as an admin, open the Administration page to create password-based users from the UI.

You can also create users with the admin API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/admin/create-user \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-admin-key" \
  -d '{"username": "alice", "password": "pass123", "is_admin": false}'
```

Set `"is_admin": true` only for users who should manage other accounts.

## Initial demo target for Google users

You can automatically create a starter HTTP target for each new Google-auth user by setting `DEMO_TARGET_ENDPOINT` and the related `DEMO_TARGET_*` variables:

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

This only runs when `DEMO_TARGET_ENDPOINT` is set, and only for users created through Google Sign-In. Replace the example metadata, endpoint, response path, body template, and headers with values for your own demo target before sharing it with users.
