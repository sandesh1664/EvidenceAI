# Persistent research conversations — Milestone 08

Conversations save questions, validated answer outcomes and bounded source snapshots. They
are private to the creating user and require current workspace membership for every access.
Workspace owners/admins have no special access to another user's conversation. The existing
stateless `POST /api/v1/workspaces/{workspace_id}/ask` contract is preserved.

## Schema and integrity

Migration `6f22cc4c46ad` follows `d64a9f2b830c`. It adds three tables and indexes; it does
not alter existing tables, documents, vectors or profiles. The generated migration and its
SQL were reviewed before application. No historical data is backfilled.

| Table | Fields and invariants |
| --- | --- |
| conversations | UUID, workspace/owner RESTRICT FKs, title, created/updated/last_activity timestamps, optional archive timestamp, next_sequence. Title 1–200 trimmed characters. Next sequence starts at 1 and is odd. Composite workspace/owner/creation/UUID index supports private listing. |
| messages | UUID, CASCADE conversation FK, user/assistant role, content, positive sequence, created timestamp, pending/completed/failed generation state, optional answer status/reason/model/usage, validated claims, admitted evidence count, request UUID, original generation HTTP status, user idempotency UUID/request hash, assistant lease expiry. Unique conversation/sequence and conversation/idempotency-key constraints; partial unique index permits one pending assistant per conversation. |
| message_citations | UUID, CASCADE message FK, nullable live document/chunk SET NULL FKs and indexes, immutable original source UUIDs, citation ID, bounded quote snapshot, filename/page/section/canonical location, character offsets, ordering, validation metadata. Unique message/citation ID and message/ordering; ID/offset/order checks. |

Database checks restrict roles/states and enforce user messages at odd sequence numbers,
assistant messages at even numbers, required user idempotency/hash fields, and empty pending
assistant content with a lease. Terminal assistants require a nonempty message, answer status
and no lease. Server transactions create the pair together; direct SQL must also maintain
pairing, ownership and source/workspace consistency. There is no database RLS.

## APIs and schemas

All routes below share prefix `/api/v1/workspaces/{workspace_id}/conversations`. UUID path
parameters are validated. Existing cookie session authentication and Origin/CSRF checks apply.
Mutations require the existing `X-CSRF-Protection: 1` header. API responses remain no-store.

| Method/path | Request/query | Success |
| --- | --- | --- |
| POST prefix | `{ "title": "Research" }`; title optional, defaults to New research conversation | 201 Conversation |
| GET prefix | limit 1–100 (default 20), optional cursor UUID, include_archived boolean (default false) | 200 ConversationPage |
| GET /{id} | none | 200 Conversation |
| PATCH /{id} | Nonempty subset of title and archived boolean; nulls rejected | 200 Conversation |
| DELETE /{id} | none | 204; permanently removes conversation/messages/snapshots |
| GET /{id}/messages | limit 1–100 (default 50), after_sequence >=0 (default 0) | 200 MessagePage |
| POST /{id}/messages | MessageCreate below | 201 new terminal turn, 200 terminal replay, 202 pending replay |

All request bodies forbid unknown fields, including owner_id, role, assistant content and
client-supplied citations/status. Titles trim whitespace and reject controls. Rename/archive
can be combined. Archived conversations can be read, renamed, restored, deleted and replayed;
new turns return 409. Archiving does not cancel a turn already reserved.

Conversation fields are `id`, `workspace_id`, `owner_id`, `title`, `created_at`, `updated_at`,
`last_activity_at`, `archived_at`. ConversationPage is `{items: [Conversation], next_cursor:
UUID|null}`. Ordering is **created_at descending, UUID descending**, intentionally stable
under message activity/rename. Pass next_cursor as cursor; it is the last returned ID.
The cursor must remain an accessible conversation matching the archive filter; otherwise 404.
Deleted cursors require restarting pagination. Changing include_archived mid-pagination can
change results. Listing never includes another owner's records.

MessageCreate example:

```json
{
  "question": "What is their warranty?",
  "idempotency_key": "11111111-1111-4111-8111-111111111111",
  "document_ids": null,
  "retrieval_limit": 6
}
```

Question/document/limit validation is inherited from AskRequest: trimmed question 1–2000
characters and <=6000 UTF-8 bytes; no controls except tab/newline; <=50 unique document UUIDs;
strict integer retrieval_limit 1–12, clipped to the server limit. The idempotency UUID is
required in the body. Keep it for retries; use a new key only for a new intended turn.

