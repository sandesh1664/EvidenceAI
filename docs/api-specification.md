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
through the membership API first; document cleanup is outside this milestone. Existing
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

Current migration remains `a31f8c9d204e`; Milestone 04 changes no schema or applied
migration. Tests authenticate real session cookies and use isolated PostgreSQL data.
Concurrency tests require CREATE SCHEMA permission and use only uniquely named,
disposable test schemas; they verify actual row-lock contention via pg_blocking_pids.
Public application records and Docker volumes are not reset. No independent production
security audit is implied by passing automated tests.
