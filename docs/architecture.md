# Architecture

The existing Next.js frontend and FastAPI health endpoint remain unchanged. The
backend foundation uses synchronous SQLAlchemy typed models, Psycopg 3, PostgreSQL
17 and Alembic. pgvector now supports versioned embeddings and exact cosine retrieval. Workspace management and membership-based tenant
access are implemented. Document upload, private storage, extraction and chunks are implemented in Milestone 05.
Stateless grounded answers (Milestone 07) and private persistent conversations (Milestone 08) are implemented; production retrieval evaluation remains future work.

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
Authentication is implemented in Milestone 03; document ingestion is implemented in Milestone 05.
Nullable password_hash supports legacy users; passwordless records cannot log in. Document contents belong in separate private storage.

Python 3.14.6 and the pinned dependencies passed the suite; pip check found no broken
requirements. Installed Starlette 1.9.0 TestClient source and package metadata recommend
httpx2>=2.0.0 and emit a deprecation warning for the current httpx transport. The health
test passes with that warning visible. Dependencies were preserved; validate a transport
upgrade separately. No warnings are filtered.

Milestone 07 adds validated extractive answers on top of authorized retrieval.

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
arbitrary writes the service guarantees. No frontend or AI code changed.

Concurrency tests use independent connections and authenticated TestClient requests.
Each test creates only a unique disposable schema, seeds test users/sessions/workspace,
observes actual lock blocking with pg_blocking_pids, and checks the resulting owner
invariant and permission decision. Scratch schemas are removed in finally cleanup;
public data is untouched. Other new and existing tests retain rollback isolation.
Use a dedicated CI database whose role can create test schemas.

