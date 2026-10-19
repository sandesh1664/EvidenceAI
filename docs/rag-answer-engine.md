# Grounded answer engine — Milestone 07

`POST /api/v1/workspaces/{workspace_id}/ask` implements stateless question answering.
The response contains validated **extractive** claims: each claim is an exact source
quotation, followed by server-added citation markers. It does not currently produce
free-form summaries, paraphrases, calculations or multi-source deductions. This deliberate
constraint makes claim support checkable beyond simply checking citation ID existence.
Stateless `/ask` persists no question, prompt or answer. Milestone 08 adds separate private conversation APIs with saved history.

## Request flow

1. Authenticate using existing server-side sessions and enforce the existing Origin/CSRF
   middleware. Owner, admin and member can ask; outsiders receive 404.
2. Authorize the workspace and every document filter, including before early abstention.
3. Reuse `search_service.search`: active embedding profile/dimensions, completed chunks
   and documents, exact pgvector cosine threshold, bounded deterministic ranking. An empty
   filter selects no documents. Disabled embeddings produce retrieval_unavailable.
4. Reload source chunks using workspace, current membership, active user and profile joins.
   Preserve server metadata; use only the first 1,000 characters provided by search.
5. Deduplicate chunk IDs and exact repeated text; assign C1, C2, … in retrieval order.
   Truncate evidence prefixes to the serialized context budget without breaking Unicode.
6. Abstain before generation when evidence is empty, relevant terms are absent, or the
   conservative conflict guard detects contradictory numeric/negative statements.
7. Release the source transaction. Acquire a nonblocking PostgreSQL advisory generation
   slot on a separate autocommit connection; call the configured provider within a deadline.
8. Reauthorize after generation, refresh ORM state, and ensure each sent excerpt still
   belongs to an eligible source. Deleted/changed sources cannot support a returned answer.
9. Strictly validate generation and construct claim IDs, display text and metadata on the
   server. Any invalid claim/citation rejects the entire output. No unvalidated partial answer
   is returned. Request IDs are generated on the server.

The model receives a JSON user payload containing `question` and evidence objects with
only `citation_id` and `text`. Filenames, storage keys, database credentials, membership
records, backend settings and the API key are not included in the prompt. System instructions
explicitly designate retrieved text as untrusted data and prohibit instructions/tools/URLs
from becoming actions. A configured API key found literally inside a source excludes that
source from context. There are no model-directed database calls, URL fetches or tool dispatch.

## Provider configuration

Both hosted embeddings and hosted answering are separately opt-in; both default disabled.
The backend shares `OPENAI_API_KEY` when either hosted mode is enabled. Keep this key out of
frontend variables, browser requests and Git. No paid calls are made by automated tests.
Existing httpx provides the maintained Responses HTTP interface; no new SDK dependency.

For deterministic offline operation, set `EMBEDDING_PROVIDER=fake`, index synthetic documents
using the existing worker, and set:

```dotenv
LLM_PROVIDER=mock
LLM_MODEL=mock-extractive-v1
LLM_REVISION=1
```

The mock ranks safe source sentences by question-term overlap and stably selects one. It
abstains for no candidate and one-term queries with multiple distinct candidate sentences.
Fake embeddings use lexical hashing; neither mock component predicts hosted semantic accuracy.

Hosted configuration example (backend only):

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4-mini-2026-03-17
LLM_REVISION=1
LLM_HOSTED_ALLOWED=true
# Supply OPENAI_API_KEY through your backend secret manager.
```

Pin an available Responses model supporting strict structured outputs. Model aliases may
resolve to a different response model; identity mismatch is rejected, so prefer snapshots.
`LLM_REVISION` is an operator-controlled non-secret contract/prompt revision. The response
identifier is `provider:model@revision`; it does not imply a model fingerprint was verified.
For models that explicitly support temperature, set `LLM_TEMPERATURE_SUPPORTED=true` and
`LLM_TEMPERATURE` between 0 and 2. Otherwise omit temperature, including for the sample above.

The hosted request uses `POST https://api.openai.com/v1/responses`, a strict JSON schema,
`store=false`, `stream=false`, no tools, a bounded `max_output_tokens`, no proxy inheritance
and no redirect following. Only a completed assistant text JSON response for the configured
model is accepted. Refusals, tool calls, incomplete/truncated output, invalid JSON, extra
fields, inconsistent usage and oversized bodies fail closed. Optional input/output/total
usage counts are returned after validation; mock usage is null. No estimated costs are invented.

429/5xx, transport failures and timeouts permit bounded retries. Other HTTP failures and
malformed/refused outputs do not. Backoff is exponential (0.5s, 1s, capped at 2s), honoring
numeric Retry-After up to 3s if the remaining request budget permits. Error bodies and
provider exception strings never reach responses or logs. Each hosted call has an asyncio
wall timeout around the streamed HTTP body, in addition to httpx operation timeouts.

