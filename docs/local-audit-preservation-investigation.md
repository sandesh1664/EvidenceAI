# Local audit preservation investigation — 12.9

Investigation date: 2026-10-20, Asia/Dubai. HEAD remains
`a12b93d5a6802572a21089abb99de154d9056313`, branch main. The earlier audit's
uncommitted work was preserved. No commits, pushes, history rewrites, deployment,
manual session edits, credential changes or database cleanup were performed.

## Findings and decision

**The historical changed column and writer remain NOT VERIFIED.** The original
before-snapshot contains only a count and aggregate hash per table. The after-file
contains a PASS/FAIL summary and count deltas, not row images or even a full after
snapshot. Neither contains per-row/per-column evidence. Current rows cannot recreate
those missing before-images. An independent historical backup/WAL or statement audit
could change what is recoverable, but no such evidence was supplied or reconstructed.

The original result remains **FAIL**: `auth_sessions` count unchanged, aggregate
hash changed; other 15 tables/revision/private storage matched. It was not rewritten,
reclassified as harmless, or replaced with this investigation's new result.

A new user-confirmed quiescent run produced **PASS** for all 16 database table counts
and hashes, every session-column fingerprint and the migration revision. It enclosed
682 backend tests, 57 frontend tests, 21 integrated browser cases and three runner
regressions. This is evidence for the current isolated run, not retrospective proof
of who wrote the historical session change.

| Question | Conclusion |
|---|---|
| Which historical rows/columns changed? | **NOT VERIFIED**; aggregate-only baseline cannot recover them |
| Who caused the historical change? | **NOT VERIFIED**; normal activity, user/logout/refresh, indirect reload effects or another writer cannot be distinguished |
| Can legitimate authenticated activity cause this exact kind of mismatch? | **PASS** in a disposable reproduction: `/auth/me` updates only `last_used_at`, count unchanged, strict comparison correctly FAILS |
| Does an unauthenticated `/auth/me` call change existing sessions? | **PASS** negative regression: 401, no change |
| Was a test-safety defect confirmed? | **YES**: frontend unit tests lacked a default live-fetch denial guard; safely reproduced and fixed |
| Did that defect cause the old session change? | **NOT VERIFIED**; no retained evidence connects it to that change |
| Is the new controlled database comparison equal? | **PASS**, no table/session/revision differences |
| Current private-storage comparison | **NOT VERIFIED this run**; private files were not opened, per restriction |
| Tested offline local functionality | **PASS** within executed suites; historical attribution unresolved |
| Production readiness | **BLOCKED**; existing release criteria remain unmet |

## Original evidence and recovery limits

Original files remain outside Git:

- `/tmp/evidenceai-full-audit/preservation-before.json`: original 16-table aggregate
  counts/hashes, revision and storage metadata/hash inventory. No session row images.
- `/tmp/evidenceai-full-audit/preservation.json`: original failure summary only.
- `docs/local-full-system-audit.md`, its verification/matrix and the original sanitized
  evidence directory: preserved byte-for-byte.

The current initial database-only snapshot still differed from the old baseline only
in `auth_sessions`, with count delta zero. It matched the other 15 legacy aggregate
hashes. This also checks compatibility of the new server-side hashing serialization
against the original Python-side serialization on this dataset. It does not identify
when or which historical row changed.

The old before/after file mtimes place the audit in the prior execution window; file
mtimes and test command logs do not identify a PostgreSQL session writer. No supplied
access log binds a real session to a write. Authentication telemetry is intentionally
content-free and access logging was disabled for local API fixtures.

Current PostgreSQL settings: repeatable-read/read-only snapshot transactions,
TimeZone `Etc/UTC`, `log_statement=none`, `log_duration=off`,
`log_min_duration_statement=-1`, `logging_collector=off`, and
`track_commit_timestamp=off`. These are current observations, not proof of historical
settings. No current custom trigger/rule exists on `public.auth_sessions`, and no
pg_cron/pgagent extension is installed. These observations do not exclude external
writers or reconstruct a missing historical audit trail. No logging, extensions,
roles or PostgreSQL settings were changed to obtain evidence.

## Normal session-write paths

Source review and disposable regressions establish:

- Login creates a new `AuthSession`, hashes the new session token and commits. A
  password may be rehashed only when the configured hasher requires it.
- `current_session()` checks token format/hash, expiry, revocation and active user.
- `get_current_user()` calls `touch_session()`. That issues a bound SQL UPDATE of
  `last_used_at=clock_timestamp()` and commits, including on authenticated GETs.
- `/auth/me` is one such GET; other protected endpoints also use this dependency.
- Logout sets `revoked_at` and commits. It does not delete the session.
- Expiry is checked during lookup; this reviewed implementation has no periodic
  session-deletion/refresh cleanup job. The document/embedding worker does not write
  authentication sessions.