TurnResponse is `{user_message: Message, assistant_message: Message, replayed: boolean}`.
Message fields:

| Field | Meaning |
| --- | --- |
| id, conversation_id, role, content, sequence, created_at | Immutable identity/order; content is the saved question or validated answer/safe failure message |
| generation_status | pending, completed or failed; user messages are completed |
| answer_status | null while pending/user; otherwise answered, insufficient_evidence, retrieval_unavailable or provider_error |
| reason, model_identifier, usage | Fixed safe outcome reason, configured model identity and validated token counters/null |
| claims | Validated claim IDs/text/citation IDs; empty for user, pending, failed and abstained messages |
| retrieved_evidence_count, request_id | RAG evidence count and server UUID/null for user messages |
| generation_http_status | Underlying RAG HTTP status/null, distinct from successful message-persistence HTTP status |
| citations | Ordered SavedCitation snapshots; empty until a validated answer is committed |

SavedCitation contains `id`, `citation_id`, `document_id`, `chunk_id`, `original_document_id`,
`original_chunk_id`, `filename`, `page_number`, `section`, `source_ref`, `supporting_excerpt`,
`char_start`, `char_end`, `ordering`, `validation_metadata`. Nullable live IDs describe source
existence, not renewed authorization or revalidation of an old claim. Original IDs and
canonical references remain as historical identifiers. Validation metadata records
`method=exact_quote_v1`, `validated_at` in UTC and associated `claim_ids`. This is validation
at save time, not proof of semantic entailment or source truth. Character offsets have the
same Unicode/exclusive-end semantics as stateless citations. No storage path/key is saved.

MessagePage is `{items: [Message], next_after_sequence: integer|null}`. Messages are ordered
by sequence ascending. Set after_sequence to next_after_sequence. Pages can split a saved
pair, but both messages are created in one transaction. Deleted conversations return 404.
The page never exposes lease tokens, request fingerprints or internal idempotency fields.

| Error / special response | Meaning |
| --- | --- |
| 401 / 403 | Existing authentication / Origin-CSRF failure |
| 404 | Inaccessible workspace, conversation, cursor or document filter; same response class for wrong owner/workspace and nonexistent IDs |
| 422 | Invalid UUID, body, title, pagination, key or request limits |
| 409 | Archived new submission; key reused with different payload; another turn is running (Retry-After: 2) |
| 202 | Same key/payload still pending; Retry-After: 2; no duplicate generation |
| 503 | Storage or unexpected generation failure prevented completion; fixed safe detail, no private exception string |

For a newly saved terminal turn, **HTTP 201 describes persistence**, including a saved
provider failure or insufficient evidence. Inspect assistant generation_status/answer_status,
reason and generation_http_status. Terminal retries return 200 even when the recorded
provider outcome failed. Transport/storage interruptions can return 503 after the pair has
already been reserved; retry with the same key to recover its state. POST responses carry
X-Request-ID from the assistant message. Its reservation UUID can be replaced by the actual
RAG UUID at completion; terminal replays preserve the completed UUID.

## Transaction boundaries, concurrency and recovery

1. Authorize and lock the workspace, then lock/reload the owned conversation. All writes
   use this order. Active user and current membership are checked, including after I/O.
2. Expire any stale pending turn using PostgreSQL clock_timestamp. Compare an existing
   idempotency key's canonical SHA-256 payload hash. Exact replay returns the original pair;
   mismatches return 409. Document filter order is normalized for hashing; null and [] differ.
3. For a new turn, reject archived/busy state, validate all current filters and read bounded
   recent questions. Allocate consecutive odd/even sequence numbers, insert user + pending
   assistant together, advance next_sequence and commit. No partial pair survives rollback.
4. Release the transaction and run existing RAG. No conversation/workspace lock is held
   during query embedding or generation. Independent conversations can generate concurrently
   within the existing database-wide RAG generation capacity.
5. Reauthorize and lock again. Reject deleted/inaccessible conversations; expire overdue
   generation and fence stale results. Before writing snapshots, recheck citation chunks,
   offsets, metadata, document completion and active embedding profile under the workspace
   lock. A deleted/changed/unindexed source produces an abstention instead of a stale answer.