`store=false` disables response storage requested through this API; it does not establish
zero retention or override the provider's contractual data handling. Hosted embeddings send
the question, and hosted generation sends the question plus selected document excerpts.
Assess applicable provider/project retention and processing terms before opt-in.

## Citation validation

Provider output must follow `GroundedOutput`: `outcome` and `claims`, each claim containing
`text` and one or more `{citation_id, quote}` supports. Answers require nonempty claims;
abstentions require none. Fields are strict and unknown fields are rejected.

For each claim, the validator requires:

- Every support uses an ID from the exact context sent in this request.
- Claim text equals its supporting quote, and that quote occurs exactly in the admitted
  source prefix. A correct C1 with fabricated text is rejected.
- All meaningful question terms, including numbers and negative qualifiers, occur in the
  quote. An instruction/credential/citation-marker pattern guard must also pass.
- Claim/support counts and text lengths stay within the schema and configured maximum.

This lexical relevance rule is intentionally conservative. It can reject synonyms,
inflections, multilingual queries or valid questions containing additional qualifiers.
It does **not** establish semantic entailment, source truth, completeness or that an exact
quotation answers the user's intent. Negation scope, numerical relationships, sarcasm,
misleading quotations and complex contradictions need stronger evaluation. The conflict
heuristic compares similar relevant statements for different numbers or negative polarity;
it can miss conflicts and over-abstain, especially when evidence is outside the retrieval
threshold/count/prefix/token budget. No general hallucination prevention is claimed.

Server-assigned A1, A2, … claim IDs map to citation IDs. Repeated citations are deduplicated
in first-use order, with all associated claim IDs. Metadata comes exclusively from the
server: document/chunk UUIDs, filename, page/section, supporting excerpt, character start/end
and canonical `document:<UUID>/page:<N>` source reference. Character offsets are Python Unicode
character offsets within extracted source text, with an exclusive end. Multiple quotes from
one chunk return that bounded context as the excerpt so every associated quote is available.
Original storage keys and filesystem paths are never source locations. Treat filenames,
sections, excerpts and display text as untrusted plain text when building a future client;
do not interpret them as HTML, instructions or executable links.

## API and outcome states

Request:

```json
{"question":"What do solar panels convert?","document_ids":null,"retrieval_limit":6}
```

Successful response shape:

```json
{
  "answer":"Solar panels convert sunlight into renewable electricity. [C1]",
  "status":"answered",
  "reason":"validated_extracts",
  "claims":[{"claim_id":"A1","text":"Solar panels convert sunlight into renewable electricity.","citation_ids":["C1"]}],
  "citations":[{
    "citation_id":"C1",
    "document_id":"11111111-1111-4111-8111-111111111111",
    "chunk_id":"22222222-2222-4222-8222-222222222222",
    "filename":"solar.txt","page_number":1,"section":"Energy",
    "source_ref":"document:11111111-1111-4111-8111-111111111111/page:1",
    "supporting_excerpt":"Solar panels convert sunlight into renewable electricity.",
    "char_start":0,"char_end":55,"claim_ids":["A1"]
  }],
  "retrieved_evidence_count":1,"model_identifier":"mock:mock-extractive-v1@1",
  "usage":null,"request_id":"33333333-3333-4333-8333-333333333333"
}
```

| HTTP | status | Meaning |
| --- | --- | --- |
| 200 | answered | Every emitted extract and reference passed validation |
| 200 | insufficient_evidence | Empty/irrelevant/ambiguous/conflicting evidence, source changed, or model abstained |
| 503 / 504 | retrieval_unavailable | Retrieval/revalidation failed, or retrieval exceeded scheduling deadline |
| 503 / 504 | provider_error | Provider disabled/failed, malformed or unsupported output, budget failure; 504 for timeout |
| 429 | provider_error | All shared generation slots occupied; Retry-After: 1 |

Abstentions/failures return empty claims/citations and an explicit message. Auth/input errors
retain existing FastAPI detail responses: 401 session missing/invalid, 403 CSRF, 404 inaccessible
workspace/filter, 422 invalid body/UUID. Post-generation membership revocation similarly
returns 404 with no generated content. Normal ask envelopes include `X-Request-ID` matching
the body and the API's existing `Cache-Control: no-store` policy. Retrieved count is the number
of admitted deduplicated evidence items, not all matching database rows. Model identifier
names the configured provider even when an early abstention avoided calling it.

## Limits and operations

