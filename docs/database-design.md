# Database design

| Table | Purpose | Integrity and indexes |
| --- | --- | --- |
| users | Email identity, name, optional Argon2id password hash, active flag | UUID PK; original unique email index plus unique lower(btrim(email)) index |
| auth_sessions | Server-side browser sessions | UUID PK; RESTRICT user FK/index; unique SHA-256 token digest; expiry index |
| auth_rate_limits | Shared authentication attempt counters | Composite PK (hashed action/client key, window start); atomic attempt increments |
| workspaces | Name, description, required owner | UUID PK; indexed owner FK to users |
| workspace_members | Membership, role, joined timestamp | UUID PK; unique (workspace_id, user_id); user index; owner/admin/member check |
| documents | Original metadata and processing lifecycle | UUID PK; indexed workspace/uploader FKs; unique workspace/checksum; unique id/workspace; status/size/checksum/attempt checks |
| document_chunks | Extracted source text and references | UUID PK; composite document/workspace FK; workspace FK; unique document/index; offset/page/text checks |
| document_jobs | Durable processing queue, one row per document | Document FK/PK; queued/running/done/failed state; availability and expiring lease |
| storage_cleanup | Upload reservations and eventual file cleanup | Opaque storage key PK; availability index; attempt count and safe error |
| embedding_profiles | Provider/model/revision/dimension identity | SHA-256 profile PK; unique id/dimension; dimension bounds |
| chunk_embeddings | Derived pgvector vectors and batch progress | Composite chunk/profile PK; profile/dimension FK; vector/status/norm checks; profile/status index |
| embedding_jobs | Durable per-document/profile indexing | Composite document/profile PK; generation/lease UUIDs; availability index; attempt checks |

Users have owned workspaces, memberships, and uploaded documents. Workspaces have
memberships and documents. Existing ORM relationships are explicitly paired. Original application foreign keys
use ON DELETE RESTRICT. Accounts with referencing records and workspaces with members
or documents cannot be deleted directly. The workspace deletion service explicitly
removes only the mandatory owner membership before deleting an otherwise empty workspace,
in one transaction; any other member or document produces 409. ORM relationships delegate deletion checks to the DB,
even with loaded children. No automatic delete cascades occur. Future explicit cleanup
must account for external stored files before removing document metadata.

Membership's unique composite index supports workspace lookup without a redundant
workspace index. Email identity is enforced case-insensitively by `uq_users_email_normalized` on
`lower(btrim(email))`; the original exact-email index is retained. Registration trims,
validates ASCII local parts, converts international domain names to ASCII, and lowercases
email. Login uses the same input normalization and the database index expression.
Existing rows are preserved. Migration preflight aborts on conflicting normalized
legacy identities without merging accounts; the unique index also closes concurrent
registration races. New non-ASCII local parts are rejected to avoid collation ambiguity.
Never store plaintext passwords.

## Ownership and permissions

workspaces.owner_id is authoritative and must reference an existing user. The service-enforced
application invariant is exactly one owner membership matching owner_id. The database enforces
valid role values and unique memberships, but does not enforce that cross-table match
or require an owner membership. Milestone 04 creation and transfer services maintain both
records atomically. All workspace mutations lock the workspace row first, reload
membership, verify permissions and owner consistency, then commit or roll back together.
An owner role grants no owner authority unless its user also matches owner_id.
Legacy inconsistent records fail closed for mutation and require explicit operator
resolution; none are silently repaired. Direct SQL/ORM callers must maintain these
invariants and lock ordering themselves because no cross-row trigger was added.
Membership authorizes workspace access. Document services apply workspace checks before
exposing metadata or originals; worker operations run as trusted backend jobs.

## Fields and timestamps

ORM UUID defaults use uuid4; raw SQL callers supply IDs. Creation, update, and join
columns are timezone-aware and default to PostgreSQL now(). SQLAlchemy emits updated_at
on updates; raw SQL must set it explicitly. There is no timestamp trigger. PostgreSQL
now() is transaction time, so updates within a transaction may share a timestamp.
Required fields are non-null. Workspace schemas trim names, reject blank/null names,
limit names to 200 characters and descriptions to 10000 characters. PATCH can explicitly
clear a description with null and leaves omitted fields unchanged.

