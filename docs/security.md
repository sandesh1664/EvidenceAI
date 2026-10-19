# Authentication and workspace security

Milestone 03 uses server-side PostgreSQL sessions. Milestone 04 adds authenticated
workspace management and role-based membership authorization. OAuth, JWT, email
verification, password reset, and account recovery are not implemented.

## API contract

All paths are under `/api/v1/auth`. Successful user responses contain exactly `id`,
`email`, `display_name`, `is_active`, and `created_at` (UTC timestamp).

| Method/path | JSON input | Success | Expected failures |
| --- | --- | --- | --- |
| POST /register | email, display_name, password | 201 safe user; no automatic login | 409 duplicate; 422 invalid; 429 rate limit |
| POST /login | email, password | 200 safe user and session Set-Cookie | 401 generic credentials/status failure; 422 invalid; 429 rate limit |
| POST /logout | none | 204; revoke current session and clear cookie | 401 absent/invalid session |
| GET /me | none | 200 safe user; update last-used time | 401 absent/invalid/expired/revoked/inactive |

Browser POSTs also return 403 on CSRF failure, untrusted Origin, or required HTTPS
missing. Cross-origin read requests from untrusted origins return 403. CORS preflight
from untrusted origins fails with 400. Authentication responses use Cache-Control:
no-store. Validation errors omit input and context so invalid passwords are not echoed.

## Passwords and identities

`argon2-cffi` supplies Argon2id secure hashing and verification with its maintained
RFC 9106 low-memory defaults (64 MiB, three iterations, parallelism four). Successful
login rehashes when parameters need updating. Registration accepts 12–128 characters;
login accepts 1–128 to support legacy hashes. Passwords are not trimmed or transformed.
Request passwords use SecretStr, and neither hashes nor passwords are returned/logged.
SQLAlchemy hides SQL parameters. Deployment logging/APM must not capture request bodies,
Cookie/Set-Cookie headers, or database credentials. Unknown/passwordless users undergo
a dummy verification; all failed credential/status checks use the same 401 message.

Emails are trimmed, validated without DNS requests, converted to ASCII domain form,
and lowercased. Non-ASCII local parts are rejected. A unique PostgreSQL expression
index rejects case/space conflicts even for concurrent requests. Existing conflicting
identities abort migration and require an explicit operator resolution; no merge occurs.
Duplicate registration returns 409 and thus reveals registration status by design.

## Session lifecycle

Each login generates 32 random bytes using `secrets.token_urlsafe(32)`. Only SHA-256
of the token is stored. Tokens contain no identity data. The raw token is sent exclusively
in an HTTP-only cookie with SameSite=Lax, Path=/, and no Domain. Production uses Secure
and the `__Host-evidenceai_session` name. Local explicit HTTP mode uses
`evidenceai_session`. Cookies have no persistence expiry; server-side expiry is absolute
and configurable (default 24 hours). Browser session restore can retain session cookies;
server expiry remains authoritative. Login always generates a new token.

`/me` verifies token format/digest, active user, revocation and expiry against the database.
Last-used tracking never slides expiry. Logout revokes the current session and clears
the cookie with matching attributes. Other devices remain signed in. No plaintext token
is stored in PostgreSQL or localStorage. Revoke all sessions operationally when an account
is compromised; there is no public revoke-all endpoint in this milestone.

## Browser, CSRF, and CORS

Use Next.js `http://localhost:3000` and API `http://localhost:8000` for development.
These are different origins and the same site. Use fetch `credentials: "include"`
for every auth call. Every state-changing request requires an exact trusted Origin plus
`X-CSRF-Protection: 1`. Browser code cannot set Origin manually. Requiring a custom header
forces a CORS preflight; credentialed CORS allows only configured exact origins, GET/POST/PATCH/DELETE,
and Content-Type/X-CSRF-Protection. No wildcard origins, regex reflection, or wildcard
credential policy exists. Login and registration are protected too, preventing login CSRF.
Requests without Origin are rejected for writes, including CLI clients unless they supply
it. CLI clients must also supply the custom header. No separate CSRF token endpoint is
needed for this strategy. SameSite is defense in depth, not the sole CSRF protection.

```javascript
await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  credentials: "include",
  headers: {"Content-Type": "application/json", "X-CSRF-Protection": "1"},
  body: JSON.stringify({email, password})
});
```