| Setting / request field | Default | Allowed bounds / behavior |
| --- | --- | --- |
| question | required | Trimmed, 1–2000 characters and <=6000 UTF-8 bytes; control characters rejected except tab/newline |
| document_ids | null | At most 50 unique UUIDs; [] intentionally selects nothing |
| retrieval_limit | 6 | Strict integer 1–12, clipped to server limit |
| RAG_RETRIEVAL_LIMIT | 6 | 1–12 |
| RAG_MIN_SIMILARITY | 0.35 | 0–1; overrides search threshold for ask only |
| RAG_CONTEXT_TOKEN_BUDGET | 4096 | 128–16000 |
| RAG_INPUT_TOKEN_BUDGET | 12000 | 2048–32000, >= context budget+3000 |
| RAG_MAX_CLAIMS | 4 | 1–6; <=600 characters/claim and <=4 supports/claim |
| LLM_MAX_OUTPUT_TOKENS | 1000 | 128–4096 |
| LLM_TIMEOUT_SECONDS | 15 | 0.1–60 per hosted call |
| LLM_MAX_ATTEMPTS | 2 | 1–4 including initial attempt |
| RAG_REQUEST_TIMEOUT_SECONDS | 45 | 1–120; scheduling deadline shared across retrieval/generation/retries |
| RAG_CONCURRENT_GENERATIONS | 4 | 1–8, all workers must use the same value |

Token accounting uses the UTF-8 byte length as a conservative bound for byte-level BPE;
this is deliberately more restrictive than tokenizer-exact accounting. Evidence is budgeted
as serialized JSON. The complete question/prompt/system/schema plus a 256-byte framing
reserve is checked separately before generation. An accepted maximum-length question may
still exceed the configured combined input budget; this returns provider_error/provider_budget
without calling a provider. Output has schema/text/body byte limits as well as the provider
output-token setting. Real usage counts are not inferred from byte bounds.

The overall deadline prevents new generation/retry work after expiry and caps hosted call
wall time. Existing synchronous SQL, pool acquisition and embedding retrieval are checked
when they return, and cannot be forcibly interrupted by this layer. Configure PostgreSQL
statement/lock timeouts and embedding timeouts appropriate to production; this is not a hard
wall-clock guarantee for the entire HTTP request. Disconnected synchronous clients may leave
a bounded hosted call running until completion/timeout; no SSE cancellation is implemented.

Generation capacity uses session-scoped `pg_try_advisory_lock` locks, shared across workers
on the same PostgreSQL instance/database. No rows or migrations are required. A dedicated
connection is held in autocommit for each generation and released in `finally`; failed unlock
invalidates the connection before returning it to the pool. Do not use transaction-pooling
proxies for these session locks. Reserve pool capacity for source revalidation and existing
workers; coordinate these slots across deployments and leave headroom for traffic. This is
not a per-user quota or a bound on hosted query embeddings/retrieval requests.

`evidenceai.rag` logs only request UUID, fixed status/reason, elapsed milliseconds, evidence
count and provider name. In-process metrics expose outcome counters and aggregate milliseconds
through `rag_service.metrics.snapshot()` for instrumentation; they reset on worker restart
and are not a distributed telemetry endpoint. No document text, questions, answers, raw HTTP
errors, keys or raw provider usage objects are logged. Reverse proxy/APM/SQL logging settings
need the same privacy controls. No persistent cost ledger is added. Stateless `/ask` retains no conversation state; the separate conversation layer saves explicit history.

## Verification and evaluation

