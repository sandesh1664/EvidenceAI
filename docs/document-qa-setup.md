# Document QA: local setup and verification boundary

**Gemini is disabled by default. Live requests require explicit local configuration
and authorization to send document text and questions to Google.**
Backend settings are private and can change; use the configuration doctor below
to check the current profile and blockers without exposing values. Fake embeddings
and mock generation are offline test doubles, not real semantic AI. Keep actual
keys in the ignored backend environment. This guide supersedes earlier one-generation-call
probe instructions; answered Gemini turns now include a separate relevance review.

## What was repaired

The old RAG path vetoed a question unless every non-stopword occurred literally in
a source sentence, and then applied that same condition to the generated quotation.
That prevented Gemini from even seeing ordinary paraphrases. RAG also used the first
1000 characters of the search preview instead of the complete retrieved chunk.

Gemini now gets the question and bounded authorized chunk context, can select relevant
verbatim quotations, and must pass a second, independent request reviewing whether
those quotations actually answer the question and its qualifiers. A mere topical match
is insufficient. A negative/conflicting/incomplete review abstains. The server still
requires real admitted citation IDs, exact claim/support/source text, numeric qualifiers,
injection guards and current authorization/source rechecks. No prose claim absent
from the source is published. Fake/mock/OpenAI retain their existing lexical guard.

The review is a model judgment, not a formal semantic proof. Its real quality is not
established until an approved live test. Exact quotation proves provenance, not that
a document is true. Literal numeric qualifiers remain conservative; e.g. numeral/word
variants may still abstain. No claim of complete natural-language understanding is made.

## Configure privately, with all live execution blocked

Use your existing editor to add the existing key **only** to the ignored
`apps/api/.env` as GEMINI_API_KEY. Do not put it in commands, chat, Next.js variables,
Git or diagnostics. Check custody from the repository root:

```sh
chmod 600 apps/api/.env
git check-ignore apps/api/.env
```

To prepare Gemini without authorizing a request, set these non-secret values privately:

```dotenv
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_REVISION=retrieval-v1
EMBEDDING_DIMENSIONS=768
EMBEDDING_HOSTED_ALLOWED=false
EMBEDDING_BATCH_SIZE=8
EMBEDDING_PROVIDER_ATTEMPTS=1
EMBEDDING_JOB_MAX_ATTEMPTS=1
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash-lite
LLM_REVISION=2
LLM_HOSTED_ALLOWED=false
LLM_MAX_ATTEMPTS=1
LLM_MAX_OUTPUT_TOKENS=1000
GEMINI_LIVE_REQUESTS_ALLOWED=false
GEMINI_PRIVATE_DOCUMENTS_ALLOWED=false
GEMINI_FREE_TIER_CONFIRMED=false
GEMINI_DATA_TRANSFER_ALLOWED=false
```

Settings allow this **blocked** local configuration, including a missing key, so the
app can explain what is missing. Model IDs/dimensions and development/test-only scope
are still validated. Enabling the live master flag requires the key and all existing
hosted/free/privacy opt-ins. Every transport checks authorization again; blocked
configuration does not permit a request. No setting was enabled by this implementation.
Normal workers leave Gemini indexing jobs queued without consuming attempts while
configuration/consent is blocked. The synthetic probe uses only its own disposable scope.

Run the configuration doctor; it never opens a DB connection or contacts Google:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m app.gemini_setup
```

It prints safe provider/profile/configuration status and key-presence only. A
configuration-only result is not model access, free-tier confirmation or live success.
Keep database, storage, authentication and SMTP settings unchanged.

## Exact local startup (three separate terminals)

Stop each existing owned API/worker/frontend process using Ctrl-C in its terminal
before restarting; do not kill unrelated services or reset Docker volumes.

API:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Worker:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m app.document_worker
```

Frontend:

```sh
cd "$(git rev-parse --show-toplevel)"
npm --prefix apps/web run dev -- --hostname 127.0.0.1 --port 3000
```

Use http://localhost:3000 consistently. Retain the existing local insecure-HTTP cookie
opt-in and trusted localhost origin; never apply that to hosted environments. If signup
email is needed, use the existing validated TLS receiver/API launcher from
[local-signup-email.md](local-signup-email.md) instead of the plain API command.
The implementation did not restart development services or change existing accounts.

## Reindex existing extracted documents

No existing user document was reindexed or transferred by this work. Switching models
creates a different provider/model/revision/dimensions profile, not new extraction.
The pgvector schema already supports 768 dimensions; no migration/reset is needed.

After a separate approval for private document processing and correct configuration:

1. Restart API and worker with identical embedding settings.
2. Sign in and open the intended workspace's Documents page.
3. Confirm **Extraction complete**. Use **Index document** for the new active profile.
4. Observe **Pending indexing**, **Indexing**, then **Indexed**. Readiness additionally
   requires allowed/configured providers. Offline profiles are explicitly labelled.
5. If an earlier index failed, inspect the safe error, fix its cause and use Retry
   indexing within budget. Rebuild index is an explicit authorized new generation when
   a failed job exhausted its budget; it does not reset extraction or delete old profiles.
6. Select that source in Research and ask a specific question about its contents.

