# EvidenceAI API specification

The API prefix is `/api/v1`. Workspace and membership requests all require a valid
HTTP-only session cookie from `/auth/login`; there is no bearer-token alternative.
Every POST/PATCH/DELETE requires the trusted Origin and `X-CSRF-Protection: 1`.
For browsers use `credentials: "include"`. JSON writes use Content-Type application/json.
Local HTTP must be explicitly enabled; see [security](security.md) for all settings.

## Authentication and health

| Method/path | Request body | Success |
| --- | --- | --- |
| GET /health | None | 200: service, status, version; no auth/configuration required |
| POST /auth/register | email, display_name, password (12–128 characters) | 201 safe user; no automatic login |
| POST /auth/login | email, password (1–128 characters) | 200 safe user; sets opaque HTTP-only session cookie |
| POST /auth/logout | None | 204 empty; revokes session and clears cookie |
| GET /auth/me | None | 200 safe current user |

Safe user fields are id, email, display_name, is_active and created_at. Authentication
errors/validation, session lifecycle and rate limits are documented in [security](security.md).

## Shared workspace contracts

`workspace_id`, membership `user_id`, and transfer `new_owner_id` are UUIDs. Route
UUIDs and request fields are validated; malformed values return 422. All request bodies
reject unrecognized fields, including owner_id on workspace create/update.

Workspace response (returned by create/read/update/transfer, and as list items):

```json
{
  "id": "ef5b5597-39c0-4bac-8fe7-5df7e1740404",
  "name": "Research",
  "description": "Private research",
  "owner_id": "dd030a35-aab4-47be-908a-350717c68eb9",
  "created_at": "2026-10-19T08:00:00Z",
  "updated_at": "2026-10-19T08:00:00Z"
}
```

Membership response (returned by add/update, and as list items):

```json
{
  "id": "d909f023-bab4-4679-9b94-560c8ad589e6",
  "workspace_id": "ef5b5597-39c0-4bac-8fe7-5df7e1740404",
  "user_id": "dd030a35-aab4-47be-908a-350717c68eb9",
  "role": "owner",
  "joined_at": "2026-10-19T08:00:00Z"
}
```

No user email, password hash or session information appears in workspace/member
responses. Timestamps are timezone-aware. List responses are JSON arrays, with `limit`
(default 50, range 1–100) and `offset` (default 0, nonnegative). Empty results are `[]`.
There is no total count. Ordering is created_at/id for workspaces and joined_at/id for
members. Offset pagination can shift when concurrent inserts/deletions occur.

## Workspace endpoints

All paths below start `/api/v1/workspaces`. Use the trailing slash for collection
routes; FastAPI redirects the slashless collection path to it.

| Method/path | Request | Success | Authorization / operation-specific errors |
| --- | --- | --- | --- |
| POST / | `{"name":"Research","description":"Private research"}` | 201 workspace | Any authenticated active user; atomically creates matching owner membership |
| GET / | Optional limit/offset query | 200 workspace array | Only caller memberships, including workspaces they own through membership |
| GET /{workspace_id} | None | 200 workspace | Any workspace member; otherwise 404 |
| PATCH /{workspace_id} | `{"name":"Renamed","description":null}` | 200 workspace | Owner/admin; 403 for members; 409 inconsistent ownership |
| DELETE /{workspace_id} | None | 204 empty | Owner only; 403 for others; 409 if other members/documents remain or data conflict |

`name` is required on creation, trimmed and nonblank, maximum 200 characters. Description
is optional/nullable with a 10000-character maximum. PATCH requires at least one field;
omitted values are unchanged, description null clears it, name null is invalid. Clients
cannot change ownership through workspace PATCH.

Deletion removes only an otherwise empty workspace and its mandatory owner membership,
atomically. It does not delete users, documents, or other members. Remove other memberships
through the membership API first; delete documents through the document API below. Existing
RESTRICT foreign keys remain in place. Any failure restores the owner membership.

## Membership endpoints

All paths below start `/api/v1/workspaces/{workspace_id}`. Membership must be checked
before responding, including before checking target-user existence.