6. Save terminal assistant content, claims, model/usage/outcome and citation snapshots in
   one transaction. A snapshot/commit failure cannot leave an answer marked completed.

Concurrent requests for the same key return the same pending/terminal pair; a different key
while a turn is running receives 409. No ordering gaps are created by rejected reservations.
A completed failed turn consumes its allocated sequence numbers; retries need a new key to
generate again. Keys/hashes remain for the conversation's lifetime and are erased on deletion.
Per-conversation generation is serialized; source retrieval and generation remain synchronous.

Pending turns have a persisted lease, default 180 seconds (allowed 150–900). The minimum
exceeds the maximum configured RAG scheduling deadline (120 seconds) by 30 seconds. PostgreSQL
time is used throughout lease operations. Message listing and message submission recover
expired pending assistants to failed/provider_error with reason generation_expired, including
archived conversations. No failed/expired request is automatically regenerated. A process
crash before finalization leaves a visible pending pair until lease expiry and the next read
or submission; no background sweeper is added. A late worker cannot overwrite the expired
terminal state. Unexpected failures mark generation_interrupted when cleanup storage is
available; otherwise the lease remains recoverable. Never store raw exceptions or drafts.

Deleting during generation removes the pair and all snapshots immediately. The in-flight
provider operation may finish, but its finalization returns 404 and cannot recreate data.
Revocation similarly prevents generated content from being persisted or returned; cleanup
can write only a fixed failure marker. Archiving permits an already reserved turn to finish
and blocks subsequent new turns. Deleting the conversation does not cancel external HTTP
processing or purge provider-side retention.

## Contextual follow-ups and budgets

The conversation layer reads at most CONVERSATION_HISTORY_MESSAGES recent message rows
(default 6, range 0–20), excludes all assistant messages and drops known instruction-pattern
user questions. Remaining user questions are admitted most-recent-first within
CONVERSATION_HISTORY_TOKEN_BUDGET (default 1500, range 0–6000). The budget counts serialized
UTF-8 bytes as the existing conservative byte-level-BPE token bound. Oversized older content
is dropped; the current question is never truncated/replaced. Zero count/budget disables
history. Prompts carry optional conversation_history separately from question and current
evidence, with an explicit system rule: historical questions are untrusted reference context,
never evidence or instructions. The combined LLM input budget includes this history.

For English reference words (it/its/they/their/them/this/that/those/these), retrieval augments
the complete latest question with bounded recent questions, respecting search's existing
2000-character/6000-byte limits. Source authorization, profile, threshold, count and **current
turn** document filters apply every time. Prior filters are not silently inherited. [] selects
no evidence; a foreign/missing current filter returns 404 before reserving a turn. Idempotent
replay is a historical read and does not require original source documents still to exist.

The mock uses the latest explicit historical subject to break candidate ties. For lexical
support checking, reference words are omitted only when bounded history exists; the model
still receives the unchanged latest question. All emitted claims must still quote freshly
retrieved, permitted evidence exactly and pass the existing source/citation checks. History
never supplies a source ID, an authorization decision, a saved answer or a quote to validation.
Deleted/unindexed sources are not revived from saved snapshots on a follow-up.

Reference handling is a conservative English heuristic, not semantic coreference resolution.
Topic changes, demonstratives in explicit questions, ambiguous subjects and omitted history
can cause abstentions or wrong relevance choices even for exact quotes. Some references
simply require the user to name the subject again. No unconstrained summary, inference or
semantic entailment verifier is added. The shared strict extractive-answer limitations remain.

## Privacy and retention policy

- Conversations are owner-private within a currently accessible workspace; there is no
  sharing, admin override or ownership transfer API. Membership restoration can restore
  access; revocation is not erasure. The workspace/user RESTRICT links require explicit
  conversation cleanup before deleting an otherwise empty workspace/account.
- Save only the question, terminal answer/outcome/claims, sanitized usage and bounded cited
  excerpts with location metadata. Do not snapshot full documents or provider request/error
  bodies. Excerpts are at most the already admitted search/context prefix; citations can
  share a bounded chunk excerpt for multiple claims. No unvalidated draft is stored.
- **Document deletion does not erase historical quotations.** SET NULL removes live links;
  original IDs, filename, excerpt and validation metadata remain privately readable. They
  describe historical evidence, not a currently available authoritative source. The original
  document download URL may no longer work. Archive also retains everything.
