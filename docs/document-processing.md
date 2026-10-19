# Document processing and operations

Milestone 05 supports PDF, UTF-8 TXT and Markdown in authenticated workspaces. Owners
and admins upload/retry/delete; all members list/view/download; non-members have no
access. The API contract is in [api-specification](api-specification.md). No uploads are
publicly served, and no embeddings, AI answers, OCR, invitations or frontend are added.

## Request and storage lifecycle

1. Authenticate and check workspace write permission before reading multipart data.
2. Enforce an ASGI raw-body cap (file limit + 64 KiB envelope), including chunked bodies.
   Accept exactly one file part, then copy in <=64 KiB blocks with the exact file limit.
3. Reject unsafe names/unsupported extensions and commit an opaque storage-key cleanup
   reservation before writing any file. The original name is metadata only.
4. Write a private .part file, hash SHA-256 while streaming, fsync, validate actual content,
   and atomically publish the opaque original. PDF structural/encryption validation runs
   in a bounded child; text validation checks UTF-8 and binary/control content.
5. Recheck current workspace role under its row lock, lock the cleanup reservation, verify
   the published original, reject same-workspace duplicate bytes, and atomically create
   Document plus its queued DocumentJob while removing the reservation.
6. Return 202 pending. Extraction happens only in a separate worker.

Unsupported extensions return 415, unsafe names/content/encoding/malformed or encrypted
PDFs return 422, oversized files/bodies 413, duplicates 409, storage problems 503. Parser
validation has a short time budget and does not extract full PDF text. Malformed deeper
content detected only during extraction becomes a recorded failure. All encrypted PDFs,
including empty-password PDFs, are rejected. Valid zero-page PDFs fail extraction as empty;
textless/image-only PDFs report that OCR is not supported.

Filename checks reject traversal sequences, slash/backslash, colon, control/format
characters, surrounding whitespace and >255 characters. Accepted extensions are .pdf,
.txt and .md, case-insensitively. Actual content is checked independently of browser MIME;
application/octet-stream is accepted with valid content. Markdown also permits text/plain.
Text inputs are strict UTF-8, allowing a leading UTF-8 BOM, rejecting NUL/binary controls
and common disguised binary signatures. Text/Markdown normalize CRLF/CR to LF and retain
headings and paragraph boundaries. No document contents are logged.

The initial storage implementation is a private local directory, default
<project>/storage/documents, with flat random 32-hex keys. Files/directories use 0600/0700.
Every path component is opened relative to a directory descriptor with no symlink following;
symlink roots/objects, nonregular files and hardlinks are refused. Publication uses
link/unlink plus fsync without overwriting a pre-existing key. Downloads open a pinned
descriptor only after membership/context checks and stream attachments with nosniff and
no-store. No API response exposes a key/path. Do not configure a publicly served directory.
On platforms with symlinked path components, supply the canonical private path.

DocumentStorage exposes stage/open/promote/delete. A future S3 adapter must preserve
opaque keys, private access, seekable parser input, publication/cleanup semantics and
idempotent deletion. API/worker processes on separate hosts currently need a shared
private filesystem at the same configured root; host-local independent disks do not work.

## Durable queue and worker

The queue is PostgreSQL-backed, rather than Redis-backed. This keeps document/job creation
in one database transaction without a broker dual-write gap, while meeting durability,
separate-worker, retry and recovery requirements. PostgreSQL and Compose are already
present; port 5433 and the existing volume are unchanged. No Redis connection is required.
This is a polling queue suitable for the current ingestion foundation, not a claim of
unbounded throughput. Migration c52d8e7a901b creates jobs, chunks and cleanup intents.

From apps/api, using its virtual environment and backend environment:

```sh
python -m pip install -r requirements.txt
python -m alembic current
# Review the migration and generated SQL before applying:
python -m alembic upgrade a31f8c9d204e:c52d8e7a901b --sql
python -m alembic upgrade head
python -m app.document_worker
```

