# Database design

| Table | Purpose | Integrity and indexes |
| --- | --- | --- |
| users | Email identity, name, optional password hash, active flag | UUID PK; unique email index |
| workspaces | Name, description, required owner | UUID PK; indexed owner FK to users |
| workspace_members | Membership, role, joined timestamp | UUID PK; unique (workspace_id, user_id); user index; owner/admin/member check |
| documents | File/storage metadata and processing state | UUID PK; indexed workspace/uploader FKs; status, checksum and size checks |

Users have owned workspaces, memberships, and uploaded documents. Workspaces have
memberships and documents. All relationships are explicitly paired. All foreign keys
use ON DELETE RESTRICT. Accounts with referencing records and workspaces with members
or documents cannot be deleted. ORM relationships delegate deletion checks to the DB,
even with loaded children. No automatic delete cascades occur. Future explicit cleanup
must account for external stored files before removing document metadata.

Membership's unique composite index supports workspace lookup without a redundant
workspace index. Email uniqueness is case-sensitive. Future identity services must
consistently trim/normalize email before writes and lookup, and consider a case-insensitive
constraint migration before accepting public identities. Never store plaintext passwords.

## Ownership and permissions

workspaces.owner_id is authoritative and must reference an existing user. The intended
application invariant is one owner membership matching owner_id. The database enforces
valid role values and unique memberships, but does not enforce that cross-table match
or require an owner membership. Future creation/transfer services must maintain both
records atomically. Until then, direct SQL/ORM callers must maintain it themselves.
An owner role grants no authorization by itself. Uploader membership and tenant access
also require future services; this milestone does not implement permission checks.

## Fields and timestamps

ORM UUID defaults use uuid4; raw SQL callers supply IDs. Creation, update, and join
columns are timezone-aware and default to PostgreSQL now(). SQLAlchemy emits updated_at
on updates; raw SQL must set it explicitly. There is no timestamp trigger. PostgreSQL
now() is transaction time, so updates within a transaction may share a timestamp.
Required fields are non-null; empty-text validation belongs to future input schemas.

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

Expect four application tables plus alembic_version. From apps/api, run
`python -m alembic current`, `python -m alembic heads`, and `python -m alembic check`.
See the root README for migration and test commands.