| Method/path | Request | Success | Authorization / operation-specific errors |
| --- | --- | --- | --- |
| GET /members | Optional limit/offset query | 200 membership array | Any workspace member |
| POST /members | `{"user_id":"<UUID>","role":"member"}` | 201 membership | Owner/admin; 404 eligible user not found; 409 duplicate |
| PATCH /members/{user_id} | `{"role":"admin"}` | 200 membership | Owner/admin; 404 member not found; 409 if target is owner; admins get 403 for existing admin targets |
| DELETE /members/{user_id} | None | 204 empty | Owner/admin; 404 member not found; 409 if target is owner; admins get 403 for existing admin targets |
| POST /transfer-ownership | `{"new_owner_id":"<UUID>"}` | 200 updated workspace | Owner only; 404 missing/ineligible member; 409 transfer to self or inconsistent ownership |

Membership POST defaults role to member; POST/PATCH role can only be member or admin.
PATCH requires role. No membership request can assign owner. Additions identify an existing
user by UUID only; no email lookup, invitation or join-link endpoint exists. Eligible
users must be active with a non-null password hash (a registered password account).
Missing, inactive and passwordless users all receive the same eligible-user error.

Owners can change/remove any non-owner membership. Admins can add member/admin accounts
and promote ordinary members to admin, but cannot change/remove a user who is already
admin, including themselves. Ordinary members cannot manage memberships or self-remove.
All roles can view membership identifiers, roles and join timestamps only.

Transfer requires the target to already be an eligible workspace member. It atomically
updates owner_id, promotes the target to owner, and demotes the prior owner to admin.
The old owner does not retain transfer/delete authority. Exactly one owner membership
matching owner_id must hold before and after. Direct owner removal/demotion is forbidden;
use transfer instead. Concurrent mutations lock the workspace, then re-read current
permissions and ownership before proceeding. A losing concurrent transfer by the former
owner gets 403, because that requester is now admin.

## Permission matrix

| Action | Owner | Admin | Member |
| --- | --- | --- | --- |
| Read workspace / members | Yes | Yes | Yes |
| Update workspace | Yes | Yes | No |
| Add active registered users as member/admin | Yes | Yes | No |
| Change/remove ordinary members | Yes | Yes | No |
| Change/remove existing admins | Yes | No | No |
| Assign owner through membership POST/PATCH | No | No | No |
| Transfer ownership | Yes | No | No |
| Delete workspace when otherwise empty | Yes | No | No |

An actor with no membership gets 404, irrespective of whether the workspace exists.
Owner permissions require both designated owner_id and a matching owner membership.
Legacy owner_id without membership does not grant access. Inconsistent ownership is
never silently repaired; mutations fail the applicable authorization/invariant check.

## Error responses

Operational errors use `{"detail":"<safe message>"}`. Validation errors use a detail
array with loc, msg and type, omitting original inputs. SQL, constraint details,
credentials and private user information are not included in client errors.

| Status | Meaning |
| --- | --- |
| 400 | Rejected CORS preflight |
| 401 | Missing, invalid, expired, revoked session or inactive authenticated user |
| 403 | Insufficient workspace role, forbidden admin target, untrusted Origin, missing CSRF header, or required HTTPS missing |
| 404 | Workspace absent/inaccessible (same `Workspace not found`), member absent, or eligible user absent |
| 409 | Duplicate membership, protected owner mutation, transfer to self, inconsistent ownership, deletion dependencies, integrity conflict, or retryable database contention |
| 422 | Invalid UUID, name/description/role/body, unknown field, empty PATCH, or invalid pagination |
| 429 | Registration/login rate limit; Retry-After included |

CSRF middleware can reject a write before authentication; supply valid CSRF headers to
exercise the 401 contract. For valid request bodies, unauthorized workspace access uses
the same 404 response as a nonexistent workspace. Validation can return 422 before an
operation-specific check. Workspace integrity conflicts return a generic 409; deadlock,
serialization or lock-not-available failures return `Concurrent workspace change; retry
request`. Re-read state before retrying, especially after a concurrent ownership change.
Database/network errors are not converted into successful responses.

## Verification

Run from apps/api using its virtual environment:

```sh
python -m pytest -q
python -m alembic current
python -m alembic check
python -m pip check
# From the repository root:
git diff --check
```

