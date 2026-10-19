# Retrieval engine and operations

Milestone 06 adds versioned chunk embeddings and authenticated exact cosine retrieval.
The retrieval service does not generate answers; Milestone 07 composes it in a separate RAG pipeline. Source chunks, page/section references and originals
remain unchanged by indexing. Search returns only source excerpts from authorized workspaces.

## Providers and explicit configuration

EMBEDDING_PROVIDER defaults to disabled: no automatic indexing or outbound calls. Fake
mode uses versioned deterministic signed token hashing, normalized to unit length. It is
an offline lexical test double, not a trained semantic model and not a replacement for
production semantic evaluation. All automated tests and the supplied benchmark use fake
or HTTP MockTransport; no paid API credentials/network calls are required.

For local offline development, set these backend environment values and run the worker:

```dotenv
EMBEDDING_PROVIDER=fake
EMBEDDING_MODEL=fake-hash-v1
EMBEDDING_REVISION=1
EMBEDDING_DIMENSIONS=128
```

The hosted implementation uses OpenAI's fixed HTTPS /v1/embeddings endpoint through httpx.
After an appropriate privacy review, an operator can configure:

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_REVISION=deployment-v1
EMBEDDING_DIMENSIONS=1536
EMBEDDING_HOSTED_ALLOWED=true
# Supply OPENAI_API_KEY via backend secret management, never in Git/frontend.
```

text-embedding-3-large is also supported, up to 3072 dimensions; small allows up to 1536.
The dimensions parameter and float response format are explicit. The returned model name
must match configuration. Input/output counts, response index coverage and ordering,
finite numeric values, dimensions and nonzero norm are validated. Vectors are normalized
before writing pgvector values. Credentials are SecretStr and never included in API output.
The provider disables redirects and environment proxy inheritance and bounds response size.
No live hosted-provider test was performed during implementation; contract/failure tests
use mocked transport, so actual account access and model availability need deployment testing.

Hosted providers receive full selected chunk text and user search queries. Review consent,
retention, residency, provider access and contractual requirements before enabling it.
The hosted_allowed setting is a deliberate configuration guard, not a complete privacy
approval workflow. Do not capture HTTP bodies/authorization headers in logs or APM.

## Profile and dimension isolation

A profile is SHA-256 of the canonical provider/model/revision/dimension tuple. Those values
are stored in embedding_profiles and used for every queue and retrieval operation. An
operator-managed revision must change when preprocessing or a known model revision changes.
Hosted aliases can change invisibly upstream; the engine cannot detect a backend change
that preserves the returned model name. Operators must manage revisions/reindexing for
such changes rather than treating aliases as immutable weights.

chunk_embeddings is separate from document_chunks, keyed by (chunk_id,profile_id), with
VECTOR, dimension, status, generation, generated_at and safe error. Source text/references
are not duplicated or rewritten. The column has no fixed typmod so multiple profiles can
coexist. Composite profile/dimension FKs plus vector_dims/nonzero checks protect writes.
Search binds exactly one profile/dimension and guards its cast before cosine calculation,
preventing cross-profile or cross-dimension comparisons. A config change yields [] until
new-profile embeddings exist; there is no fallback to old incompatible embeddings.

## Durable indexing lifecycle

The existing PostgreSQL queue design is extended with embedding_jobs, unique on document
and profile. No Redis is added. Successful extraction, chunks and enabled-provider enqueue
commit together. Migration does not backfill existing documents or send their contents
outbound. Use index APIs to schedule already completed documents.

A worker takes a Document row lock with SKIP LOCKED, then its EmbeddingJob lock. It records
an expiring lease UUID, job generation, attempt increment and last attempt timestamp, then
commits before any provider call. All mutation/finalization paths retain Document-before-Job
ordering. Source text is read in bounded batches, leases renew between batches, and each
validated vector batch commits independently after rechecking document existence/workspace,
completed extraction, generation, lease token and unexpired deadline.

State is queued/running/done/failed. Chunk status is pending/completed/failed. A completed
extraction can have incomplete indexing. On a later batch failure, previously completed
vectors remain indexed and searchable. A retry skips completed chunks from the same target
generation. Forced same-profile rebuilds retain older usable vectors; successful replacement
batches move to the new generation. Status distinguishes all usable indexed_chunks from
current_generation_chunks. Partially completed documents can therefore yield partial results.

Provider calls have bounded attempts (default 3), exponential delays and a shared retry
budget. HTTP 429/5xx, timeouts and transport errors are transient; numeric Retry-After is
honored with a five-second cap. Validation/auth/model failures are permanent. Raw HTTP bodies
and exceptions are discarded. Transient exhausted provider calls requeue the durable job
with capped exponential backoff while its per-generation job attempt budget remains
(default 3). Permanent failures become failed immediately. Total possible provider calls
per failed batch can be provider attempts multiplied by durable attempts. No unbounded
automatic retry loop exists. Default httpx timeouts are per operation; the retry budget is
checked between calls/sleeps and is not a hard kill of a blocked DNS/network operation.
Leases fence late results even if network work outlasts its budget.

Abandoned running leases become reclaimable and consume another attempt; exhausted jobs
become failed without another call. Only one current lease can publish. A suspended/slow
old request can still consume provider resources until its timeout; late results are
ignored after recovery. No automatic cancellation/heartbeat thread is added.

## API and operations

All paths require valid session authentication and workspace membership. POSTs additionally
require trusted Origin and X-CSRF-Protection: 1. Every member may search/read index status;
only owner/admin may index/retry/force rebuild. Refer to [API specification](api-specification.md)
for exact request/response fields and status codes.

- POST /api/v1/workspaces/{workspace_id}/search: query (1–2000 characters, <=6000 UTF-8 bytes),
  limit (1–50, default 10), optional up to 50 distinct document_ids. [] matches none.
- GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/index: active-profile status,
  generation, attempts, chunk totals/current progress and safe error.
- POST the same /index path with {}: idempotently enqueue a completed document with chunks.
  Repeated requests do not duplicate/reset queued/running/done/failed jobs.
- POST /index/retry: failed jobs only, below per-generation attempt limit; same generation
  and completed batches are preserved. Other states/exhaustion return 409.
- POST /index with {"force":true}: new generation/reset attempts for done/failed jobs.
  Queued/running jobs return 409; live work is never silently cancelled.

Changing provider/model/revision/dimension creates a new profile. Queue each eligible
document under that configuration, then run workers with the same configuration. Old
profiles and vectors are retained until source deletion; there is no retention/purge API.
Workers only claim their configured profile. Switching configuration does not silently
drain jobs for an older profile using a different provider. Explicit force rebuild can
reset a generation's attempt budget; authorized repeated requests still require cost/abuse
controls in production.

```sh
cd apps/api
source .venv/bin/activate
# Review d64a9f2b830c and generated SQL before applying:
python -m alembic upgrade c52d8e7a901b:d64a9f2b830c --sql
python -m alembic upgrade head
python -m app.document_worker
# Monitor from another shell:
python -m app.document_worker --status
python -m app.document_worker --once
```

A normal worker tick handles due file cleanup, extraction, then one embedding job. It can
process multiple bounded batches for that indexing job before moving on. Monitor queued/
running/failed counts per profile, expired leases, attempts, oldest availability, provider
rate limits/cost and search latency. /health remains API liveness, not index readiness.
Multiple workers are supported with row locks. No additional Compose services, ports or
Docker volume changes are needed.

## Search correctness and performance

Search first authorizes workspace membership and validates every document filter against
that workspace. Invalid/foreign IDs use the same 404 error. If no completed indexed
candidates exist, [] is returned without making a query-provider call. Otherwise it releases
the DB transaction, embeds the query, reauthorizes, and executes a parameterized pgvector
query joining current membership, document and source chunk context. Only completed
compatible vectors for completed documents in that workspace qualify. No raw storage
paths are returned. Provider failure gives a safe generic 503.

Ranking is exact cosine distance (<=>), with similarity = 1-distance. The default minimum
similarity is 0.25; it is a filter, not calibrated confidence. Returned scores are clamped
to [-1,1]. Ties use document UUID, chunk index then chunk UUID. Results include original
filename, <=1000-character source excerpt, page/section/source_ref and model identifier.
No answer, factual claim or citation beyond stored provenance is invented. Relevant evidence
can still be missed by the model/threshold, and unrelated matches remain possible.

The initial implementation deliberately uses exact filtered nearest-neighbor search.
It provides a clear ranking baseline and avoids approximate post-filter recall loss for
small workspaces. B-tree profile/status and existing workspace/document indexes restrict
candidates. Distance work grows with candidate count and dimensions; no throughput claim
is made from the tiny benchmark. HNSW can reduce query latency on larger corpora at the
cost of index memory/build time and approximation/filter tuning. A future migration must
create dimension/profile-specific typed cosine indexes, choose supported vector/halfvec
limits, evaluate recall under workspace/document filtering and benchmark representative data.
A single HNSW index on this unconstrained mixed-dimension column is not appropriate.

Deletion removes derived embedding rows with chunks and indexing jobs with documents via
new CASCADE child FKs only; original RESTRICT source constraints are unchanged. Workers
cannot resurrect deleted data or overwrite newer generations. Embeddings and excerpts are
sensitive derived data requiring the same DB/backup access controls as source text. An
already authorized read may complete while concurrent deletion commits.

## Repeatable synthetic evaluation

Dataset: apps/api/evaluation/retrieval.json, containing ten synthetic source documents
(four two-document topics plus two distractors), duplicated in an inaccessible workspace.
Eight labeled queries have two relevant document IDs each. Evaluation runs fake mode with
pinned retrieval settings in a uniquely named disposable PostgreSQL schema; it never
uses normal user documents/storage or paid APIs. It indexes via the real durable service
and searches through actual PostgreSQL <=> operations, then removes its schema in finally.
CREATE SCHEMA privilege is required for this benchmark and concurrency tests only.

```sh
python -m app.evaluate_retrieval --output ../../docs/retrieval-evaluation.json
```

Recall@K is relevant returned / all labeled relevant. Precision@K is relevant returned / K,
including missing result slots. MRR@K averages reciprocal rank of the first relevant
result within returned top K (zero if none). Latencies include local authorization, fake
query embedding and SQL, not hosted network latency. Isolation checks include every result
set plus unauthorized workspace and foreign-document-filter rejection. Automated tests also
verify metric arithmetic and rerun the full synthetic dataset.

Observed run (see [raw measured report](retrieval-evaluation.json)):

| Metric | Result |
| --- | --- |
| K / queries | 2 / 8 |
| Recall@2 | 0.9375 |
| Precision@2 | 0.9375 |
| MRR@2 | 1.0 |
| Mean latency | 3.3549 ms |
| Median / p95 latency | 2.9477 / 6.1754 ms |
| Workspace isolation | 10/10 checks passed |

One battery query returned only one of its two relevant documents above threshold, so
recall/precision are below 1. This is a small lexical test-double evaluation, not proof
of general semantic relevance, production security or hosted model accuracy. Hosted
providers require a separately approved evaluation using representative authorized data;
no such live evaluation was run. Latency varies by host/load; regenerate the report when
benchmarking a new configuration or implementation.

## Settings and limits

| Variable | Default / meaning |
| --- | --- |
| EMBEDDING_PROVIDER | disabled; fake or openai opt-in |
| EMBEDDING_MODEL | fake-hash-v1; hosted supported models explicit |
| EMBEDDING_REVISION | 1; operator-managed non-secret model/preprocessing revision |
| EMBEDDING_DIMENSIONS | 128; 8–3072, provider limits also enforced |
| EMBEDDING_HOSTED_ALLOWED | false; must be true for hosted mode |
| OPENAI_API_KEY | absent; backend secret required for hosted mode |
| EMBEDDING_BATCH_SIZE | 16; maximum 32 |
| EMBEDDING_INPUT_MAX_BYTES | 8000; strict per-input UTF-8 byte cap, never truncate |
| EMBEDDING_HTTP_TIMEOUT_SECONDS | 10; HTTP per-operation timeout |
| EMBEDDING_REQUEST_BUDGET_SECONDS | 30; shared call/retry scheduling budget per batch |
| EMBEDDING_PROVIDER_ATTEMPTS | 3; maximum 5 |
| EMBEDDING_JOB_MAX_ATTEMPTS | 3; maximum 10 per generation |
| EMBEDDING_JOB_LEASE_SECONDS | 120; at least 2*request budget+15 |
| SEARCH_MIN_SIMILARITY | 0.25; range 0–1 |

The UTF-8 byte cap is a conservative token bound for these hosted models; with <=32
inputs the configured maxima stay below the per-request aggregate token cap. Large source
chunks exceeding the input cap fail indexing rather than being silently truncated; reduce
chunk size before ingestion or explicitly plan a future split/indexing strategy. Unit
normalization handles scale but not incompatible model spaces. Fake token collisions,
application-level authorization (no DB RLS), absent search/index quotas, exact-search scale,
old-profile retention and nondeterministic upstream aliases are current limitations.
No independent security audit is claimed. Milestone 07 adds answer generation in a separate service.

References: [official OpenAI embedding request contract](https://developers.openai.com/api/reference/resources/embeddings/methods/create),
[pgvector cosine/exact and approximate search](https://github.com/pgvector/pgvector),
[pgvector SQLAlchemy support](https://github.com/pgvector/pgvector-python).

## Use by grounded answers (Milestone 07)

The ask pipeline reuses search with its own RAG_MIN_SIMILARITY (default 0.35), bounded
retrieval count (default 6, maximum 12), optional authorized filters and active profile.
The existing search API/worker/index contracts are unchanged. Source text, embeddings,
profiles and applied migrations are preserved. Only indexed completed evidence is admitted.

The RAG service deduplicates returned chunks/text, assigns deterministic citation IDs and
truncates 1,000-character search excerpts further to its context budget. Empty/unusable
evidence avoids generation. Model output cannot broaden the retrieval query. A second
authorized source lookup after generation invalidates changed/deleted sources. Exact source
quotations and lexical support checks are intentionally conservative and can over-abstain;
retrieval score is not answer confidence. A conflicting source outside the retrieved context
cannot be detected. See [RAG answer engine](rag-answer-engine.md) and its separate
[13-case synthetic evaluation](rag-evaluation.json), which reports one retrieval false abstention.

## Milestone 10 evaluation and telemetry

Retrieval and embedding stages now record safe durations, result totals and adapter
attempt/failure counts under the HTTP request correlation context. The versioned offline
runner compares 128/256-dimensional fake profiles, adds nDCG/empty-result/filter metrics,
protects report history and enforces configurable CI thresholds. See
[evaluation framework](evaluation-framework.md); fake lexical scores do not establish
hosted semantic quality. Existing exact authorized vector search behavior is unchanged.
