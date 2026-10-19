# Authentication security

Milestone 03 uses server-side PostgreSQL sessions. It implements no OAuth, JWT,
workspace authorization, email verification, password reset, or account recovery.

## API contract

All paths are under `/api/v1/auth`. Successful user responses contain exactly `id`,
`email`, `display_name`, `is_active`, and `created_at` (UTC timestamp).

| Method/path | JSON input | Success | Expected failures |
| --- | --- | --- | --- |
| POST /register | email, display_name, password | 201 safe user; no automatic login | 409 duplicate; 422 invalid; 429 rate limit |
| POST /login | email, password | 200 safe user and session Set-Cookie | 401 generic credentials/status failure; 422 invalid; 429 rate limit |
| POST /logout | none | 204; revoke current session and clear cookie | 401 absent/invalid session |
| GET /me | none | 200 safe user; update last-used time | 401 absent/invalid/expired/revoked/inactive |

Browser POSTs also return 403 on CSRF failure, untrusted Origin, or required HTTPS
missing. Cross-origin read requests from untrusted origins return 403. CORS preflight
from untrusted origins fails with 400. Authentication responses use Cache-Control:
no-store. Validation errors omit input and context so invalid passwords are not echoed.

## Passwords and identities

`argon2-cffi` supplies Argon2id secure hashing and verification with its maintained
RFC 9106 low-memory defaults (64 MiB, three iterations, parallelism four). Successful
login rehashes when parameters need updating. Registration accepts 12–128 characters;
login accepts 1–128 to support legacy hashes. Passwords are not trimmed or transformed.
Request passwords use SecretStr, and neither hashes nor passwords are returned/logged.
SQLAlchemy hides SQL parameters. Deployment logging/APM must not capture request bodies,
Cookie/Set-Cookie headers, or database credentials. Unknown/passwordless users undergo
a dummy verification; all failed credential/status checks use the same 401 message.

Emails are trimmed, validated without DNS requests, converted to ASCII domain form,
and lowercased. Non-ASCII local parts are rejected. A unique PostgreSQL expression
index rejects case/space conflicts even for concurrent requests. Existing conflicting
identities abort migration and require an explicit operator resolution; no merge occurs.
Duplicate registration returns 409 and thus reveals registration status by design.

## Session lifecycle

Each login generates 32 random bytes using `secrets.token_urlsafe(32)`. Only SHA-256
of the token is stored. Tokens contain no identity data. The raw token is sent exclusively
in an HTTP-only cookie with SameSite=Lax, Path=/, and no Domain. Production uses Secure
and the `__Host-evidenceai_session` name. Local explicit HTTP mode uses
`evidenceai_session`. Cookies have no persistence expiry; server-side expiry is absolute
and configurable (default 24 hours). Browser session restore can retain session cookies;
server expiry remains authoritative. Login always generates a new token.

`/me` verifies token format/digest, active user, revocation and expiry against the database.
Last-used tracking never slides expiry. Logout revokes the current session and clears
the cookie with matching attributes. Other devices remain signed in. No plaintext token
is stored in PostgreSQL or localStorage. Revoke all sessions operationally when an account
is compromised; there is no public revoke-all endpoint in this milestone.

## Browser, CSRF, and CORS

Use Next.js `http://localhost:3000` and API `http://localhost:8000` for development.
These are different origins and the same site. Use fetch `credentials: "include"`
for every auth call. Every state-changing request requires an exact trusted Origin plus
`X-CSRF-Protection: 1`. Browser code cannot set Origin manually. Requiring a custom header
forces a CORS preflight; credentialed CORS allows only configured exact origins, GET/POST,
and Content-Type/X-CSRF-Protection. No wildcard origins, regex reflection, or wildcard
credential policy exists. Login and registration are protected too, preventing login CSRF.
Requests without Origin are rejected for writes, including CLI clients unless they supply
it. CLI clients must also supply the custom header. No separate CSRF token endpoint is
needed for this strategy. SameSite is defense in depth, not the sole CSRF protection.

