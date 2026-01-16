"""Generate a secret key. Run once for each key needed."""

import secrets

key = secrets.token_urlsafe(32)
print(key)