Run from `apps/api`:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m app.evaluate_rag --output ../../docs/rag-evaluation.json
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m pip check
git diff --check
```

Tests block both sync and async live httpx transports. Hosted requests use explicit
MockTransport fixtures, including cancellation of a slow response, retry classification,
request privacy fields, strict schema, model/usage identity, refusals and malformed bodies.
API tests exercise real PostgreSQL vectors and cookie sessions, role access, CSRF, foreign
filters, malicious sources, missing/invalid citations, unsupported claims, numeric/negative
qualifiers, context budgets and post-generation authorization/source changes. Independent
connections exercise capacity exclusion and externally committed source replacement. The
existing session-expiry regression uses database time to avoid Docker/host clock skew.

The synthetic dataset is `apps/api/evaluation/grounded_answers.json`; the CLI creates only
`eval_rag_<UUID>` and removes that schema after completion, leaving public records untouched.
Its checked-in report covers 13 cases (including two adversarial generated outputs):

- Expected outcome and exact answer correctness: 12/13 (92.31%).
- Valid source references: 4/4; expected claim/source support: 4/4.
- Unsupported emitted claims: 0/4; insufficient-evidence detection: 6/6.
- One valid backup-region answer was missed by fake-hash retrieval at the 0.25 threshold.
- Mean/median/p95 latency: 6.5118 / 5.3762 / 17.1991 ms on this local run.

Metrics compare hand-authored expected status, claim text and supporting document, and
independently check returned chunks/excerpts. They are a small English lexical fixture,
not a representative production benchmark. They do not establish semantic accuracy,
hallucination prevention, prompt-injection immunity, production latency or independent
security verification. No live paid-provider evaluation was performed. Rerun the report
when comparing configurations; latency depends on host/load and actual hosted calls.

SSE was evaluated and deferred: emitting draft tokens would expose claims before validation.
A future design must buffer/validate claim units, send typed events with explicit final state,
handle disconnects/cancellation and account for provider errors before declaring completion.
No streaming endpoint is registered. Milestone 08 now supplies conversation history. Semantic entailment checks,
source-level contradiction resolution, per-user spend/abuse quotas, production corpus/load
benchmarks and independent security review remain future work.

References: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
[Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create),
[GPT-5.4 Mini model](https://developers.openai.com/api/docs/models/gpt-5.4-mini).

## Implementation file map

| Action | Paths (relative to repository root) |
| --- | --- |
| Create API contract | `apps/api/app/api/routes/ask.py`, `apps/api/app/schemas/ask.py` |
| Create pipeline and safeguards | `apps/api/app/services/rag_service.py`, `rag_context.py`, `citation_validation.py`, `generation_capacity.py` in the same services directory |
| Create providers | `apps/api/app/services/llm_providers.py` |
| Create tests/evaluation | `apps/api/tests/test_rag.py`, `apps/api/app/evaluate_rag.py`, `apps/api/evaluation/grounded_answers.json`, `docs/rag-evaluation.json` |
| Create guide | `docs/rag-answer-engine.md` |
| Update wiring/config | `apps/api/app/main.py`, `apps/api/app/core/config.py`, `apps/api/.env.example` |
| Update test isolation | `apps/api/tests/conftest.py` (offline provider defaults and async HTTP guard), `apps/api/tests/test_auth.py` (database-clock expiry fixture; original assertion preserved) |
| Update existing documentation | `README.md`, `docs/architecture.md`, `docs/security.md`, `docs/api-specification.md`, `docs/retrieval-engine.md` |

No requirements, frontend files, existing migrations or local `.env` secrets were changed.
No Git commit or push was performed.

## Completed verification

On 2026-10-19, the completed implementation passed:

- Full pytest: **498 passed**, comprising all 398 existing tests plus 100 RAG tests,
  in 14.87 seconds. One existing Starlette/httpx deprecation warning remains.
- Alembic current: `d64a9f2b830c (head)`; check: no new upgrade operations.
- pip check: no broken requirements.
- Ruff checks for all new Python files and `git diff --check`: passed.
- Read-only before/after comparison: all 12 original public tables (empty at baseline),
  migration revision and pgvector 0.8.7 preserved. Test/evaluation schemas are disposable.

No migration was created/applied, no original records were deleted, and no Docker volumes
were changed. The only existing-test adjustment uses PostgreSQL time for an expired-session
fixture after host/database clock skew exposed a false failure; its rejection assertion and
production authentication behavior remain unchanged.

## Milestone 08 conversation composition

The separate conversation service now calls ask with optional bounded, non-authoritative
prior user questions. Its latest question stays unchanged in the prompt; English referential
queries may augment retrieval with prior user questions within search limits. Reference
words are omitted from lexical support matching only when admitted history is available.
Assistant answers and historical snapshots are excluded from prompts/retrieval evidence.
Fresh authorized workspace/profile retrieval, current filters and existing citation validation
apply every turn; a second source check precedes atomic saved citation creation. Stateless
`/ask` request/response and no-history behavior remain unchanged.

New settings control recent message count (6), serialized history token/byte budget (1500)
and durable conversation turn lease (180s). History counts in the combined input budget.
Hosted prompts with history add explicit system separation rules; test fixtures verify that
the current question/history/evidence stay separate and no tools/storage are requested.
Persistence, idempotency, ordered pair reservations, owner privacy, failure/recovery, archive
and snapshot retention are specified in [conversation engine](conversation-engine.md).
The current migration is `6f22cc4c46ad`; Milestone 07's verification above is historical.

## Milestone 10 evaluation and telemetry

Stateless ask request_id now matches the validated HTTP support ID. Safe answer-outcome,
RAG/generation duration, adapter attempt/failure, validated usage and citation rejection
metrics complement existing bounds/validators. Saved replay keeps its historical result
ID. The extended offline benchmark covers provider/retrieval outages and numeric,
misleading, cross-workspace and deleted-source guards; semantic judgments remain
unverified. See [evaluation framework](evaluation-framework.md) and
[observability](observability.md). No hosted requests are required.
