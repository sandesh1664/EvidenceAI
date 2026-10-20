# EvidenceAI

EvidenceAI is a document intelligence and research platform. Milestone 09 adds a responsive
web application for private workspaces, document research, source-grounded answers and
persistent conversations, connected to the existing secure FastAPI backend.

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

For real local signup email delivery, use the [local TLS mail workflow](docs/local-signup-email.md).
It preserves browser-bound verification and needs no `.env` changes.

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
.venv/bin/python ../../infra/testing/run_isolated.py -- apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

Tests require the [disposable database runner](infra/testing/README.md), which migrates
an owned temporary PostgreSQL database and fails closed if a development URL is
supplied. It never inherits the development database from `.env`. Use this runner
for backend and browser tests; do not run tests directly against the application
database. Do not execute application schema migrations concurrently with other work.

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

Milestone 04 needed no schema migration; the current head is `6f22cc4c46ad` (Milestone 08).
Run `python -m pytest -q`, `python -m alembic current`, `python -m alembic check`,
`python -m pip check`, and `git diff --check` to verify. Authenticated TestClient tests
cover tenant isolation, roles, CSRF, rollback, and actual PostgreSQL lock contention.
The frontend, invitations and AI features remain outside the current milestone.

## Document ingestion

See [document processing](docs/document-processing.md) for storage, parser limits,
queue recovery, deletion/cleanup, source metadata, retry policy and operations.
Owners/admins can upload, retry and delete documents; every workspace member can
list, view metadata and download originals. All API requests reuse session auth;
POST/DELETE still require trusted Origin and `X-CSRF-Protection: 1`.

```sh
cd apps/api
source .venv/bin/activate
python -m pip install -r requirements.txt
# Review the new migrations before applying them:
python -m alembic upgrade head
python -m app.document_worker          # separate long-running worker
# Other operational commands:
python -m app.document_worker --once   # at most one cleanup and one processing job
python -m app.document_worker --status
```

The durable queue uses PostgreSQL, so metadata and job publication share a transaction.
No Redis or Compose change is required; PostgreSQL port 5433 and its volume are unchanged.
API and workers must share the same private storage directory, defaulting to
`<project>/storage/documents`. Optional DOCUMENT_STORAGE_ROOT must be absolute and
outside the frontend. Originals are not publicly served. Local files/directories use
0600/0700. Defaults: 20 MiB/file, 500 PDF pages, 2 million extracted characters,
1600-character chunks with 200 overlap, 3 total processing attempts. Uploads return
202 pending; full extraction happens only in the separate worker. Processing and
cleanup stop when no worker is running; start and monitor it separately from Uvicorn.

Verification uses `python -m pytest -q`, `python -m alembic current`,
`python -m alembic check`, `python -m pip check`, and `git diff --check`.
Tests isolate storage and queues; real concurrency uses disposable database schemas.
No existing records, frontend files, applied migrations, or Docker volumes are reset.

## Embeddings and retrieval

See [retrieval engine](docs/retrieval-engine.md) for configuration, lifecycle, API contracts,
privacy, reindexing and measured evaluation. Embeddings are disabled by default. For
explicit offline development set EMBEDDING_PROVIDER=fake, EMBEDDING_MODEL=fake-hash-v1,
EMBEDDING_REVISION=1 and EMBEDDING_DIMENSIONS=128. The fake provider is deterministic
lexical hashing for tests, not a trained semantic model. For real semantic embeddings,
configure the hosted OpenAI provider after reviewing outbound data/privacy requirements.
No paid API is called by tests or the synthetic evaluation.

With a provider enabled, the existing `python -m app.document_worker` indexes successful
extractions automatically. Existing completed documents need an authorized POST to their
`/index` endpoint. Model/revision/dimension changes create separate profiles; reindex each
eligible document for the new configuration. No source chunks are modified by indexing.

`POST /api/v1/workspaces/{workspace_id}/search` accepts query, bounded limit and optional
document_ids, and returns authorized source excerpts/references with cosine scores.
Every workspace member may search; owners/admins enqueue, force reindex or retry indexing.
Session cookies and existing CSRF/trusted-Origin controls apply to all POSTs.

```sh
cd apps/api
source .venv/bin/activate
python -m alembic upgrade head
python -m app.document_worker
# From a separate shell:
python -m app.document_worker --status
python -m app.evaluate_retrieval --output ../../docs/retrieval-evaluation.json
```

Migration `d64a9f2b830c` adds embedding_profiles, chunk_embeddings and embedding_jobs.
It preserves source tables and pgvector. Search is exact filtered cosine, with B-tree
profile/status indexes and no HNSW approximation. The checked-in synthetic benchmark
reports Recall@2/Precision@2 0.9375, MRR@2 1.0 and isolation 10/10; it measures only the
fake lexical provider on a tiny synthetic corpus, not hosted semantic quality or scale.

## Grounded answers (Milestone 07)

