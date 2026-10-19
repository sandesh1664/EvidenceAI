# EvidenceAI

EvidenceAI is a document intelligence and research platform. Milestone 02 implements
the PostgreSQL database foundation. Authentication, document ingestion, AI research,
chunks, embeddings, conversations, citations, and evaluations are planned.

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
python -m uvicorn app.main:app --reload
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

Tests require a migrated PostgreSQL database. They never create/drop application
tables or truncate data: each database test rolls back an outer transaction, and
session commits use savepoints. Use an isolated database for CI; set `DATABASE_URL`
to its PostgreSQL URL, migrate it, then run pytest. Database connection failures
fail tests rather than silently skipping coverage. Do not execute tests concurrently
with schema migrations. Test configuration can use `Settings(_env_file=None, ...)`.

[Architecture](docs/architecture.md) and [database design](docs/database-design.md)
cover settings, relationships, deletion policy, security, and current limitations.