- Retention is explicit owner-managed lifetime: keep history until DELETE conversation,
  which hard-deletes its messages, snapshots and idempotency records in one DB transaction.
  No automatic TTL, trash, legal hold, per-message erasure or cross-conversation source purge
  is implemented. To erase a document's historical quotations, delete each containing
  conversation. Operator backup/WAL retention and external provider retention are separate;
  an API DELETE is not guaranteed immediate erasure from backups.
- Hosted RAG opt-in still sends the latest question/current excerpts externally. Saved
  conversation operation can additionally send the admitted prior user questions. Responses
  uses store=false; provider processing/retention terms still apply. Mock/offline mode makes
  no paid calls. Questions, excerpts and history are not added to application logs.

Apply deployment access controls, encrypted storage/backups, provider policy and retention
procedures appropriate to this newly persisted sensitive data. These implementation tests
are not independent security verification or a production accuracy/load assessment.

## Tests and operation

Run from apps/api with the existing virtual environment:

```sh
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m pip check
git diff --check
```

The migration was reviewed before upgrade and contains only new tables/indexes plus the
Alembic revision update. Do not downgrade a populated conversation deployment without an
explicit retention/migration plan. Existing migration files were not edited.

Tests preserve the existing 498 cases. New real-PostgreSQL API tests cover ownership, all
routes' session/CSRF checks, filters/cursors, sequencing, idempotency, budgets, fresh follow-up
retrieval, snapshots after deletion/unindexing, archive/erase, DB constraints and rollback.
Independent-connection HTTP tests gate actual mock generation to exercise same-key replay,
competing-key exclusion, deletion/revocation/archival during provider I/O and stale lease
fencing. HTTP transports remain blocked except explicit offline MockTransport fixtures.
Tests create disposable schemas or use rollback transactions; no development rows/volumes
are reset. No live paid-provider or independent security evaluation was performed.

Remaining operational work includes a background recovery sweep if required, asynchronous
job delivery/cancellation, rate/storage/spend quotas, production locking/load evaluation,
stronger semantic reference/support checks, automatic retention and backup erasure tooling,
and a future validated streaming design. Synchronous retrieval can outlast its scheduling
budget until it returns; configure DB/pool/provider timeouts as described in the RAG guide.

## Implementation and verification record

| Files | Change |
| --- | --- |
| `apps/api/app/models/conversation.py`, `app/schemas/conversation.py`, `app/api/routes/conversations.py` (under apps/api) | New persistence models, strict request/response schemas and seven authenticated endpoints |
| `apps/api/app/services/conversation_service.py`, `conversation_context.py` in the same services directory | New reservation/finalization/idempotency/lease, pagination, lifecycle and bounded reference history |
| `apps/api/alembic/versions/6f22cc4c46ad_research_conversations.py` | Reviewed additive migration, applied to the existing database |
| `apps/api/tests/test_conversations.py`, `test_conversation_concurrency.py` in the same tests directory | 97 new cases, including independent connection races |
| `apps/api/app/core/config.py`, `apps/api/.env.example`, `app/main.py`, `app/models/__init__.py` under apps/api | Configuration defaults and model/router registration |
| `apps/api/app/services/rag_service.py`, `rag_context.py`, `llm_providers.py` in the same services directory | Optional bounded history composition; no-history stateless behavior retained |
| `docs/conversation-engine.md` | New implementation/API/privacy guide |
| `README.md`, `docs/architecture.md`, `database-design.md`, `security.md`, `api-specification.md`, `rag-answer-engine.md` in docs | Updated architecture, schema, API and retention documentation |

Verified on 2026-10-19:

- Baseline before implementation: 498 passed. Final full suite: **595 passed**, one existing
  Starlette/httpx deprecation warning, in 18.02 seconds. No original test was edited.
- Alembic current: `6f22cc4c46ad (head)`; Alembic check: no new upgrade operations.
- pip check: no broken requirements. New/changed service/schema/route/test Ruff checks
  and git diff --check pass.
- Read-only before/after hashes/counts preserve every original public row in all 12 tables
  (empty at baseline) and pgvector 0.8.7. Only the intended migration revision advanced.

No frontend, local .env secret, existing migration or dependency file was changed. No
Docker volume was reset; no original development row was deleted. No commit or push was made.
