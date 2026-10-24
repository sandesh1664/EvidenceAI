# Local Gemini integration

Current document-QA repair and exact setup: [document-qa-setup.md](document-qa-setup.md).
Gemini now uses an additional bounded relevance-review request before publishing an
answered extract. The future synthetic scope is three embedding and up to two generation
requests; earlier one-generation-call instructions below are superseded. Live calls
remain unauthorized. Blocked local Gemini configuration can now start for diagnostics
without granting transport permission.

Current safety controls and the unexecuted approval checkpoint are in
[local-gemini-setup.md](local-gemini-setup.md). The additional default-off
`GEMINI_LIVE_REQUESTS_ALLOWED` master gate and separate
`GEMINI_PRIVATE_DOCUMENTS_ALLOWED` gate supersede the earlier opt-in recipe below.
Live requests remain unauthorized; do not enable either flag automatically.

This integration uses Google's HTTPS REST API through the existing httpx dependency;
there is no new SDK, frontend key, migration or production deployment. Disabled,
fake/mock and OpenAI configurations remain supported. Gemini is rejected in staging
and production. Production release remains **FAIL / BLOCKED**.

## Availability and cost checkpoint (2026-10-21)

The [vendor lifecycle page](https://ai.google.dev/gemini-api/docs/deprecations)
currently lists gemini-embedding-001 until May 14, 2028, but restricts 2.5 Flash access
to prior users. A new project may therefore be unable to use the requested generation
model. No alternate model is selected automatically.

The [pricing page](https://ai.google.dev/gemini-api/docs/pricing) lists free-tier
2.5 Flash generation. The current page does not list gemini-embedding-001 pricing;
its original [GA announcement](https://developers.googleblog.com/en/gemini-embedding-available-gemini-api/)
describes a free starting tier, which does not establish current project eligibility.
Before authorizing a probe, check the exact project's tier, billing association,
model access and nonzero free quota in Google AI Studio. A key or model listing alone
does not prove calls are free. If eligibility for either operation cannot be confirmed,
leave the opt-ins false and make no requests. Free-tier content may be used to improve
Google products; do not send private documents without explicit authorization.

## Private configuration

Edit the existing ignored `apps/api/.env` in your local editor, never paste a key into
chat, terminal arguments, frontend variables or Git. Set its file permissions:

```sh
cd "$(git rev-parse --show-toplevel)"
chmod 600 apps/api/.env
git check-ignore apps/api/.env
```

Add `GEMINI_API_KEY` privately. Only after the cost/privacy checkpoint, configure:

```dotenv
APP_ENV=development
GEMINI_FREE_TIER_CONFIRMED=true
GEMINI_DATA_TRANSFER_ALLOWED=true
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_REVISION=retrieval-v1
EMBEDDING_DIMENSIONS=768
EMBEDDING_HOSTED_ALLOWED=true
EMBEDDING_BATCH_SIZE=8
EMBEDDING_PROVIDER_ATTEMPTS=1
EMBEDDING_JOB_MAX_ATTEMPTS=1
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
LLM_REVISION=1
LLM_HOSTED_ALLOWED=true
LLM_MAX_OUTPUT_TOKENS=1000
LLM_MAX_ATTEMPTS=1
```

The two Gemini confirmation flags are operator attestations, not a billing API or a
provider-side spending cap. Do not set them for a paid project. They authorize the
configured local application to transfer supplied questions, admitted evidence and
indexed chunk text; they are not per-document access grants. Workspace authorization
still applies. Start with synthetic data only. Keep database, storage, auth and TLS
settings unchanged. Do not print the environment or run verbose HTTP diagnostics.

## Bounded synthetic probe

Before starting a development worker, explicitly authorize only the synthetic probe:

```sh
cd "$(git rev-parse --show-toplevel)"
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-live-owned \
  -- apps/api/.venv/bin/python -m app.gemini_probe --authorize-synthetic-transfer
```

It refuses a development database target, uses a new scratch schema in the runner's
owned tmpfs container, and sends at most three embedding requests and one generation
request (all attempts set to one). It embeds a synthetic sentence, indexes a synthetic
chunk through the authorized indexing service, retrieves it and validates citations
through the normal RAG path. Only aggregate result, provider identities, request
counts and token counts are printed. No key, response text or vectors are printed.
It stops on its first failure, drops only its own schema, and the runner verifies and
removes its own container. A failed generation or no answer is BLOCKED, never a mock
success. The command performs real external requests only when all opt-ins and the
key are configured. Do not run it until both operations are confirmed free.

## Restart local API and worker

Stop each existing process using Ctrl-C in its own terminal. Do not use broad kill
commands. In the API terminal:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

If using local signup email, retain the TLS mail receiver and launch the API through
the existing `infra/development/mail.py api` command in
[local-signup-email.md](local-signup-email.md); that command loads the same backend
settings while adding the validated local SMTP process settings.

In a separate worker terminal, after explicitly authorizing the documents it may
process:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m app.document_worker
```

Stop either with Ctrl-C. Next.js needs no key or provider configuration. Its existing
localhost:3000 frontend displays the server-returned embedding/model identities.
Avoid launching duplicate workers while changing profiles. Existing pending document
processing may also run when a worker starts; review your local queue first.

## Index existing extracted documents

No document was reindexed or transferred by this implementation session. After
explicitly authorizing a particular document for Google processing, sign in normally
and use its existing Index action (or the same-origin authenticated API UI). Existing
endpoints are:

- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/index` with `{}`.
- `GET` that same path to observe the selected profile's state and indexed chunk counts.
- `POST .../index/retry` after resolving a failed attempt, within the existing job budget.
- Explicit `{"force":true}` rebuilds only the selected profile; it is not necessary
  merely to switch from fake to Gemini.

The document must already have completed extraction. The worker reads its existing
chunks and writes a **new** profile; chunk IDs, source references, document status,
files and previous fake/OpenAI vectors are preserved. The vector column is untyped
pgvector with an 8–3072 dimension constraint and per-profile dimension checks; 768
needs no migration. Exact search casts only compatible-profile vectors. Profile
identity hashes provider, model, revision and dimensions. The `retrieval-v1` revision
records this adapter's document/query task semantics; change it if semantics change.
Never copy vectors between profiles or manually update processing states.

Use Search and Research for that workspace after indexing is done. Queries use
`RETRIEVAL_QUERY`; chunks use `RETRIEVAL_DOCUMENT`. Responses retain the existing
conservative extractive policy: supported verbatim quotations with server-mapped
citations. This is not unconstrained summarization or semantic entailment validation.
Missing/ambiguous evidence abstains; malformed or invented citations fail closed.
Authorization is checked before retrieval and again after remote I/O.

## Limits and diagnosis

Batches respect the existing configurable 1–32 limit. Inputs remain bounded by the
existing 8000-byte ceiling. Vectors require correct count/dimensions, finite numeric
components and nonzero norm, then are normalized (including reduced dimensions).
Responses are bounded in bytes, requests in total time, and engine/job retries in
attempts. Generation has no tools, search grounding, file upload or explicit cache;
thinking budget is zero. Token usage must balance and remain under the output cap.
The API key goes only in `x-goog-api-key` to the fixed Google endpoint; redirects and
proxy-environment inheritance are disabled, and normal TLS verification stays on.

- Invalid key/403/404/model unavailable: generic rejection, no fallback. Verify the
  project/model privately; do not paste raw diagnostic bodies. New projects may lack
  2.5 Flash access. No silent paid-model substitution is permitted.
- 429: quota exhausted, no adapter/engine/job automatic retry. Stop and confirm free
  quota before an explicit indexing retry. Do not enable billing as a workaround.
- Timeout/5xx: sanitized transient error within configured budgets; the sample uses
  one attempt. Increase limits only deliberately, considering quota.
- Dimension/profile mismatch: verify API and worker use identical settings, then
  index the new profile. Do not edit old vectors or change schemas destructively.
- Truncated/blocked/malformed output or unsupported claim: fail closed. Inspect only
  safe aggregate categories; do not log prompts, headers or provider response bodies.

To return offline, stop API/worker, set `EMBEDDING_PROVIDER=fake`,
`EMBEDDING_MODEL=fake-hash-v1`, `EMBEDDING_REVISION=1`, `EMBEDDING_DIMENSIONS=128`,
`LLM_PROVIDER=mock`, `LLM_MODEL=mock-extractive-v1`, `LLM_REVISION=1`, both hosted flags
false and both Gemini confirmation flags false. Restart processes. Existing fake
vectors are available under their original profile; documents without that profile
require the normal offline index action. No Gemini vectors are deleted.

## Offline verification

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web test
```

Pytest replaces Gemini opt-ins/key with offline placeholders before application
imports and rejects real HTTP transports; explicit MockTransport contracts exercise
Gemini without transferring data. All database tests remain disposable. See
[gemini-integration-verification.md](gemini-integration-verification.md) for actual
results and the live verification limitation.
