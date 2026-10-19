# Architecture

The existing Next.js frontend and FastAPI health endpoint remain unchanged. The
backend foundation uses synchronous SQLAlchemy typed models, Psycopg 3, PostgreSQL
17 and Alembic. pgvector is installed but unused. Workspace management and membership-based tenant
access are implemented. Uploads, storage, chunks, embeddings, conversations, citations,
and evaluations remain planned.

## Configuration and connections

`app/core/config.py` reads APP_NAME (default EvidenceAI API), APP_ENV (development,
test, staging, production), and mandatory DATABASE_URL. Process variables override
`apps/api/.env`, resolved independently of the working directory. Configuration tests
can disable dotenv with `Settings(_env_file=None, ...)`. Unsupported environments,
invalid PostgreSQL URLs, and missing hosts/databases fail validation. Plain PostgreSQL
URLs are normalized to Psycopg 3. URLs are secret values hidden from settings repr
and validation errors. APP_NAME is available to configured consumers; the existing
health response retains its stable service name and needs no database configuration.

Settings, engine, and session factory are lazy and cached. Importing modules opens
no database connection. `get_db` yields a session and always closes it; errors trigger
rollback. Callers explicitly commit successful writes. Closing rolls back pending work.
SQL parameter logging is hidden. Do not print secret values or unredacted connection
exceptions. Future route tests can override get_db with isolated sessions.

## Migrations and tests

Alembic registers all models and owns schema changes. No application create_all runs.
Autogeneration excludes unrelated reflected tables from proposed drops; always review
migrations and SQL before applying. Managed table changes still require careful review.
Initial revision `6cc0ce3f2778` creates the four application tables and leaves pgvector
and the Docker volume intact. Downgrading destroys these tables; do not downgrade a
populated database without a recovery plan.

Tests use PostgreSQL transactions with externally owned outer transactions and
`join_transaction_mode="create_savepoint"` sessions. Commits/rollbacks operate within
savepoints; fixture cleanup rolls back the outer transaction. A dedicated test proves
a committed row disappears after outer rollback. No public application tables are truncated or dropped.
Use a separate migrated database in CI. Missing connectivity fails tests, rather than
skipping them. Commands are in the root README.

## Security and compatibility

Backend `.env` is ignored and the example contains placeholders. The existing Compose
password is for local development only; provision secret management, least-privilege
credentials and TLS for deployment. Do not expose ORM objects directly as API responses.
Authentication is implemented in Milestone 03; upload routes remain planned.
Nullable password_hash supports legacy users; passwordless records cannot log in. Document contents belong in separate private storage.

Python 3.14.6 and the pinned dependencies passed the suite; pip check found no broken
requirements. Installed Starlette 1.9.0 TestClient source and package metadata recommend
httpx2>=2.0.0 and emit a deprecation warning for the current httpx transport. The health
test passes with that warning visible. Dependencies were preserved; validate a transport
upgrade separately. No warnings are filtered.

Next milestone: authenticated upload/storage with document-level workspace checks.

## Milestone 03 authentication

Routes in `app/api/routes/auth.py` expose `/api/v1/auth/register`, `/login`, `/logout`,
and `/me`. Pydantic request/response schemas are in `app/schemas/auth.py`.
`app/services/auth_service.py` owns registration, credential verification, rate limits,
and session lookup. `app/core/security.py` owns Argon2id and random-token primitives.
`app/core/browser_security.py` applies trusted-Origin checks, custom-header CSRF,
credentialed CORS and no-store responses. Settings remain lazy so health checks
need neither database settings nor connectivity.

The reusable `get_current_user` FastAPI dependency rejects missing, invalid, expired,
revoked sessions and inactive accounts. It returns a User for application services;
only explicit safe schemas cross the API boundary. Future state-changing API routes
inherit the browser middleware and must declare this dependency for authentication.
CSRF checks alone do not authorize users or workspace access.

Login creates a fresh opaque 256-bit token and stores its SHA-256 digest with user ID,
creation time and absolute expiry. The browser receives the raw token only through
an HTTP-only host cookie; JavaScript receives safe user fields. `/me` updates last use
without extending expiry. Logout timestamps revocation and expires the same cookie.
Other devices remain signed in. Authentication attempts are counted atomically in
PostgreSQL and committed before credential handling so failures consume the budget.
Each subsequent write commits explicitly; IntegrityError causes registration rollback.
See [security](security.md) for browser and deployment contracts.

## Milestone 04 workspaces and membership

`app/api/routes/workspaces.py` and `workspace_members.py` use the existing
`get_current_user` dependency on every endpoint. Authentication completes and records
session use before workspace work starts. No endpoint substitutes caller-supplied users
or trusts owner/role fields outside the explicit schemas. `app/schemas/workspace.py`
and `workspace_member.py` define safe responses, bounded payloads, and validated UUIDs.
Workspace and membership listings are paginated, ordered, and membership-filtered.

`app/core/authorization.py` centralizes access checks and role rules. Read queries
require a membership join. Missing and inaccessible workspaces both return 404 with
`Workspace not found`. Mutation services acquire a workspace `SELECT ... FOR UPDATE`
lock before loading current membership in a separate statement. Queries refresh the
Session identity map (`populate_existing=True`) so cached pre-transfer ownership or
admin roles cannot authorize a waiting request. All mutations acquire locks in this
same order and hold them through commit/rollback. This uses PostgreSQL's default
READ COMMITTED isolation; changing isolation requires a fresh concurrency review.

`app/services/workspace_service.py` creates a workspace and its owner membership in
one transaction, handles workspace updates, and permits only safe empty deletion.
`workspace_member_service.py` handles addition of active registered users, duplicate
membership conflicts, non-owner role changes/removal, and atomic ownership transfer.
Transfer changes owner_id and both membership roles together; the former owner becomes
admin. The target must already be an active registered member. General role requests
accept only admin/member. Admins may promote ordinary members to admin, but cannot
change/remove existing admins, themselves, or owners. Only owners manage existing admins.

`workspace_transaction.py` commits successful writes and rolls back failed operations.
Integrity failures become safe 409 responses. PostgreSQL deadlock, serialization, and
lock-not-available errors also become retryable 409 conflicts. Database/network failures
are not swallowed. Read and failed-auth transactions close via the existing get_db
lifecycle. Services reject inconsistent legacy owner memberships without repairing data.

No Milestone 04 migration is needed. Application services maintain the cross-row owner
invariant; existing unique membership, role checks and RESTRICT FKs remain authoritative
within their scope. Direct SQL/ORM tools must honor the same protocol; no trigger grants
arbitrary writes the service guarantees. No frontend, upload, or AI code changed.

Concurrency tests use independent connections and authenticated TestClient requests.
Each test creates only a unique disposable schema, seeds test users/sessions/workspace,
observes actual lock blocking with pg_blocking_pids, and checks the resulting owner
invariant and permission decision. Scratch schemas are removed in finally cleanup;
public data is untouched. Other new and existing tests retain rollback isolation.
Use a dedicated CI database whose role can create test schemas.

Reference: [PostgreSQL 17 row locking](https://www.postgresql.org/docs/17/explicit-locking.html).