Run the worker separately from Uvicorn, under a process supervisor with restart-on-failure.
Multiple worker processes are supported. Each process handles one document per tick;
idle polling waits one second. SIGTERM/SIGINT requests graceful shutdown after the bounded
current tick. Force-killing leaves leases/reservations for later recovery. No processing
occurs while no worker runs. Use the same DATABASE_URL and DOCUMENT_STORAGE_ROOT for API
and workers. The parser child receives neither DB credentials nor application env secrets.

```sh
python -m app.document_worker --once
python -m app.document_worker --status
```

--once performs at most one due cleanup and one processing claim, then exits. --status
prints job counts by state and cleanup_pending, without original content or filenames.
Monitor the supervised process plus queued/failed counts, expired running leases, oldest
queued available_at, and due/failed storage_cleanup attempts. API /health remains a
configuration-independent liveness check, not worker readiness. Logs contain only a safe
fixed operational failure message; alert on that message and sustained backlog.

| Document state | Job state | Meaning |
| --- | --- | --- |
| pending | queued | Durable job waiting for availability |
| processing | running | Unique expiring lease and attempt start committed |
| completed | done | Chunks and completion committed atomically |
| failed | failed | Terminal extraction error or exhausted attempts |

Workers claim Document rows with FOR UPDATE SKIP LOCKED, then lock their job row in that
order. Retry/delete also lock the document before the job (after workspace authorization),
preventing lock inversion. Claim commits the lease UUID/deadline, increments total attempts
and records last_processed_at, then releases the transaction before parsing. A worker
verifies original SHA-256 before extraction. Finalization locks the document/job, verifies
workspace, lease UUID, running state and unexpired deadline, replaces chunks, and commits
completion atomically. Deleted documents and stale/expired leases cannot publish results.

Default leases last 120 seconds; parser timeout is 30 seconds and configuration requires
at least 15 seconds margin. No heartbeat is needed for the bounded current parser. Under
abnormal suspension/lease expiry another worker can recover the job, but only one current
lease can publish. A stale parser may still consume resources until killed/its bound is
reached; result fencing protects database correctness.

Storage/unexpected transient failures automatically requeue with exponential backoff capped
at 300 seconds, until the configured total attempt limit (default 3). Parser/encoding/OCR/
resource-limit failures become failed immediately. Interrupted leases are reclaimed and
consume another attempt; exhausted interrupted jobs become failed without more parsing.
Manual retry is owner/admin only, failed state only, and below the same lifetime attempt
limit. It preserves the document UUID; pending/processing/completed/exhausted retries are
409. Permanently unsupported inputs may fail again. Retry cannot replace original bytes.

## Parsing and resource limits

pypdf is pinned and runs in an isolated Python child process. Structural upload validation
and full extraction have separate deadlines. PDF text is extracted page-by-page, with
one-based page numbers and source references. Textless PDFs report OCR unsupported; there
is no external OCR/image tool or network fetch. PDF scripts, embedded attachments, macros
and external links are never executed or followed; originals can still contain active
content and should only be opened by users with appropriate viewer protections.

The child uses a restricted environment, no core dumps, CPU/output/descriptor budgets,
parser-specific decompression/stream/page-tree/work limits, disabled Python sockets and
no external JBIG2 executable. The parent kills/reaps the child on timeout or excessive RSS,
polling at roughly 20 ms. Linux adds RLIMIT_AS. macOS does not reliably support that limit,
so RSS supervision can overshoot between samples. Use OS/container memory limits and
network-denied parser isolation for stronger production containment. This is not a malware
scanner, a full OS sandbox, or independently audited production security.

## Chunk provenance

Chunking uses characters, not model tokens. The default window is 1600 characters with
200-character overlap. Order is page order then source order. Markdown ATX headings start
new sections; overlap does not cross those section boundaries or PDF pages. Useful heading
and paragraph text remains intact, though windows can split long paragraphs/words. Empty
and whitespace-only chunks are skipped. Chunk indexes are contiguous from zero and UUIDs
are deterministic UUID5(document_id,index), making reruns reproducible with the same
parser/configuration/input. Changing parser/version/configuration can change extraction.