POST `/api/v1/workspaces/{workspace_id}/ask` accepts a question, optional document UUIDs
and retrieval limit. Members receive source quotations with validated claim-level citations,
or explicit insufficient_evidence/retrieval_unavailable/provider_error states. Existing session
authentication and CSRF apply. This endpoint remains stateless; Milestone 08 provides separate persistent conversation APIs.

Generation defaults to disabled. For offline development use `LLM_PROVIDER=mock`,
`LLM_MODEL=mock-extractive-v1`, and the existing indexed fake embedding profile. Hosted
OpenAI generation requires its own explicit privacy opt-in and backend model/key configuration.
The hosted provider uses Responses strict structured outputs with bounded retries/timeouts.

See [RAG answer engine](docs/rag-answer-engine.md) for configuration, API examples, safeguards,
limits and the 13-case [synthetic report](docs/rag-evaluation.json). Current answers are exact
source extracts; this small mock-provider evaluation does not establish production accuracy.
Streaming is deferred until draft content can be validated safely. No new schema migration
or frontend changes were introduced by Milestone 07; Milestone 08 adds migration `6f22cc4c46ad`.

## Research conversations (Milestone 08)

Authenticated workspace members can create owner-private conversations, rename/archive them,
page ordered history, submit idempotent message turns and delete their saved research. Each
turn performs fresh authorized retrieval; old assistant answers/snapshots are never evidence.
The stateless `/ask` endpoint remains available. No frontend changes are included.

Run `python -m alembic upgrade head` from apps/api after reviewing the additive migration
`6f22cc4c46ad`. New settings: CONVERSATION_HISTORY_MESSAGES=6,
CONVERSATION_HISTORY_TOKEN_BUDGET=1500, CONVERSATION_TURN_LEASE_SECONDS=180. Providers
remain disabled unless explicitly configured. See [conversation engine](docs/conversation-engine.md)
for exact APIs, idempotency, concurrency, crash recovery and limits.

**Deleting a source document retains historical citation excerpts.** Archive retains history;
DELETE conversation permanently removes its messages/snapshots. There is no automatic TTL
or source-wide historical purge. Treat saved questions and excerpts as private data.

## Integrated web application (Milestone 09)

`apps/web` now connects to the existing FastAPI API: register/login/logout, private workspace
navigation, member roles/ownership, document uploads/status/indexing/downloads, semantic
search, source-grounded questions, saved conversations and citation snapshots. Light/dark
themes, responsive navigation, accessible forms and confirmation dialogs are included.

Run the existing API on localhost:8000 and `npm ci && npm run dev` from apps/web for
localhost:3000. Review apps/web/.env.example and the backend's exact trusted-origin/local
HTTP settings; no backend secret is copied into the frontend. Real workers must run for
processing/indexing, and provider defaults remain disabled. Profile/model settings without
backend APIs are not invented.

See [frontend setup, architecture, tests and manual checklist](docs/frontend-architecture.md).
The browser uses credentialed cookie requests and the existing CSRF header; no new auth or
private server cache is introduced. Playwright uses a separate disposable local schema and
production frontend. The full npm audit retains five high development-lint-chain findings
with no upstream braces patch; production-only audit currently reports zero. No forced
framework downgrade is used. Backend migration stays at `6f22cc4c46ad`.

## Evaluation and operations (Milestone 10)

The API and worker now emit content-free JSON telemetry and validated request IDs.
Public `/api/v1/ready` separates dependency readiness from the unchanged liveness route;
operator readiness/Prometheus metrics require a backend-only `OPERATIONS_TOKEN`.
Run `python -m app.operations`, `python -m app.document_worker --status`, or the offline
versioned regression command `python -m app.evaluate --repeat 3` from apps/api.
No database migration or monitoring deployment is required by this change.

See [observability](docs/observability.md), [evaluation](docs/evaluation-framework.md),
[operator runbook](docs/operational-runbook.md), and
[observed verification](docs/milestone-10-verification.md). Prometheus/Grafana configuration
is in `infra/monitoring`. Backend tests now confine default worker/database queries to
an owned disposable schema, allowing safe tests alongside development records.

## Deployment candidates (Milestone 11)

Production Dockerfiles, separate staging/production Compose configurations, same-origin
HTTPS routing, file-mounted secrets, private monitoring, controlled rollout/migrations and
encrypted database-plus-document backup/restore verification are available. Development
`infra/docker-compose.yml` and its PostgreSQL volume/port 5433 remain unchanged.

Start with [architecture](docs/production-architecture.md),
[deployment guide](docs/deployment-guide.md), [backup/recovery](docs/backup-and-recovery.md),
[CI/CD](docs/ci-cd.md), [production security](docs/production-security.md), and
[observed verification](docs/milestone-11-verification.md). `npm run build` now consistently
uses supported Webpack; the container serves standalone output from the same HTTPS origin.
Run the local-only infrastructure drill with `python3 infra/scripts/smoke.py` after building
the four `:m11` images. Do not publicly deploy until Milestone 12 acceptance.
