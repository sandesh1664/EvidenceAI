# Gemini integration verification — 2026-10-21

Local implementation and offline validation only. Baseline HEAD:
`ef91f507146e02b15eb81f50f2aa9043f350cbad`. Pre-existing staged audit code/evidence
and unpublished reports were left intact; no commit, push, deployment, release-gate
change, database migration or development document reindex was performed.

## Implementation

- `apps/api/app/core/config.py`: Gemini provider literals, backend SecretStr key,
  explicit free-tier/data-transfer attestations, existing per-provider hosted opt-ins,
  allowlisted model IDs/dimensions, local/test-only environment restriction.
- `apps/api/app/services/gemini_providers.py`: official HTTPS REST
  `batchEmbedContents` and `generateContent` adapters. Normal TLS verification,
  header-only key, no redirects/environment proxy, bounded response/time/attempts.
  Document/query tasks are separate; validated vectors are normalized.
- `embedding_providers.py`, `search_service.py`: Gemini factory and query dispatch;
  existing profile hashes, chunk references and dimensional compatibility preserved.
- `llm_providers.py`: Gemini factory and safe quota category, no mock fallback.
- `embedding_jobs.py`: sanitized quota category; quota errors are non-transient and
  therefore do not trigger automatic job retry. Existing ownership/fencing preserved.
- `rag_context.py`: excludes admitted context containing either configured provider
  key. Existing citation validation and authorization/recheck behavior are unchanged.
- `core/telemetry.py`: fixed Gemini provider labels; no prompt or header telemetry.
- `app/gemini_probe.py`: explicit synthetic-only disposable acceptance command,
  at most three embedding and one generation request, no retries, aggregate-only
  stdout. It refuses a development target before constructing an engine.
- `tests/conftest.py`: overrides inherited Gemini key/opt-ins with offline values;
  the existing no-live-HTTP fixture and disposable DB guard remain active.
- `tests/test_gemini.py`: synthetic MockTransport provider contracts plus real
  disposable PostgreSQL indexing/retrieval/RAG, existing-vector preservation,
  unauthorized workspace access and profile mismatch coverage; bounded probe exercised
  offline. No real Google calls in pytest.
- `.env.example` and `docs/gemini-integration.md`: disabled defaults, private setup,
  exact local launch/reindex/offline rollback and cost/privacy checkpoints.

## Commands and results

Initial provider suite:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-contracts -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests/test_gemini.py -q
```

PASS: 38 tests, 0.51 seconds, one existing Starlette/httpx deprecation warning.
Initial full suite before four additional probe/body-contract cases:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-backend -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

PASS: 720 tests, 30.31 seconds, same warning. Both runner receipts report zero
remaining test schemas, public users, registration intents and limiter rows,
`isolation_clean=true`, `owned_container_removed=true`. Disposable database image
ID: `sha256:633cb956dc3fa6e5930312667aec5e02264c56a59556d783de19236e8df0d6b5`.
No development volume or private storage is mounted.

Final full-suite command after adding bounded-probe and malformed/body-size cases:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-final-backend -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

PASS: 724 tests, 30.14 seconds, same existing warning. Receipt confirms zero
remaining schemas/public users/registration intents/limiter rows, clean isolation
and owned container removal. A final edge-case regression is recorded below.

```sh
npm --prefix apps/web test
```

PASS: 57 tests across six files, 1.83 seconds. The first sandboxed run could not
bind the existing synthetic loopback receiver (`listen EPERM`); it had 56 pass,
one timeout and one unhandled environment error. Rerun with local socket permission
passed unchanged. No frontend source changes were required. Browser acceptance and
frontend build were not rerun for this backend-only provider addition; previous
audit results are not represented as fresh Gemini live evidence.

Fail-closed probe check:

```sh
EVIDENCEAI_TEST_DATABASE_URL='' PYTHONPATH=apps/api \
  apps/api/.venv/bin/python -m app.gemini_probe --authorize-synthetic-transfer
```

Expected exit 1 / BLOCKED; zero embedding/generation requests and no development
DB access. No live probe was attempted inside a container.

## Live API and data preservation

**Live API verification: BLOCKED / NOT VERIFIED.** Locally inspected configuration
presence only: no Gemini key, free-tier confirmation or transfer authorization was
configured in the backend `.env`. No key value was printed or requested. No real
provider authentication, model access, current free quota, billing eligibility,
semantic quality, indexing or answer was verified with Google. Zero Google provider
requests were made by this session. No existing document was sent or reindexed.

The [vendor lifecycle page](https://ai.google.dev/gemini-api/docs/deprecations)
currently limits 2.5 model access to prior users; gemini-embedding-001 is listed
through May 14, 2028. The [pricing page](https://ai.google.dev/gemini-api/docs/pricing)
lists free-tier 2.5 Flash generation but does not currently enumerate the requested
embedding model. Its older GA free-tier announcement cannot prove eligibility now.
No alternative or paid model was substituted. Owner confirmation in AI Studio and
private local key/authorization configuration are required before the documented
synthetic-only live command. An operator attestation cannot itself enforce billing.

Development database/private files were not accessed for this implementation or
verification. Tests used only generated disposable resources; old vectors are
explicitly checked unchanged during a synthetic Gemini index test. No fresh
row-hash/storage preservation comparison was made, so do not infer a new controlled
preservation PASS. Existing original reports and historical attribution limitations
remain unchanged. Normal development API/worker processes were not restarted.

## Decision

Offline functionality: PASS subject to final suite result below. Live Gemini access,
free-tier eligibility and real-provider end-to-end acceptance: NOT VERIFIED / BLOCKED.
Production release: **FAIL / BLOCKED**, with existing security and hosted acceptance
requirements unchanged. No release approval is implied by these provider contracts.

## Final validation

A final compatibility review found and covered an empty-unused-key edge case in the
context key filter. Empty keys must not cause every evidence item to be excluded.
The final command was:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-gemini-verified-backend -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

**PASS: 725 backend tests, 30.82 seconds**, including 43 new Gemini/compatibility
cases; one existing Starlette/httpx deprecation warning. The receipt confirms exit 0,
zero remaining schemas, public users, registration intents and limiter rows, clean
isolation and owned container removal.

```sh
python3 infra/security/scan_secrets.py \
  --private-directory /tmp/evidenceai-gemini-secret-gate
```

PASS: zero unreviewed findings, 320 existing exact adjudications. Unsuppressed
history/current/archive scans retain 134/134/52 reviewed detections respectively;
this is not a claim of zero raw detections. Private scan reports stay outside Git.
No policy, severity threshold or adjudication was changed. The final report/tree
was also checked with the same command using a fresh private directory.

`git diff --check`: PASS. New untracked implementation/test/report files are also
checked independently for trailing whitespace. No commit or staging operation was
performed. Final offline verdict: **PASS**. Live and production decisions above
remain **BLOCKED / NOT VERIFIED** and **FAIL / BLOCKED**, respectively.