- Frontend `SessionProvider` calls `/auth/me` on mount and explicit refresh/session
  events. An active user tab or development reload can therefore legitimately change
  a session row. This is a verified mechanism and a **historical hypothesis**, not
  attribution of the original mismatch.

The new disposable test observes only `last_used_at` changing after an actual
TestClient authenticated GET. A second test removes its synthetic cookie and proves
the unauthenticated request leaves the session unchanged. No production auth code,
expiry, revocation, touching frequency or cookie behavior was changed.

## Isolation review and confirmed correction

Backend pytest calls `activate()` before application imports; its explicit generated
loopback test URL overwrites `DATABASE_URL` and refuses unsafe targets. Schema-scoped
connections, ORM translation, raw SQL search path and cache replacement keep workers
inside the disposable database. The owned runner retains tmpfs, ownership labels,
immutable local image resolution, empty-public checks and verified cleanup.

Playwright refuses server reuse, uses API :18000 and frontend :3100, compiles the
explicit :18000 API origin and uses `.next-e2e`. It never attaches to an existing
browser profile, imports a development storage state or reads real browser cookies.
Additional contexts are fresh `browser.newContext()` calls. Worker connections use
its generated scratch schema. Real SMTP uses a generated private CA, ephemeral
loopback port and owned mailbox; it does not use the developer's receiver/inbox.
Lifecycle cleanup drops only the exact generated schema and removes owned mail and
containers. No existing services were stopped by this investigation.

A confirmed latent gap existed in **Vitest**: individual tests mocked fetch, but the
shared setup left native fetch available when a test forgot its mock. The production
client defaults to localhost:8000; an unmocked component request could reach a live
service. Node fetch does not import an actual browser cookie jar, and this is not
proof any previous test obtained a real user's session or changed it.

The regression opened a new synthetic loopback HTTP receiver on an ephemeral port.
Before the fix the receiver saw **one request** and the test failed. After adding a
default rejecting `fetch` mock in `src/test/setup.ts`, it saw **zero requests** and
passed; an explicit fetch mock still works. No reproduction contacted the development
API. The fix affects test transport only, not application behavior. This guard covers
the current fetch-based client; it is not an OS firewall or a blanket restriction on
future raw Node sockets/XHR/WebSocket code.

## New preservation capability

`infra/testing/session_preservation.py` complements the original preservation tool;
the old tool and original FAIL evidence are unchanged.

- All 16 strict count/hash comparisons remain. `last_used_at` is not ignored.
- Hashes are computed inside PostgreSQL in a repeatable-read, read-only transaction
  with a local statement timeout. Document/chunk bodies do not leave PostgreSQL.
- A separate random 32-byte private key produces HMAC row aliases and per-column
  fingerprints for every session column. Raw IDs, token hashes, cookies and values
  are not written to evidence or reports.
- Key, before/after snapshots and reports are owned mode-0600 exclusive files under
  an owned mode-0700 directory outside the repository. Existing evidence cannot be
  overwritten. Symlink reads and unsafe file permissions are refused.
- Comparisons retain an after-snapshot and identify changed columns, row additions
  and removals. Mismatched key/database contexts fail closed. Even normal session
  activity remains a strict FAIL; writer attribution is never inferred from a column.
- Private storage is explicitly NOT INSPECTED, not silently declared equal.

Keys/fingerprints remain sensitive incident evidence; do not commit, upload or share
them. The private temporary directory is not durable encrypted/offline custody.

## Controlled window and remaining limits

The owner confirmed tabs closed/no application activity. The controlled client capture
window was **20:28:40–20:30:45 Asia/Dubai** (16:28:40–16:30:45 UTC). The later listener
inventory found only PostgreSQL among the normal development ports; API/frontend/mail
were not listening at that observation. This investigation did not stop them and does
not attribute why they were absent. No user sessions were deleted/revoked or locked.
The run therefore does not prove preservation under simultaneous live user traffic.

All 16 hashes/counts and session fingerprints stayed equal; zero sessions were added,
removed or changed; revision and transaction context match. Development test-schema
count was zero before and after. Runner receipts show zero leaked scratch schemas,
empty public fixture baselines and removed containers. No owned :18000/:3100 listeners
remained. Evidence custody check matched **379** existing repository evidence/report
files plus the original private preservation inputs; HEAD stayed unchanged.

Normal future user activity can still make a strict development comparison fail.
Use a consented quiescent window and retain column fingerprints prospectively. Do not
change auth semantics, whitelist session columns, repair rows or declare old attribution
resolved to make preservation pass. Historical row/column recovery would require new,
independent evidence and a separately scoped forensic review.

See [verification and exact commands](local-audit-preservation-verification.md).