Current migration is `c52d8e7a901b`; Milestone 05 adds ingestion metadata without changing
previously applied migrations. Tests authenticate real session cookies and use isolated PostgreSQL data.
Concurrency tests require CREATE SCHEMA permission and use only uniquely named,
disposable test schemas; they verify actual row-lock contention via pg_blocking_pids.
Public application records and Docker volumes are not reset. No independent production
security audit is implied by passing automated tests.

## Document API (Milestone 05)

All paths below start `/api/v1/workspaces/{workspace_id}/documents`. Every endpoint
requires session authentication and membership. UUIDs are validated; missing/inaccessible
workspaces both return 404 Workspace not found. A document UUID belonging to a different
accessible workspace returns 404 Document not found. Owners/admins may mutate; members
may only read. POST/DELETE require the same trusted Origin/custom CSRF header as other
cookie-authenticated writes. Browser calls include credentials.

| Method/path | Request | Success | Additional failures |
| --- | --- | --- | --- |
| POST / | multipart/form-data, exactly one `file` part | 202 document metadata with pending status | 400 malformed/multiple parts; 413 size/body limit; 415 unsupported extension; 422 unsafe filename, mismatched content/MIME, malformed/encrypted PDF or UTF-8; 409 duplicate; 503 storage unavailable |
| GET / | limit (1–100, default 50), offset (>=0, default 0) | 200 metadata array, ordered by created_at/id | 422 invalid pagination |
| GET /{document_id} | None | 200 metadata/status | 404 inaccessible/missing document |
| GET /{document_id}/download | None | 200 streamed original attachment | 404 inaccessible/missing document; 503 original unavailable/unsafe storage object |
| DELETE /{document_id} | None | 204 empty; metadata/chunks/job removed, durable file cleanup queued | 403 member; 409 legacy unmanaged storage or integrity conflict |
| POST /{document_id}/retry | No body | 202 metadata, same UUID, pending status | 403 member; 409 not failed or total attempt limit reached |

Upload accepts .pdf, .txt and .md (case-insensitive) up to 20971520 bytes by default.
application/octet-stream is permitted only if actual content validates; Markdown also
accepts text/plain. Extension/content/MIME disagreements return 422. Text is UTF-8 only
(optional BOM); encrypted PDFs are unsupported. Valid empty/image-only PDFs are accepted
structurally then fail extraction with empty/OCR-not-supported status. A structural
validation timeout returns 422. The whole multipart envelope is capped at the file limit
plus 65536 bytes. Content-Length is not trusted as the sole limit.

Safe metadata response (no storage key, path or extracted text):

```json
{
  "id": "f61f6a5b-ec19-4d4d-a451-6c8e716b5bb3",
  "workspace_id": "ef5b5597-39c0-4bac-8fe7-5df7e1740404",
  "uploaded_by": "dd030a35-aab4-47be-908a-350717c68eb9",
  "original_filename": "research.pdf",
  "mime_type": "application/pdf",
  "file_size": 12345,
  "checksum_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "processing_status": "pending",
  "processing_error": null,
  "processing_attempts": 0,
  "last_processed_at": null,
  "created_at": "2026-10-19T08:00:00Z",
  "updated_at": "2026-10-19T08:00:00Z"
}
```

Status is pending/processing/completed/failed. last_processed_at records the most recent
attempt start; attempts count automatic, recovered and manual attempts together. Error
strings are safe fixed messages, not parser exception details. 202 does not imply
successful extraction. Poll metadata to observe completion/failure. Legacy metadata can
have null MIME/size. Download always uses application/octet-stream, attachment disposition,
nosniff and no-store; it does not execute or inline-render original content.

Duplicates mean identical SHA-256 bytes in one workspace regardless of filename; they
return 409 without another file/job. The same content in another accessible workspace
is permitted. Manual retry is allowed only when failed with fewer than the configured
3 total attempts. It preserves identity, resets queued state and never appends duplicate
chunks. Pending, running, completed and exhausted documents return 409. Some permanent
failures (e.g. OCR unsupported) will fail again unless capabilities/configuration change.

Delete removes metadata, chunks and queue row transactionally, fencing active workers.
Disk cleanup is eventual and persistent; subsequent metadata/downloads return 404 even
while storage is unavailable. In-flight authorized streams may finish. No user records
are removed. See [document processing](document-processing.md) for worker operations,
parser/source limits, crash recovery and storage consistency details.