Each row stores document UUID, workspace UUID, chunk index, private text, one-based PDF
page (null for TXT/MD), optional section, source_ref, char_start/end and timestamps. Source
references are document:<UUID>/page:<N> for PDF and document:<UUID> for text. Character
offsets are zero-based/end-exclusive within normalized page text or the normalized whole
TXT/Markdown source, not original byte offsets. They reproduce exact source substrings.
A composite FK prevents document/workspace misattribution; unique document/index prevents
repeated chunks. There is no public chunk-content endpoint or embedding generation.

## Storage/DB failure recovery and deletion

An upload reservation becomes due after one hour. Invalid/failed uploads clean files and
reservation eagerly if DB/storage is available. A process crash leaves the reservation,
and the worker later removes staged/published orphans. Publication locks the reservation
and checks the file; if recovery already removed it, the request fails instead of creating
broken metadata. Cleanup checks for live metadata before unlinking, protecting against
ambiguous commit outcomes. Files predating this milestone without managed keys are not
silently migrated/deleted; operator reconciliation is required for such legacy originals.

Authorized deletion atomically removes chunks, job and Document and creates a due storage
cleanup intent. New lookups/downloads immediately return 404. A parsing worker cannot
recreate chunks after deletion. An already open authorized download can finish. The worker
unlinks the original and any partial file idempotently, then removes the cleanup intent.
If unlink/DB commit fails, the intent persists and retries with backoff capped at one hour,
without a retry-count cutoff. Physical removal is therefore eventual and requires healthy
storage plus a worker. Cleanup rows are independent of workspace metadata. Do not run
ad-hoc filesystem purges: use the reservation/live-reference protocol to avoid races.

Legacy pending documents are not automatically queued by migration; reviewed operator
backfill is needed if such data exists. A legacy failed document may be retried under
the API policy if its original/key is compatible. Migration refuses duplicate legacy
workspace checksums for explicit operator resolution. It never merges or deletes them.

## Settings

Process env overrides apps/api/.env. Numeric values are validated and cross-setting
constraints prevent invalid overlap or leases shorter than processing timeout + 15s.

| Variable | Default |
| --- | --- |
| DOCUMENT_STORAGE_ROOT | <project>/storage/documents; absolute, private, outside frontend |
| DOCUMENT_UPLOAD_MAX_BYTES | 20971520 (20 MiB), maximum configurable 100 MiB |
| DOCUMENT_CHUNK_SIZE | 1600 characters |
| DOCUMENT_CHUNK_OVERLAP | 200 characters, less than size |
| DOCUMENT_MAX_CHUNKS | 10000 |
| DOCUMENT_MAX_PAGES | 500 |
| DOCUMENT_MAX_TEXT_CHARS | 2000000 |
| DOCUMENT_VALIDATION_TIMEOUT | 5 seconds |
| DOCUMENT_PROCESSING_TIMEOUT | 30 seconds |
| DOCUMENT_PARSER_MEMORY_MB | 512 MiB |
| DOCUMENT_MAX_ATTEMPTS | 3 total attempts |
| DOCUMENT_JOB_LEASE_SECONDS | 120 seconds |

The file byte limit differs from extracted-text/page/chunk limits: an accepted upload
can later fail processing. Per-user/workspace quotas, antivirus, OCR, S3, text-search,
embeddings, metrics export and automatic retention of completed/failed jobs are not
implemented. Configure ingress connection/rate/body/time budgets as appropriate; the
application byte cap does not by itself prevent slow clients or aggregate upload abuse.

## Verification and isolated tests

Run python -m pytest -q, python -m alembic current, python -m alembic check,
python -m pip check and git diff --check. The original 210 tests remain unchanged.
New tests use authenticated TestClient requests, real parser subprocesses, temporary
private storage and real PostgreSQL rollback fixtures. Worker/upload races use separate
connections in unique disposable schemas with finally cleanup; no development records
or Docker volumes are destroyed. CREATE SCHEMA privilege is needed only for these tests.

References: [pypdf resource configuration](https://pypdf.readthedocs.io/en/stable/modules/configuration.html),
[PostgreSQL queue locking](https://www.postgresql.org/docs/17/sql-select.html).
