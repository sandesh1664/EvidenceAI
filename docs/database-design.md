# Database design

| Table | Purpose | Integrity and indexes |
| --- | --- | --- |
| users | Email identity, name, optional Argon2id password hash, active flag | UUID PK; original unique email index plus unique lower(btrim(email)) index |
| auth_sessions | Server-side browser sessions | UUID PK; RESTRICT user FK/index; unique SHA-256 token digest; expiry index |
| auth_rate_limits | Shared authentication attempt counters | Composite PK (hashed action/client key, window start); atomic attempt increments |
| workspaces | Name, description, required owner | UUID PK; indexed owner FK to users |
| workspace_members | Membership, role, joined timestamp | UUID PK; unique (workspace_id, user_id); user index; owner/admin/member check |
| documents | File/storage metadata and processing state | UUID PK; indexed workspace/uploader FKs; status, checksum and size checks |

Users have owned workspaces, memberships, and uploaded documents. Workspaces have
memberships and documents. All relationships are explicitly paired. All foreign keys
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
Membership authorizes workspace access; future document/upload services must also
apply tenant checks before exposing document metadata or content.

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
vector columns and AI processing are not implemented.

Names follow the common metadata constraint/index convention. Initial migration revision
is 6cc0ce3f2778. pgvector is untouched.

## Read-only inspection

Use a configured PostgreSQL client without putting passwords in shell history:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
SELECT version_num FROM alembic_version;
SELECT extname, extversion FROM pg_extension;
```

Expect six application tables plus alembic_version. From apps/api, run
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

No schema change or migration is required; head remains `a31f8c9d204e`. Existing users,
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