```javascript
await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  credentials: "include",
  headers: {"Content-Type": "application/json", "X-CSRF-Protection": "1"},
  body: JSON.stringify({email, password})
});
```

Keep the hostname consistent; mixing localhost and 127.0.0.1 breaks the site/cookie
assumptions. Cookies do not isolate ports, so use trusted local services. Production
must use HTTPS on the same site (e.g. app.example.com/api.example.com), or a same-origin
reverse proxy, with explicit trusted frontend origins. Cross-site deployment with
unrelated registrable domains is unsupported by the Lax cookie policy. No frontend files
or Next.js proxy changes are necessary for this API milestone.

## Environment and deployment

| Setting | Default / requirement |
| --- | --- |
| APP_ENV | development; production/staging enforce HTTPS origins |
| DATABASE_URL | Required PostgreSQL URL; backend only |
| AUTH_ALLOW_INSECURE_HTTP | false; true permitted only in development/test |
| TRUSTED_FRONTEND_ORIGINS | JSON array, default ["http://localhost:3000"]; production must override with HTTPS origins |
| SESSION_TTL_SECONDS | 86400; range 60–2592000 |
| AUTH_RATE_LIMIT | 20; range 1–10000 attempts per socket IP per endpoint/window |
| AUTH_RATE_WINDOW_SECONDS | 300; range 1–86400 |

For local HTTP, explicitly set AUTH_ALLOW_INSECURE_HTTP=true in the backend .env;
the tracked example opts in, the application default does not. Production/staging
reject that option and reject HTTP frontend origins. The server rejects unsafe requests
on HTTP whenever Secure cookies are enabled. Terminate TLS at a trusted proxy or Uvicorn;
set forwarding trust only to controlled proxy addresses. Run directly accessible Uvicorn
with `--no-proxy-headers`. The limiter reads `request.client.host` and never parses
Forwarded/X-Forwarded-For. Uvicorn may rewrite that value if proxy headers are enabled;
never use `--forwarded-allow-ips='*'` on an untrusted network. Proxies must strip supplied
forwarding headers and set their own. Otherwise client IP spoofing defeats rate limits.

## Rate limiting and operational limits

Login and registration use atomic, database-backed fixed-window counters before credential
work, including malformed attempts. Failed logins and duplicate registrations consume
the budget. Reaching it returns 429 and Retry-After. All workers must use the same database.
An in-memory limiter would lose counters on restart and grant separate budgets per worker;
PostgreSQL is the shared storage implemented here. Redis atomic counters would be an
alternative at higher scale. PostgreSQL failures fail closed.

Per-IP limiting can affect shared NAT users; distributed botnets can bypass an individual
IP budget. Fixed windows permit bursts around boundaries. Production also needs ingress
connection/body limits and distributed abuse monitoring; add shared account/network
budgets or progressive challenges as abuse patterns require. This milestone does not
add a background retention job: schedule reviewed cleanup of old rate windows and
expired/revoked sessions before large-scale rollout. No cleanup runs automatically.
A request already authenticated when logout/deactivation occurs may complete; future
requests are rejected. No email verification or MFA is implemented.

## Verification

From apps/api, activate `.venv`, install requirements, review the additive migration,
and run `python -m alembic upgrade head`, `python -m pytest -q`,
`python -m alembic heads`, `python -m alembic current`, `python -m alembic check`, and
`python -m pip check`. Tests use real PostgreSQL and TestClient with get_db overrides
and the existing outer-transaction/savepoint isolation. CI should use a separate migrated
database. Tests never truncate/delete existing rows. Existing health/model/config tests
are retained. No warning filters hide the existing Starlette/httpx deprecation warning;
httpx2 transport migration remains a separate compatibility task.

References: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[Starlette CORS](https://www.starlette.io/middleware/#corsmiddleware).