Keep the hostname consistent; mixing localhost and 127.0.0.1 breaks the site/cookie
assumptions. Cookies do not isolate ports, so use trusted local services. Production
must use HTTPS on the same site (e.g. app.example.com/api.example.com), or a same-origin
reverse proxy, with explicit trusted frontend origins. Cross-site deployment with
unrelated registrable domains is unsupported by the Lax cookie policy. No frontend files
or Next.js proxy changes are necessary for this API milestone.

## Environment and deployment

| Setting | Default / requirement |
| --- | --- |
| APP_ENV | development; production/staging enforce HTTPS origins |
| DATABASE_URL | Required PostgreSQL URL; backend only |
| AUTH_ALLOW_INSECURE_HTTP | false; true permitted only in development/test |
| TRUSTED_FRONTEND_ORIGINS | JSON array, default ["http://localhost:3000"]; production must override with HTTPS origins |
| SESSION_TTL_SECONDS | 86400; range 60–2592000 |
| AUTH_RATE_LIMIT | 20; range 1–10000 attempts per socket IP per endpoint/window |
| AUTH_RATE_WINDOW_SECONDS | 300; range 1–86400 |

For local HTTP, explicitly set AUTH_ALLOW_INSECURE_HTTP=true in the backend .env;
the tracked example opts in, the application default does not. Production/staging
reject that option and reject HTTP frontend origins. The server rejects unsafe requests
on HTTP whenever Secure cookies are enabled. Terminate TLS at a trusted proxy or Uvicorn;
set forwarding trust only to controlled proxy addresses. Run directly accessible Uvicorn
with `--no-proxy-headers`. The limiter reads `request.client.host` and never parses
Forwarded/X-Forwarded-For. Uvicorn may rewrite that value if proxy headers are enabled;
never use `--forwarded-allow-ips='*'` on an untrusted network. Proxies must strip supplied
forwarding headers and set their own. Otherwise client IP spoofing defeats rate limits.

## Rate limiting and operational limits

Login and registration use atomic, database-backed fixed-window counters before credential
work, including malformed attempts. Failed logins and duplicate registrations consume
the budget. Reaching it returns 429 and Retry-After. All workers must use the same database.
An in-memory limiter would lose counters on restart and grant separate budgets per worker;
PostgreSQL is the shared storage implemented here. Redis atomic counters would be an
alternative at higher scale. PostgreSQL failures fail closed.

Per-IP limiting can affect shared NAT users; distributed botnets can bypass an individual
IP budget. Fixed windows permit bursts around boundaries. Production also needs ingress
connection/body limits and distributed abuse monitoring; add shared account/network
budgets or progressive challenges as abuse patterns require. This milestone does not
add a background retention job: schedule reviewed cleanup of old rate windows and
expired/revoked sessions before large-scale rollout. No cleanup runs automatically.
A request already authenticated when logout/deactivation occurs may complete; future
requests are rejected. No email verification or MFA is implemented.

## Verification

From apps/api, activate `.venv`, install requirements, review the additive migration,
and run `python -m alembic upgrade head`, `python -m pytest -q`,
`python -m alembic heads`, `python -m alembic current`, `python -m alembic check`, and
`python -m pip check`. Tests use real PostgreSQL and TestClient with get_db overrides
and the existing outer-transaction/savepoint isolation. CI should use a separate migrated
database. Tests never truncate/delete existing rows. Existing health/model/config tests
are retained. No warning filters hide the existing Starlette/httpx deprecation warning;
httpx2 transport migration remains a separate compatibility task.