Documents store metadata only. Content resides in external private storage. States are
pending (default), processing, completed, failed. Optional size cannot be negative;
SHA-256 must contain 64 lowercase hexadecimal characters. Workflow transitions, chunks,
Vector columns are now stored in derived chunk_embeddings; AI answer generation is not implemented.

Names follow the common metadata constraint/index convention. Initial migration revision
is 6cc0ce3f2778. pgvector is untouched.

## Read-only inspection

Use a configured PostgreSQL client without putting passwords in shell history:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
SELECT version_num FROM alembic_version;
SELECT extname, extversion FROM pg_extension;
```

Expect twelve application tables plus alembic_version. From apps/api, run
`python -m alembic current`, `python -m alembic heads`, and `python -m alembic check`.
See the root README for migration and test commands.

## Authentication migration

Revision `a31f8c9d204e` follows `6cc0ce3f2778`. It only creates the normalized-email
index, `auth_sessions`, and `auth_rate_limits`; it does not modify existing data or
pgvector. Its transactional conflict guard refuses ambiguous legacy accounts.
Downgrade removes the auth tables and must not run against a populated deployment.

Sessions store only a 64-character SHA-256 token digest, UUID user FK, `created_at`,
`expires_at`, nullable `revoked_at`, and nullable `last_used_at`. Timestamps are UTC-aware.
Expiry comparisons and rate windows use PostgreSQL `clock_timestamp()` so long-running
transactions cannot keep expired sessions valid. The session TTL is absolute.
User deletion remains restricted while sessions reference it; no cascade was introduced.

Rate-limit keys hash route plus socket client IP and are shared across workers through
atomic PostgreSQL `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`. Windows are
fixed, defaulting to 20 attempts per client per endpoint per 300 seconds. Rate counters
are committed separately from account/session writes. Old counters and expired/revoked
sessions need a separately operated retention job; none deletes rows in this milestone.

## Workspace transactions (Milestone 04)

Milestone 04 required no schema change; Milestone 05 advances to `c52d8e7a901b`. Existing users,
documents, migrations, Docker volumes and pgvector are preserved.

Creation inserts workspace plus its sole owner membership in a single transaction.
Transfer requires an existing active registered member and atomically updates owner_id,
demotes the old owner to admin, and promotes the target to owner. Membership role changes
cannot assign owner; removal cannot target the owner. Every cooperating mutation locks
the workspace before reading current role data, so concurrent transfers/additions/
removals are serialized. The unique (workspace_id,user_id) constraint remains the final
membership race defense. User eligibility is read under a shared user-row lock to avoid
an eligibility change during addition/transfer.

Deletion locks the workspace and checks dependencies. Other memberships/documents mean
409 without changes. If only the owner membership exists, the service deletes that
membership then the workspace and commits both together. RESTRICT constraints remain
in place; any unexpected FK conflict rolls back the entire operation, restoring the
owner membership. Users and documents are never deleted by workspace services.

Tests normally roll back an outer transaction even if services commit. Real concurrency
tests require committed data visible across independent connections, so they use uniquely
named `test_workspace_<UUID>` schemas with test-only tables and finally cleanup. They
never create/drop/reset public application tables. The test role needs CREATE SCHEMA;
production runtime accounts need no additional schema privileges for these APIs.

## Document ingestion migration (Milestone 05)

`c52d8e7a901b` follows `a31f8c9d204e`. The migration adds processing_attempts (nonnegative,
NOT NULL, default 0) and nullable last_processed_at to documents, plus document_chunks,
document_jobs and storage_cleanup. Existing document identities and original fields
are untouched. A preflight refuses duplicate (workspace_id,checksum_sha256) records
without deleting/merging anything. A unique constraint then enforces the same-workspace
byte-identity duplicate policy under races. Applied earlier migrations are unchanged.

Chunks reference documents through (document_id,workspace_id), backed by a matching
unique constraint on documents. This rejects a valid document UUID paired with another
workspace. A separate workspace FK and unique (document_id,chunk_index) enforce context
and order. All FKs retain RESTRICT. Text is untrusted private source data. Character
start/end are zero-based and end-exclusive within the normalized page/text; page numbers
are one-based and null for text/Markdown. Section/source references and timezone-aware
creation/update timestamps preserve provenance.

Job states are queued, running, done and failed. A job's document FK is also its primary
key, preventing duplicate jobs. Pending documents have queued jobs, processing has a
running lease, completed has done, and terminal failures have failed. Claim timestamps
and deadlines use PostgreSQL clock_timestamp. Attempt increments commit before work;
chunk replacement and state completion commit together, guarded by the lease token.
A worker crash leaves a recoverable lease, not an invisible in-memory task. Existing
legacy documents are not automatically queued by the migration.

Storage cleanup has no workspace/document FK intentionally: the file cleanup intent
must survive removal of both records. For uploads it begins as a one-hour reservation;
publication deletes it atomically with metadata/job insertion. For deletion it is due
immediately. Cleanup checks for any live document storage reference before unlinking,
and removes missing files idempotently. Failures retain the intent with a safe error
and capped exponential backoff. No automatic retention purges completed/failed job rows;
those remain until authorized document deletion.

Review migration/SQL before upgrade. Downgrade destroys ingestion metadata/chunks and
must not be run on a populated deployment. No original fields or records are deleted
by upgrade, and pgvector and the PostgreSQL Docker volume/port remain unchanged.

## Embedding migration (Milestone 06)

Revision d64a9f2b830c follows c52d8e7a901b and only adds embedding_profiles,
chunk_embeddings and embedding_jobs plus their constraints/indexes. It ensures the
already-installed vector extension exists without updating/dropping it. No source text,
references, original metadata, or applied migrations change. Downgrade removes only the
new derived tables and must not be run casually on a populated deployment.

Profiles identify provider/model/operator-managed revision/dimensions immutably, with
SHA-256 of their canonical tuple. Embedding rows carry chunk UUID, profile ID, dimension,
VECTOR value, status (pending/completed/failed), generation UUID, generated_at and safe
error. A profile/dimension composite FK and vector_dims/norm checks prevent incompatible
or zero vectors. Completed requires a vector and generation timestamp. pgvector rejects
nonfinite float elements; application validation adds shape/norm checks before writes.

Embeddings intentionally use a dimension-unconstrained VECTOR column to retain multiple
model versions/dimensions. No incompatible vectors share a retrieval profile: queries
always filter profile/dimensions and guard the dimension cast. No ANN index exists on the
mixed-dimension column. Exact cosine uses <=> plus a B-tree (profile_id,status) filter and
the existing workspace/document indexes. A future ANN design must create separate typed
profile/dimension cosine indexes and re-evaluate filtering recall; it cannot blindly index
this mixed-dimension column with one typmod/opclass.

An indexing job is unique on document/profile, with queued/running/done/failed states,
generation, bounded attempts, availability, lease UUID/deadline, last attempt time and
safe error. Claims/finalization lock Document before EmbeddingJob, consistent with API
mutation ordering. Generations separate explicit rebuilds; leases fence competing attempts.
Per-batch commits preserve completed chunks during partial failures. Old completed vectors
remain available during a same-profile rebuild; current-generation counts distinguish
those retained vectors from rebuilt ones.

Only the NEW derived child FKs use CASCADE: source chunk deletion removes its embedding
rows and document deletion removes its indexing jobs. The original source-data RESTRICT
constraints are unchanged. Thus deletion and chunk replacement cannot leave derivative
vectors/jobs orphaned, and late provider results cannot recreate them. Profiles and old
model-version embeddings are retained until their source is deleted; no automatic profile
retention or cleanup of old versions is implemented.
