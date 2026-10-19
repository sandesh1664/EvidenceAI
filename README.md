# EvidenceAI

EvidenceAI is a document intelligence and research platform. Milestone 04 adds authenticated workspace management and role-based membership
authorization to the existing database-backed authentication system. Document ingestion and AI research are planned.

## Development

The existing frontend is in `apps/web` (Next.js/TypeScript/Tailwind). The backend is
in `apps/api` (Python 3.14, FastAPI, synchronous SQLAlchemy, Psycopg 3, Alembic).
PostgreSQL 17 with pgvector runs through `infra/docker-compose.yml`, bound to
`127.0.0.1:5433`. Preserve the existing Docker volume.

```sh
docker compose -f infra/docker-compose.yml up -d
cd apps/api
source .venv/bin/activate
python -m pip install -r requirements.txt
# For a new checkout only: copy .env.example to .env and replace placeholders.
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --no-proxy-headers
```

The existing `/api/v1/health` endpoint is a lightweight liveness check, independent
of database configuration and connectivity. It is not database readiness.

## Database commands

Run from `apps/api` with its virtual environment activated:

```sh
python -m alembic current
python -m alembic heads
python -m alembic check
python -m alembic revision --autogenerate -m "Describe schema change"
python -m alembic upgrade head --sql
# Review the generated migration and SQL before applying:
python -m alembic upgrade head
python -m pytest -q
```

Tests require a migrated PostgreSQL database. Ordinary tests roll back an outer
transaction; session commits use savepoints. Concurrency tests create independently
committed data only in uniquely named `test_workspace_<UUID>` schemas, then remove
those disposable schemas. Public application tables are never reset or truncated.
The test DB role needs CREATE SCHEMA permission for concurrency tests. Use an isolated database for CI; set `DATABASE_URL`
to its PostgreSQL URL, migrate it, then run pytest. Database connection failures
fail tests rather than silently skipping coverage. Do not execute tests concurrently
with schema migrations. Test configuration can use `Settings(_env_file=None, ...)`.

[Architecture](docs/architecture.md) and [database design](docs/database-design.md)
cover settings, relationships, deletion policy, security, and current limitations.

## Authentication

See [security](docs/security.md) for API contracts, environment settings, browser
integration, deployment requirements, and session lifecycle. No frontend files changed.
For local HTTP, explicitly set `AUTH_ALLOW_INSECURE_HTTP=true` in `apps/api/.env`
and `TRUSTED_FRONTEND_ORIGINS=["http://localhost:3000"]`. Without the opt-in,
cookies are Secure and writes require HTTPS even in development.
Run local Uvicorn with `--no-proxy-headers` so untrusted forwarding headers cannot
change the client IP used for rate limiting.

Next.js on `http://localhost:3000` calls `http://localhost:8000/api/v1/auth/...`
with `credentials: "include"`. Every POST/PATCH/DELETE requires `Content-Type: application/json`,
`X-CSRF-Protection: 1`, and the browser's trusted Origin. Use `localhost` consistently
for both services. Cookies are host scoped, so use dedicated development hosts and
trusted services. Production requires HTTPS and an explicit HTTPS origin allowlist.

Migration `a31f8c9d204e` adds two auth tables and a normalized unique email index.
It refuses conflicting legacy identities; resolve those explicitly before rerunning.
It does not rewrite existing users. Review it before `python -m alembic upgrade head`.
The original migration is unchanged. Tests use TestClient and real PostgreSQL with
rollback isolation; no records are deleted or tables reset.

## Workspace management

Authenticated endpoints under `/api/v1/workspaces` create/list/read/update/delete
workspaces, manage existing users' memberships, and transfer ownership. See the
[API specification](docs/api-specification.md) for all request/response formats,
permissions, pagination, and errors. Read access requires membership; owners/admins
manage ordinary members, while only the designated owner can transfer or delete.
Creation and transfer preserve exactly one matching owner membership in a transaction.
An empty workspace can be deleted with its mandatory owner membership; other members
or any documents cause 409. No users or documents are cascade-deleted.

Milestone 04 needs no schema migration: the current head remains `a31f8c9d204e`.
Run `python -m pytest -q`, `python -m alembic current`, `python -m alembic check`,
`python -m pip check`, and `git diff --check` to verify. Authenticated TestClient tests
cover tenant isolation, roles, CSRF, rollback, and actual PostgreSQL lock contention.
The frontend, uploads, invitations, and AI features are outside this milestone.
