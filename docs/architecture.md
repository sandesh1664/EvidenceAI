# Architecture

The existing Next.js frontend and FastAPI health endpoint remain unchanged. The
backend foundation uses synchronous SQLAlchemy typed models, Psycopg 3, PostgreSQL
17 and Alembic. pgvector is installed but unused. Authentication, tenant authorization,
CRUD, storage, chunks, embeddings, conversations, citations, and evaluations are planned.

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
a committed row disappears after outer rollback. No tables are truncated or dropped.
Use a separate migrated database in CI. Missing connectivity fails tests, rather than
skipping them. Commands are in the root README.

## Security and compatibility

Backend `.env` is ignored and the example contains placeholders. The existing Compose
password is for local development only; provision secret management, least-privilege
credentials and TLS for deployment. Do not expose ORM objects directly as API responses.
No authentication or upload routes exist. Nullable password_hash is reserved for future
secure authentication. Document contents belong in separate private storage.

Python 3.14.6 and the pinned dependencies passed the suite; pip check found no broken
requirements. Installed Starlette 1.9.0 TestClient source and package metadata recommend
httpx2>=2.0.0 and emit a deprecation warning for the current httpx transport. The health
test passes with that warning visible. Dependencies were preserved; validate a transport
upgrade separately. No warnings are filtered.

Next milestone: atomic workspace services, normalized identities, authorization-aware
CRUD and owner-membership enforcement, followed by authenticated upload/storage.