References: [argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[Starlette CORS](https://www.starlette.io/middleware/#corsmiddleware).

## Workspace authorization

Every workspace and membership endpoint reuses get_current_user and rejects invalid,
revoked, expired sessions or inactive users. A caller must hold workspace membership
before workspace/member data is returned. Membership cannot be inferred from owner_id
alone. Missing/inaccessible workspace IDs use the same 404 response. Listing queries
are filtered by caller membership and have bounded pagination. UUIDs and bounded request
schemas reject malformed IDs, unrecognized fields and client-assigned owner_id/roles.
Membership responses expose only membership identifiers, role and join time, never
emails, password hashes or auth-session details.

| Action | Owner | Admin | Member |
| --- | --- | --- | --- |
| View workspace and members | Yes | Yes | Yes |
| Update workspace | Yes | Yes | No |
| Add existing active registered users as member/admin | Yes | Yes | No |
| Change/remove ordinary members | Yes | Yes | No |
| Change/remove existing admins | Yes | No | No |
| Assign owner using membership POST/PATCH | No | No | No |
| Transfer ownership to an existing eligible member | Yes | No | No |
| Delete an empty workspace | Yes | No | No |

Admins may promote ordinary members to admin; they cannot modify/remove current admins,
including themselves. Members cannot self-promote or self-remove. No general membership
mutation can demote/remove an owner. Owners must use transfer; the old owner becomes
admin and the new owner must already be an active registered member. Only the new owner
can transfer again. Explicit assignment of owner through member payloads is a 422 error.

Creation atomically creates exactly one owner membership matching owner_id. Every
workspace mutation takes the workspace row lock before rechecking current membership
and designated ownership, refreshing stale ORM objects. This prevents a concurrent
transfer/demotion/removal from leaving an old authority usable after the lock wait.
Exactly one matching owner membership is checked before mutation; inconsistent legacy
records produce a conflict or fail the owner check and require operator resolution.
The schema does not independently impose this cross-row invariant on direct SQL writers;
operational scripts must use these services or follow the same locking/invariant rules.

Deletion is permitted only for the designated owner of a workspace with no documents
and no other memberships. The service removes its required owner membership and workspace
in one transaction. Dependency checks and existing RESTRICT FKs prevent unexpected
cascades; errors roll back both operations. No user/document data is deleted.

CSRF and trusted-Origin checks cover every POST/PATCH/DELETE, with credentials and
HTTPS requirements unchanged. CORS explicitly includes PATCH/DELETE for authorized
frontend preflights. CSRF is not an authorization substitute; all routes also authenticate
and check workspace role on the backend.

No invitations or public join links are added. Milestone 05 document endpoints use the
workspace checks described below. An already authorized read can
finish while a concurrent membership removal commits. Per-workspace mutation locks
serialize writes and can become a contention point for very active workspaces. Deadlock,
serialization and lock-unavailable errors return generic retryable 409 conflicts; there
is no automatic retry of non-idempotent operations. Configure deployment request/DB
lock timeouts as appropriate. No independent production security audit has been performed.

See [API specification](api-specification.md) for contracts and consistent error responses.

## Document ingestion security (Milestone 05)

Owner/admin: upload, list, metadata, download, retry and delete. Member: list, metadata
and download only. Non-member: no document access. Every endpoint reuses authenticated
current-user resolution. Central document helpers check membership and scope lookups by
both document and workspace UUID. Upload role is checked before reading the form and
again under the workspace lock before publication. Missing/inaccessible workspaces have
identical 404 responses. No API exposes raw storage keys/paths. Document metadata excludes extracted text; authorized
search exposes bounded excerpts. Arbitrary legacy processing
error strings are redacted in responses without rewriting their stored values.

Raw request bodies are capped before multipart spooling, even without Content-Length.
Exactly one file field is accepted. File copying enforces the configured 20 MiB default
independently of headers. Safe filenames reject separators, traversal sequences, colons,
control/format characters, leading/trailing whitespace and overlong names. Storage paths
use opaque server keys only. Extension, signature/UTF-8 validation and declared MIME
compatibility are checked; application/octet-stream is allowed when content validates.
All encrypted PDFs are rejected. Deep extraction errors become safe failed statuses.

Originals reside in a private non-frontend directory with 0700 directories and 0600 files.
Descriptor-relative no-follow operations prevent symlink traversal; hardlinked/nonregular
objects are rejected. Originals publish atomically; partial uploads have eager cleanup
and durable crash-recovery reservations. Downloads open only after authorization, stream
from a pinned descriptor, force attachment/application/octet-stream and nosniff, and use
no-store. New downloads return 404 after metadata deletion; already authorized in-flight
downloads can complete while asynchronous disk cleanup runs.

Untrusted PDF parsing uses pypdf in isolated child processes, with structural validation
bounded separately from extraction. Page/stream/decompression/text/output budgets,
CPU and wall timeouts, descriptor limits and RSS monitoring reduce resource exhaustion.
Linux additionally enforces address-space limits; macOS RSS monitoring is sampled and
can overshoot between samples. Python socket creation and external JBIG2 tools are disabled;
no network fetch, attachment/script/macro execution or external-link following occurs.
Deploy production parsers in a process/container with hard memory and egress controls
for stronger isolation; this implementation is not a complete OS sandbox or malware scan.
Original PDFs can retain active content; downloads are attachments and opening them is
outside server processing. Never embed uploaded PDF/Markdown as trusted HTML.

Extracted text, headings, source references and originals are private untrusted content.
Future retrieval/AI/UI code must treat instructions within documents as data and escape
rendered text. Do not log request bodies, extracted text, filenames, paths or parser
exceptions. Workers log only fixed operational messages and return fixed failure strings.
Milestone 06 adds embeddings. Milestone 07 adds answer generation with untrusted source text and validation; no document instructions are executed.

PostgreSQL queue claims use row locks, bounded total attempts and expiring unique leases.
Finalization is fenced and atomic, preventing stale/duplicate jobs from publishing chunks.
Deletion invalidates an active worker's document/job before scheduling durable file cleanup.
A DB/storage dual-write cannot be fully atomic; cleanup intents, idempotent deletion and
live-reference checks handle partial failures. Physical deletion requires the worker and
working storage. Monitoring must alert on pending cleanup, old queued/running jobs and
terminal failures. No independent production security audit has been performed.

## Embedding and retrieval privacy (Milestone 06)

Embeddings default to disabled. Fake mode is offline deterministic lexical hashing, used
by all automated tests/evaluation. Hosted mode requires provider=openai, explicit
EMBEDDING_HOSTED_ALLOWED=true and a server-side OPENAI_API_KEY. This configuration is an
operator privacy opt-in, not a substitute for organizational/legal review or end-user
consent requirements. Hosted providers receive private chunk text and search queries.
Review provider retention, residency, access controls and contractual requirements before
production use. No live hosted request was made as part of local verification.

OpenAI calls use a fixed official HTTPS endpoint, normal certificate verification,
no redirects, no environment proxies, bounded response/input sizes and finite/dimension
validation. API keys are SecretStr, not returned or committed. Do not enable HTTP body/header
logging or APM capture for embedding requests: it can expose keys and private source/query
text. Error strings use a safe vocabulary; raw provider bodies/exceptions never reach API
responses or worker logs. Per-input UTF-8 byte and batch bounds conservatively constrain
provider token limits, without silently truncating source chunks.

All workspace members may POST search and view index status. Only owners/admins enqueue,
force-reindex or retry; role checks reuse existing workspace/document authorization. All
POSTs require session authentication, trusted Origin and the custom CSRF header, including
read-only search because it uses cookie-authenticated POST and may incur provider cost.
Foreign/missing workspace IDs and foreign/missing document filters receive consistent
404s. Membership is rechecked after provider I/O and joined again in the final SQL.
Queries are parameterized. Search returns only completed, compatible vectors for completed
documents in that workspace; no raw storage paths or unrestricted chunk dump is exposed.

Profile identity includes provider/model/revision/dimension, and provider responses must
identify the configured model. Changing configuration never falls back to incompatible
old vectors. Hosted model aliases can change upstream without a new returned name; operators
must bump EMBEDDING_REVISION and reindex for known backend/preprocessing changes. The system
cannot detect undisclosed upstream alias changes. Stale jobs are fenced by generation,
lease and document existence checks. Deletion cascades only derived vectors/jobs, preserving
original source-data restrictions. Retained embeddings are sensitive derived data and need
the same database access/backup protections as document text.

Similarity is not evidence confidence, factual verification or answer generation. Fake
mode has lexical collisions and lacks trained semantic understanding. A threshold reduces
unrelated matches but does not guarantee relevance. Search/index quotas, abuse controls,
production semantic evaluation, database RLS and a full independent audit are not added.
Existing authorization is application-enforced. Monitor hosted cost, retries, backlog and
failed indexing; bounded automatic retries do not prevent repeated authorized force rebuilds.

## Grounded generation security (Milestone 07)

The ask API preserves cookie authentication, Origin/CSRF enforcement and membership checks.
All document UUID filters are authorized before early returns; retrieval and source loading
join the authorized workspace, compatible embeddings, completed documents and current
membership. Membership/active-user/source eligibility are checked again after generation;
external source replacement and membership removal are tested. Authorization stays in server
code and parameterized SQL; generated IDs never determine database queries or permissions.

Evidence is serialized separately from system instructions and explicitly marked untrusted.
No tool runner, URL fetcher or code executor is available. Keys/settings/storage paths never
enter the prompt; literal configured-key source matches are excluded. Injection/credential
patterns are rejected in emitted claims. Every claim must be an exact quotation of sent
evidence with validated server IDs and lexical question support. Invented IDs, fabricated
claims with real IDs, malformed schema and missing references reject the entire output.
Canonical document UUID/page references replace raw source paths. Future clients must render
all answer/source metadata as plain untrusted text. These are defense-in-depth controls,
not an absolute prompt-injection guarantee or proof of semantic entailment/source truth.

Hosted answering is separately disabled by default and requires explicit opt-in and a server
secret. Questions/excerpts are transmitted externally when enabled. Responses store=false
is set, but provider retention/processing terms still apply. Fixed endpoint, no redirects, no
proxy inheritance, bounded body/attempt/token limits and hosted wall timeouts constrain I/O.
Only fixed failure codes are logged/returned; no raw response bodies, prompts or keys.
Tests block live sync/async HTTP and use offline MockTransport. No paid evaluation was run.

Generation capacity is bounded across workers using PostgreSQL session advisory locks;
transaction-pooling proxies are incompatible. Capacity is not a per-user cost/abuse quota.
Retrieval/DB pool work still requires operational statement/lock/pool timeouts; the scheduling
deadline cannot forcibly cancel synchronous retrieval. No streaming tokens or history are retained by stateless `/ask`; Milestone 08 explicitly persists conversations through separate APIs. Small synthetic tests do not constitute independent security review.
See [RAG security, limits and evaluation](rag-answer-engine.md).

## Persistent conversation privacy (Milestone 08)

Every conversation route requires the existing session and workspace membership plus exact
conversation ownership. Workspace owner/admin roles do not grant access to someone else's
research. Wrong owner/workspace and missing resources return 404. Current active-user and
membership checks are repeated after generation. Payloads cannot set owners, sender roles,
citations or generation states; existing Origin/CSRF protection and no-store policy apply.

Historical user questions are untrusted, bounded reference context in a separate prompt
field; known instruction-pattern questions are excluded. Assistant history is never sent as
source evidence. No saved quote or source ID can replace current authorized retrieval. Source
eligibility is checked again under the workspace lock before saving citations. No generated
content is persisted after revocation/deletion. Concurrent/replayed requests cannot create
duplicate turns or overwrite expired generations; failed finalization cannot mark a partial
answer completed. Tests include real independent-connection races and injected rollback.

Questions/answers and bounded cited excerpts are now persisted sensitive data. Snapshots
remain owner-private after document deletion; nullable live links distinguish unavailable
sources. Archive is not erasure. DELETE conversation hard-deletes its messages/snapshots and
idempotency records, but does not purge other conversations, backups or provider records.
No automatic TTL, source-wide history purge or per-message deletion exists. Membership
revocation removes access and does not erase history. Operators need backup/encryption and
retention policies appropriate to this data; see [conversation retention](conversation-engine.md).

Hosted opt-in can transmit bounded prior user questions as well as the current question and
excerpts. store=false does not override provider retention terms. No question/history/error
bodies are added to logs, and automated tests remain offline. Reference resolution and claim
relevance are heuristics; tests are not semantic assurance or independent security review.

## Browser integration (Milestone 09)

The web app uses existing API-host HttpOnly cookies with credentials=include and the exact
trusted frontend Origin/CSRF contract. JavaScript never reads or stores session tokens; only
theme preference goes into localStorage. Private API calls are browser-only/no-store, with
account/workspace/path-scoped in-memory reads, abort/late-response guards, cross-tab session
notifications and clearing/unmounting on logout/401. Private server HTML contains no user
payload. Backend authorization is unchanged and remains authoritative even when UI hints stale.

Source/answer/title text is React-escaped plain text, never dangerouslySetInnerHTML or untrusted
Markdown. Downloads use credentialed API responses and temporary Blob URLs. Provider keys and
backend .env are not exposed. Production documents use a fresh CSP nonce/strict-dynamic for
scripts, no unsafe-inline/eval scripts, frame denial, nosniff, referrer/device restrictions and
no-store. Styles still permit unsafe-inline; production TLS/HSTS/trusted proxy configuration
remain ingress responsibilities. No private content is sent to analytics or application logs.

Use HTTPS and same-site app/API hosts in production; do not weaken SameSite=Lax or Secure to
support unrelated sites. No proxy forwards browser credentials elsewhere. Current provider
readiness is not exposed by an API, so the UI reports this limitation and displays actual
request outcomes/offline labels. Historical quotations survive source deletion until their
conversation is erased; deletion confirmations explain that retention.

Chromium tests use only generated local schemas, temporary private storage and fake/mock
providers, block live outbound HTTP, and exercise actual CSRF/session/role boundaries. npm
audit reports five high findings along the development braces/glob/ESLint chain; no upstream
patch is listed and no force downgrade/suppression is applied. Production-only audit reports
zero findings, which is not a security guarantee. See [frontend risks/tests](frontend-architecture.md)
and [the advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No independent audit is claimed.