Reference: [PostgreSQL 17 row locking](https://www.postgresql.org/docs/17/explicit-locking.html).

## Milestone 05 document ingestion

`app/api/routes/documents.py` exposes authenticated workspace-scoped upload, list,
metadata, download, retry and delete endpoints. `document_workspace_access` and
`document_access` in core/authorization.py reuse workspace access policy. API lookups
scope document UUID and workspace UUID together; missing/inaccessible workspaces use
the same 404. Members are read-only; owners/admins can mutate. Mutation locks retain
the established workspace-first order and recheck current role. Safe response schemas
exclude storage keys, filesystem paths and extracted content.

The ASGI browser middleware caps the raw multipart body before spooling, including
chunked requests. The upload route accepts exactly one file, authorizes before parsing,
and closes multipart files on all paths. Storage streams in bounded blocks with an
independent exact per-file cap. Text is checked for UTF-8/binary content; PDFs get
bounded subprocess structural/encryption validation. Full page text extraction is
never performed by the request handler. 202 means persisted and queued, not completed.

`DocumentStorage` is a protocol with stage/open/promote/delete operations. The local
implementation uses private, flat, opaque server-generated keys and descriptor-relative
operations with O_NOFOLLOW. It refuses symlink path components and non-regular/hardlinked
objects. Originals publish atomically using link/unlink after fsync. A future S3 adapter
must provide equivalent staging/publish/delete behavior and a seekable private stream
(or temporary file) to the parser. API and worker instances must share storage.

A committed storage_cleanup reservation precedes file creation. Publishing metadata and
its document_jobs row removes the reservation in the same transaction. A failed upload
cleans up eagerly when possible; crashes/unavailable storage leave a durable cleanup
intent. Final publication locks the reservation and verifies the original still exists,
so cleanup of an abandoned upload cannot publish metadata referencing a missing file.
Ambiguous commit recovery checks live metadata before unlinking anything.

The separate `python -m app.document_worker` process polls PostgreSQL. This milestone
uses a PostgreSQL queue instead of Redis: enqueueing is atomic with document creation,
and there is no broker dual-write gap or new deployment service. Claim uses Document
row FOR UPDATE SKIP LOCKED followed by its job lock. API retry/delete and worker finalization
use the same document-before-job order. Each claim commits a unique expiring lease and
increments attempts, then parses outside a DB transaction. Finalization verifies the
lease, unexpired deadline, document ID and workspace, replaces chunks, and updates status
in one transaction. Stale or deleted jobs cannot publish. Expired claims are recoverable;
attempts and automatic transient-error retries are bounded.

`document_parser_child.py` runs with Python isolated mode, a restricted environment,
CPU/output/descriptor limits and parser-specific budgets. A supervisor enforces wall time
and samples RSS; Linux also enforces RLIMIT_AS, while macOS uses the RSS supervisor because
RLIMIT_AS is unsupported. Child stderr is discarded and errors use fixed safe messages.
The parser makes no network calls and disables Python sockets and external JBIG2 tools.
No scripts, attachments, macros or links are executed. This is not a full OS sandbox.

Chunking is deterministic over normalized per-page/plain text with Markdown heading
boundaries. Chunks carry document/workspace identity, sequential index, source reference,
page/section and exact character offsets into normalized source text. UUID5 IDs plus
unique document/index and a composite document/workspace FK prevent duplicates and
misattribution. Milestone 06 adds derived embeddings and authorized search excerpts.

Deleting a document atomically removes chunks, job and metadata and records a storage
cleanup intent. It immediately invalidates future metadata/download access. File deletion
is eventual, idempotent and retried with capped backoff until storage is available.
In-flight authorized streams can finish. Cleanup does not depend on the workspace FK,
so an otherwise empty workspace can subsequently be deleted. See
[document processing](document-processing.md) for limits and operational details.

## Milestone 06 versioned embeddings and retrieval

`embedding_providers.py` defines a provider protocol, immutable profile identity, deterministic
fake provider, hosted OpenAI implementation, validation and bounded retry engine. Provider,
model, operator-managed revision and dimension hash to an immutable profile ID. The hosted
provider uses the fixed official HTTPS endpoint, verifies response model/index ordering,
bounds response size, disables redirects/environment proxies, and never exposes raw HTTP
errors. All vectors must have expected shape, finite values and nonzero norm; they are
normalized before persistence. Credentials remain backend SecretStr settings.

New embedding_profiles, chunk_embeddings and embedding_jobs tables store derived data.
Source chunks/references remain unchanged. Generic pgvector VECTOR supports multiple
profile dimensions; DB checks and a composite profile/dimension FK prevent mismatches.
Search restricts exact profile and dimension and uses a guarded vector cast before <=>.
This avoids comparing different-dimensional profiles even if query predicates are rearranged.

On successful extraction, enabled-provider indexing is enqueued in the same transaction
as chunks and completed status. Existing `document_worker` ticks then process indexing.
The embedding queue reuses Document-first locks, SKIP LOCKED claims, expiring leases,
bounded attempts and stale-result fences, with a unique document/profile job. Provider
calls hold no DB transaction; each validated batch commits independently. Successful
batches survive later failures; retries skip chunks completed in the target generation.
Forced same-profile rebuilds retain old usable vectors until replacement. A profile change
creates independent embeddings and never changes old profile rows.

Search routes authenticate and authorize the workspace before any provider call, validate
all document filters, release the transaction during remote query embedding, and then
recheck membership/filter context. The final parameterized SQL joins current membership
and scopes both Document and DocumentChunk to the authorized workspace, completed document
state, profile/dimension and completed embedding state. Results are ordered by cosine
distance then document ID/chunk index/chunk ID, and include bounded excerpts/provenance.
A minimum similarity threshold returns [] when nothing qualifies; scores are not confidence.

Exact search is the initial choice for predictable workspace-filtered ranking and an
unambiguous correctness baseline. Profile/status B-trees and existing workspace/chunk
indexes narrow candidates. No HNSW index is created on the mixed-dimension vector column.
Large-scale deployment needs corpus-specific benchmarks before a dimension/profile-specific
cosine ANN index and post-filter recall tuning. Milestone 06 introduced no Redis or frontend changes. See [retrieval engine](retrieval-engine.md) for operations and evaluation.

## Milestone 07 stateless grounded answers

The ask route composes existing session/CSRF and workspace authorization, semantic search,
bounded context assembly, configurable generation, source revalidation and citation validation.
Search ranking and profile compatibility remain in the existing search service. Context IDs
are assigned on the server; only question, evidence ID and evidence text reach generation.
The model cannot make authorization decisions or request tools/database queries.

Providers implement the LLMProvider generate contract: deterministic mock and opt-in OpenAI
Responses, with strict JSON, usage validation, bounded attempts, input/output budgets and
wall timeouts for hosted calls. Exact quote claims are checked against admitted source prefixes,
then rendered with server metadata and claim associations. Unvalidated output is never emitted.
Membership, active user and evidence eligibility are checked again after provider I/O.

A separate autocommit connection holds a session PostgreSQL advisory lock for generation
capacity, shared across workers without adding tables. Source transactions do not span hosted
I/O. All workers need consistent capacity settings and connection-pool headroom. The endpoint
persists no conversations or answers itself. Milestone 07 introduced no migration; Milestone 08 adds separate persistence at `6f22cc4c46ad`.
Metrics/logs contain fixed outcomes, request IDs, counts and durations only. SSE is deferred
to preserve validation before delivery. See [RAG answer engine](rag-answer-engine.md).

## Milestone 08 private conversations

Conversation endpoints authorize current membership and the conversation's immutable owner.
They reserve a user/pending-assistant pair under workspace-then-conversation row locks, commit
sequence/idempotency/lease state, run existing RAG outside the transaction, then reauthorize
and atomically save validated content/citation snapshots. A partial unique pending index and
canonical payload hashes prevent competing or duplicate turns. Expired turn leases are
recovered on message reads/submissions; late workers cannot overwrite terminal outcomes.

Bounded prior user questions are separate untrusted reference context. Assistant answers and
saved citations are excluded from prompt history and fresh evidence. Every turn uses current
workspace/profile retrieval and current filters. Nullable source FKs plus immutable original
IDs and bounded excerpts preserve historical citations after source deletion. Conversation
delete cascades only to messages/snapshots; archive retains history and blocks new turns.

The additive migration is `6f22cc4c46ad`; stateless `/ask` remains compatible. No frontend,
streaming or background conversation worker is added. See [conversation engine](conversation-engine.md)
for concurrency, privacy, exact schemas and heuristic reference-resolution limits.

## Milestone 09 integrated frontend

The existing Next.js 16.4.2 App Router app provides the backend's real account/workspace,
document, search, stateless research and persistent conversation workflows. Private data is
fetched in browser components after the existing /auth/me check, with credentials=include,
cache=no-store and X-CSRF-Protection: 1 on mutations. Server HTML contains generic loading
UI rather than private payloads. No BFF, alternate session system or backend rebuild is added.

Typed API contracts centralize methods/errors. A short-lived account/path-scoped browser
cache aborts stale reads, invalidates on mutation and clears on logout/401; no private data
is persisted to browser storage. Polling pauses on hidden/inactive pages. Workspace layouts
and role hints follow existing services; authorization remains in FastAPI. Conversation
retry preserves the exact idempotency key/body, and saved citations remain historical snapshots.

A nonce-generating Next proxy and dynamic root document enforce production script CSP and
private/no-store responses, plus other security headers. Responsive green/neutral CSS supports
light/dark themes and native accessible controls. Real-browser tests use a production Next
server, actual FastAPI/workers and a generated disposable schema/temporary storage. Backend
source/migrations remain unchanged. See [frontend architecture](frontend-architecture.md).
