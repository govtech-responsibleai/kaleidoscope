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

## Self-signup with an email whitelist

You can let invited users create their own password-based accounts without an admin, gated by an editable email whitelist file. This is independent of Google Sign-In — a whitelisted user signs up with an email and password and then logs in through the normal password form.

Point `SIGNUP_WHITELIST_PATH` at a plain-text file and add one invited email per line (blank lines and lines starting with `#` are ignored):

```bash
SIGNUP_WHITELIST_PATH=backend/signup_whitelist.txt
```

```text
# signup_whitelist.txt
alice@partner.org
bob@example.com
```

The file is re-read on every signup attempt, so you can add or remove emails while the app is running — no restart needed. Matching is case-insensitive on the full email address.

On the login page, invited users click **Sign up**, enter their email and a password, and are signed in immediately. New accounts are non-admin and receive the demo target (see below) just like Google users.

Behaviour:

- Email not in the whitelist → the signup is rejected with a clear "not invited" message.
- Email already registered → the signup is rejected; the user should sign in instead.
- Whitelist file missing or unreadable → **all** signups are rejected (fail closed) and the backend logs a warning that self-registration is disabled. Google Sign-In and password login are unaffected.

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

## Initial demo target for new users

You can automatically create a starter HTTP target for each new user — whether they arrive through Google Sign-In or self-signup — by setting `DEMO_TARGET_ENDPOINT` and the related `DEMO_TARGET_*` variables:

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

This only runs when `DEMO_TARGET_ENDPOINT` is set, and applies to users created through Google Sign-In and self-signup. Replace the example metadata, endpoint, response path, body template, and headers with values for your own demo target before sharing it with users.