Existing endpoints: POST `/api/v1/workspaces/{workspace_id}/documents/{document_id}/index`
with `{}`; GET the same path for active-profile state; POST `.../index/retry` for eligible
failed jobs; POST index with `{"force":true}` for an explicitly confirmed rebuild.
Use the authenticated application controls; do not copy session cookies into shell
commands or insert vectors manually. Original files, chunk IDs/source references,
processing status and old fake/OpenAI/Gemini profiles are preserved by reindexing.

The application will remain blocked for real Gemini indexing/answers until consent
and model availability are established. A queued job while live calls are blocked
is not an actual indexing success. Backend readiness describes local index/configuration,
not remote availability or answer quality. The source filter must include the intended
document; an empty explicit selection intentionally returns no evidence.

## Diagnosis

- **Indexing blocked:** the Documents row now displays the embedding provider's
  configuration blocker separately from extraction and overall research readiness.
  A queued job with a blocked provider cannot advance by waiting. Index/retry/rebuild
  controls are unavailable while that embedding provider is blocked. An answer-only
  blocker does not prevent a working embedding provider from completing its index.
- **Pending indexing with no provider blocker:** ensure the separate
  `python -m app.document_worker` process is running from `apps/api`. Uvicorn and
  Next.js do not run the queue. API and worker must use the same current settings.
- **Local browser connection error:** open `http://localhost:3000`. Development
  navigation from `127.0.0.1:3000` now redirects to the trusted localhost origin
  when using the default localhost API. Hosted and same-origin deployments keep
  their configured origins.
- **fake/mock selected:** offline lexical selection, not Gemini; do not interpret its
  failure on paraphrases as a live model result.
- **missing key/configuration/consent:** doctor and authenticated Research readiness
  explain the blocker. Blocked calls never silently use mock output.
- **invalid key / project denied / model unavailable:** fixed safe error category;
  check the key/project privately. Raw provider messages/headers are not displayed.
- **429/free quota exhausted:** no automatic engine/job retry; do not enable billing or
  substitute a paid model. Reconfirm eligibility before an explicit retry.
- **no passages:** verify active-profile indexing, selection and query relevance.
  Extraction alone does not make a document searchable.
- **unsupported/abstained answer:** generator/review could not support the requested fact.
  Try a specific source or wording; the system will not invent a citation or answer.
- **timeout/review failure:** bounded failure, no silent fallback. Two calls share the
  configured output-token cap and total adapter timeout. A review can exhaust its own
  reserved output budget and safely fail rather than publish unchecked text.

Use the existing metrics plus `gemini_http_requests_total{operation=...}` for actual
HTTP attempt counts (including answer and review), and token usage aggregated across
both calls. Counters are process-local, not durable billing reconciliation.

## Future live synthetic approval — NOT executable without separate approval

Checked vendor contracts: [embeddings](https://ai.google.dev/api/embeddings),
[generateContent](https://ai.google.dev/api/generate-content), and
[model lifecycle](https://ai.google.dev/gemini-api/docs/deprecations), 2026-10-21.
`gemini-embedding-001` supports the configured reduced dimensions; generation uses
the explicitly configured supported model on v1beta. For new local setups use
`gemini-3.5-flash-lite`; it supports the current structured output and relevance
review workflow. Access to older `gemini-2.5-flash` is restricted to prior users,
and a listing in model metadata does not prove that generation is available to
the project. There is no automatic switch between models after a failed request.
Current project access, free quotas and billing eligibility are NOT VERIFIED. See
[pricing](https://ai.google.dev/gemini-api/docs/pricing). No alternative model is chosen.

A new approval must name both endpoints and **three embedding requests plus up to two
generateContent requests**, not the old one-call scope. Inputs are exactly:

- `Synthetic probe sentence about solar panels.`
- `Solar panels convert sunlight into renewable electricity.`
- `What do solar panels convert?`

A synthetic local TXT file is created/uploaded/extracted only inside disposable
resources; Google receives text parts, static instructions/schema, citation IDs and
candidate exact quotations for review. No original files/private documents are sent.
Generation output is capped at **512 tokens shared across both calls**; each call's
input is independently capped by the existing 12000-token conservative bound, so the
two generation calls can total up to 24000 input tokens. All provider/job attempts are
one. Free-tier content may be used for Google product improvement. **Maximum monetary
cost is not established**, so approval cannot imply a free operation. Proceed only after
confirming free eligibility/quota for both models and approving a zero-cost synthetic scope.

After that separate approval only, configure key + hosted/free/privacy/live flags true
while keeping GEMINI_PRIVATE_DOCUMENTS_ALLOWED=false, then use the owned isolated runner:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-qa-approved-live -- \
  apps/api/.venv/bin/python -m app.gemini_probe --authorize-synthetic-transfer
```

The probe now exercises real local upload/extraction/index/retrieval/citation services.
Its external HTTP boundary is real only when explicitly authorized; offline tests mock
that boundary. It refuses development database targets, stops on failure/quota, emits
aggregate counts/usage only and cleans its schema/files/container. It has NOT been run
live. Private application documents require another approval and the separate private
content flag. Production remains FAIL / BLOCKED; no deployment is authorized.
