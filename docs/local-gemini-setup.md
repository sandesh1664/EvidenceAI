# Safe local startup and Gemini approval checkpoint

Current document-QA repair and exact setup: [document-qa-setup.md](document-qa-setup.md).
Gemini now uses an additional bounded relevance-review request before publishing an
answered extract. The future synthetic scope is three embedding and up to two generation
requests; earlier one-generation-call instructions below are superseded. Live calls
remain unauthorized. Blocked local Gemini configuration can now start for diagnostics
without granting transport permission.

**Live Gemini requests remain NOT AUTHORIZED.** The owner has not confirmed free-tier
eligibility and instructed that requests stay blocked. Do not set a live flag or invoke
the probe as part of ordinary startup. No key belongs in chat, browser code, shell
arguments, logs or Git. The backend `.env` was not changed by this work.

Run commands from the existing checkout. No migration or database reset is needed
for this increment. Do not run another copy of a service on an already-used port;
stop your own existing process with Ctrl-C in its terminal before restarting.

## Offline development (current approved mode)

In the existing ignored backend `.env`, retain your actual database/storage/auth values.
For offline AI use:

```dotenv
EMBEDDING_PROVIDER=fake
EMBEDDING_MODEL=fake-hash-v1
EMBEDDING_REVISION=1
EMBEDDING_DIMENSIONS=128
EMBEDDING_HOSTED_ALLOWED=false
LLM_PROVIDER=mock
LLM_MODEL=mock-extractive-v1
LLM_REVISION=1
LLM_HOSTED_ALLOWED=false
GEMINI_LIVE_REQUESTS_ALLOWED=false
GEMINI_PRIVATE_DOCUMENTS_ALLOWED=false
GEMINI_FREE_TIER_CONFIRMED=false
GEMINI_DATA_TRANSFER_ALLOWED=false
DOCUMENT_PDF_LAYOUT=false
```

No `.env` content is printed by these commands. Use localhost consistently for browser
cookies and keep the existing insecure-HTTP opt-in confined to local development.
API terminal:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Worker terminal:

```sh
cd "$(git rev-parse --show-toplevel)/apps/api"
.venv/bin/python -m app.document_worker
```

Frontend terminal:

```sh
cd "$(git rev-parse --show-toplevel)"
npm --prefix apps/web run dev -- --hostname 127.0.0.1 --port 3000
```

For verified local signup email, use the existing TLS receiver and API launcher in
[local-signup-email.md](local-signup-email.md) instead of the plain API command.
Keep validated CA/hostname checking enabled. Stop each owned foreground process with
Ctrl-C; do not kill unrelated services or delete Docker volumes.

Sign in → workspace → Documents. Extraction complete, Indexed and Ready for research
are separate states. Use the existing authorized Index action for the selected profile,
then Search or Research. Previewing chunks and exporting a brief are local operations.
Changing providers requires restarting API and worker consistently; it does not erase
old embeddings. Do not reindex existing private documents for Gemini without a separate
approval. Existing queues may process when a worker starts.

## Future live synthetic approval — prepared, not executed

Before requesting approval, privately confirm the exact API project's tier, billing
association, model access and nonzero free quota in AI Studio. `gemini-2.5-flash`
currently has restricted prior-user access, and current free eligibility for
`gemini-embedding-001` has not been established. If either is unavailable or billable,
stop. Do not switch models or enable billing silently.

The approval request must contain all of the following:

- Endpoints: `https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents`
  and `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`.
- Synthetic embedding sentence: `Synthetic probe sentence about solar panels.`
- Synthetic indexed chunk: `Solar panels convert sunlight into renewable electricity.`
- Synthetic retrieval question: `What do solar panels convert?`
- At most **three embedding requests and one generation request**, no retries;
  generation max output 512 tokens, existing conservative input budget 12000.
- Data sent: those texts plus static system/schema instructions and local citation ID;
  no original files, private/customer content or existing records.
- Cost: **not currently established**, therefore blocked. Only proceed with confirmed
  free eligibility for both operations and an approved zero-cost scope. Flags are not
  a billing-enforcement API; a paid project must not be used.
- Free-tier data-use terms may permit Google product improvement. State that implication
  and confirm explicit synthetic-transfer approval. Private text needs another approval.

Only after approval, enter the key privately in the ignored backend `.env`, chmod it
0600, and configure the models/hosted flags/free/privacy attestations from
[gemini-integration.md](gemini-integration.md). In addition to that earlier setup,
`GEMINI_LIVE_REQUESTS_ALLOWED=true` is now required. Keep
`GEMINI_PRIVATE_DOCUMENTS_ALLOWED=false` for the synthetic probe. Normal application
Gemini use remains blocked without a separate private-content approval and flag.

The prepared command is **not authorized to run now**:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-approved-synthetic -- \
  apps/api/.venv/bin/python -m app.gemini_probe --authorize-synthetic-transfer
```

It creates only disposable records, checks indexing/retrieval/citations, reports safe
counts/identities/usage, and stops on failure. 429 stops further requests. Do not retry
until free quota and authorization are rechecked. Never run it against development.
Afterward return the master flag false unless a separately approved usage window exists.

## Configuration and troubleshooting

No credential is returned by provider status. Disabled/consent-blocked providers appear
as not configured. Index/profile mismatch requires normal authorized indexing, not SQL
vector edits. API and worker must use identical provider/model/revision/dimensions.
Quota/403/model/timeout errors stay sanitized. Missing evidence, invalid citations or
comparison coverage failures abstain rather than fall back to mock. Optional PDF layout
is not OCR; scanned documents remain explicitly unsupported. Production/staging Gemini
configuration is rejected; production release gates remain unchanged and BLOCKED.
