> Sanitized publication derivative. Original evidence remains unchanged.
> Set PROJECT_ROOT to your local checkout before using command examples.
> Only workstation-specific paths were anonymized; original results and limitations are retained.

# Local full-system audit verification

Fresh execution on 2026-10-20, Asia/Dubai. This report distinguishes current-source
tests from existing container-image smoke checks and historical release inputs.
No additional functional tests ran after the preservation failure was observed.

## Commands, results and evidence

Commands start from `"${PROJECT_ROOT}"`. Private output root is
`/tmp/evidenceai-full-audit` (mode 0700). Sanitized JSON receipts are copied separately
to `docs/evidence/local-full-audit-20261020/`; raw mail, tokens, session cookies,
credentials and private storage snapshots are not Git deliverables.

### Baseline and preservation

```sh
git status --short
git branch --show-current
git rev-parse HEAD
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --snapshot /tmp/evidenceai-full-audit/preservation-before.json
```

Branch main, HEAD `c0103321e041f31605a0ffd4c43e065bc0116381`. The working tree was
already dirty with Milestone 12.8 and local-mail work; this audit did not reset it
or execute a commit. HEAD advanced concurrently to `a12b93d5a6802572a21089abb99de154d9056313`
(`a12b93d`, prior local-mail/security checkpoint). The actor is NOT VERIFIED. Both
revisions are recorded; historical evidence and pre-existing security-policy bytes
remain unchanged.
`baseline.json` records pre-audit file digests privately. Snapshot succeeded using
repeatable-read/read-only transactions and a mode-0600 exclusive file.

After all isolated application tests completed:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --compare /tmp/evidenceai-full-audit/preservation-before.json --report /tmp/evidenceai-full-audit/preservation.json
```

**Exit 1 / FAIL.** Exact available difference: `auth_sessions` has the same count but
a changed aggregate row hash. All 16 table counts equal their before values; the
other 15 table hashes, revision and private storage contents/metadata match. No
new/deleted rows are indicated by counts, but count equality cannot exclude arbitrary
updates or balanced inserts/deletes. The table-level baseline cannot identify the
changed row, column or writer. Testing stopped; no repair/cleanup of development data
was attempted. Normal `touch_session()` commits `last_used_at` on authenticated
requests, but attributing this difference to that path is **NOT VERIFIED**.

No earlier preservation PASS has been substituted for this failed comparison.
Read-only source inspection, cleanup inventory, report preparation and static diff
review continued; no new application tests or development writes followed the failure.

### Backend suite and disposable ownership

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory /tmp/evidenceai-full-audit/backend-isolation -- apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

**Exit 0: 676 passed, 0 failed, 1 warning, 34.18 seconds.** Warning: existing
Starlette TestClient/httpx deprecation. Full authentication, workspace/document,
embedding/RAG/conversation, concurrency, observability/deployment and database-guard
suites ran. This includes the existing real TLS mail/backend cases. No manual
PYTHONPATH or inherited development database was used. Backend source did not change
later in this audit.

Receipt `backend-isolation.json` records unique container/database, immutable image,
zero remaining scratch schemas/public users/intents/limiter rows, `isolation_clean=true`
and `owned_container_removed=true`. Every browser/runtime invocation used a different
owned container and its own evidence directory. Ownership labels, tmpfs, cleanup
checks and fail-closed URL policy were not modified.

### Frontend checks and integrated browser journeys

Final commands:

```sh
npm --prefix apps/web run lint
apps/web/node_modules/.bin/tsc --noEmit --project apps/web/tsconfig.json
npm --prefix apps/web test -- --run
EVIDENCEAI_E2E_TLS_MAIL=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory /tmp/evidenceai-full-audit/browser-delivery-isolation -- npm --prefix apps/web run test:e2e
```

- Lint **exit 0**, wrapper 1.785s.
- TypeScript **exit 0**, wrapper 0.697s.
- Vitest **exit 0**, **55 passed**, 5 files, reported duration **1.69s** (wrapper 1.976s).
- Browser **exit 0**, **21 passed (1.2m)**: seven cases each in Chromium, Firefox,
  WebKit. Next.js production build/type validation completed as part of this command.
- Two new frontend config tests assert normal/test build-directory separation.
- Three new browser executions (one per engine) prove no-JS auth forms use POST,
  have no query string and do not echo the fixture password.

The actual FastAPI app listens at 127.0.0.1:18000; the built frontend at
127.0.0.1:3100. A worker thread uses real document and embedding job functions and
real database transactions. Private storage and generated `e2e_web_*` schema are
owned by the fixture. `EVIDENCEAI_E2E_TLS_MAIL=1` starts the real loopback SMTP receiver,
generates a CA/server certificate, uses the application's unmodified TLS sender,
decodes a received MIME message, validates recipient/proof and only then makes the
proof available to the browser helper. The helper reads no development mailbox.

Mail proofs are fixture files under an owned mode-0700 directory, created mode 0600;
the directory is removed by fixture cleanup. No raw proof appears in deliverables.
The :3100 browser enters proof on the verification page; the test-only approved HTTPS
email origin is not a deployed redirect. The exact developer :3000 origin and URL
are tested separately by the backend. No TLS certificate checking was disabled.

Successful browser cases execute real upload/worker/index/search/RAG/citation,
conversation refresh/archive/restore/deleted-source history, membership/ownership,
CSRF/origin/session expiration, responsive/keyboard/accessibility and recovery flows.
Deliberate browser abort/503 fault-injection cases are identified as synthetic HTTP
failures, not live provider outages. Mock embeddings/answers remain deterministic.
The existing representative pageerror assertion is not an exhaustive console audit.

Earlier results were not hidden:

1. First TLS browser run: **12 passed / 6 WebKit failures (6.2m)**. Captured
   `Loading chunk 177 failed` for an app layout bundle while dev/build shared `.next`.
   Bounded WebKit probes reproduced the missing chunk without exposing request bodies.
2. Independent `.next-e2e` build: all original **18 passed**, plus three new regression
   failures because the test expected 405 but this Next.js renders native POST as 200.
3. Corrected regression: **all 21 passed**. No retry/skip/severity suppression was added.
4. Initial post-change lint scanned generated `.next-e2e` code; adding the matching
   generated-output exclusion corrected it. Source lint then passed.

The final removal of fixed-path screenshot writes changes only diagnostic capture,
not tested assertions. Automatic trace/screenshot capture is off to avoid authenticated
artifacts. Private diagnostic logs were sanitized for synthetic password/proof strings;
`log-redaction-ledger.json` records before/after file digests and reason. Historical
repository evidence was neither sanitized nor replaced.

### Runtime, migrations, worker CLI and offline evaluation

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory /tmp/evidenceai-full-audit/runtime-final-isolation -- apps/api/.venv/bin/python /tmp/evidenceai-full-audit/runtime_probe.py
```

The private harness activated the same database guard before imports, set a canonical
owned temporary storage root, selected fake/mock providers, disabled delivery and used
only its disposable URL. It executed:

```sh
# These ran as children inside the disposable runner, with cwd apps/api:
python -m alembic current
python -m alembic heads
python -m alembic check
python -m pip check
python -m app.document_worker --status
python -m app.document_worker --once
python -m app.document_worker --metrics-file <owned-private-directory>/worker.prom
# Also started/restarted its own Uvicorn at 127.0.0.1:18001.
python -m app.evaluate --repeat 3 --thresholds "${PROJECT_ROOT}/apps/api/evaluation/thresholds.json" --output-dir /tmp/evidenceai-full-audit/evaluation
```

All **exit 0**. Revision/head `91e2b6d8c410`, no schema drift, pip dependencies
consistent. Worker heartbeat and SIGTERM succeeded; API health/ready and restart
succeeded; the pool reconnected after disposal. Uvicorn's expected SIGTERM return is
accepted after graceful shutdown. This is not a DB-server outage or full persisted
application restart test. Runtime receipt has zero leaked scratch/public fixture rows
and confirms container removal.

**68 evaluation samples**, no threshold failures, 4.495s evaluator wrapper. Metrics
are in `evaluation-summary.json`. Recall/precision 0.9375 at 128/256 dimensions;
answer correctness 0.9444444444; citation validity/gold support 1.0; unsupported claims
0.0. Exact lexical/gold-label method, semantic judgment explicitly unverified. No
external provider credentials or paid calls used.

The bounded health probe made 30 requests with concurrency 3: zero errors, median
0.578ms, max 1.876ms. One RSS/CPU sample is recorded; there was no memory-growth or
full application throughput/queue-drain acceptance run. Those remain NOT VERIFIED.

Runtime harness failures and retries are retained privately: noncanonical macOS temp
path correctly rejected by storage guard, stdlib `inspect` filename shadowing, and an
incorrect assumption that Uvicorn always exits zero after SIGTERM. These were harness
corrections, not weakened application guards.

### Monitoring and recovery smoke

```sh
EVIDENCEAI_EVIDENCE_TAG=full-audit-20261020 python3 infra/scripts/smoke.py
```

**Exit 0**, uniquely named disposable Compose project
`evidenceai-staging-smoke03e04a7fea`. Existing m121 application images plus selected
Grafana 13.2.4 were used; no production Compose deployment started. This is current
execution of image/infrastructure checks, not certification of an unbuilt current
application image. No development volumes mounted or reset.

Grafana digest:
`sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f`.
Authentication, no anonymous access, signup disabled, dashboard provisioning,
Prometheus datasource, two healthy scrape targets, 13 signed bundled plugins,
internal network and proxy denial of monitoring paths passed. TLS mail and synthetic
fake/mock research also passed in that image fixture. Encrypted restore succeeded;
nonempty restore target and tampered ciphertext were refused. All fixture containers
were removed. No offsite hosted recovery, image vulnerability rescan or candidate
promotion was performed.

### Security/release and repository integrity

```sh
apps/api/.venv/bin/python -m unittest discover -s infra/security/tests -v
apps/api/.venv/bin/python infra/scripts/verify_release.py docs/evidence/m126/release-result.json
git fsck --full
git diff --check
```

- Security regressions: **11 passed**, 9.127s. Genuine synthetic credential detection,
  archive handling, exact adjudication constraints, safe summaries and rollout guards
  remain enforced. This is not a new full-history Gitleaks or container scan.
- Release gate: **exit 1 / BLOCKED**, unmet `container_security`, `ai_security`,
  `ci_cd`, `production_environment`. This freshly validates the existing acceptance
  input; it does not create new hosted evidence or waive criteria.
- Git integrity: **exit 0**. No garbage collection, history rewrite, commit or push.
- Static diff checks: **PASS**, including new deliverable files. These are not
  additional application tests after the preservation stop.

Final inventories found no disposable-test containers, no smoke-project containers,
no audit listeners at 18000/18001/3100 and no remaining audit browser executables.
The user's existing services were not stopped. All prior tracked evidence byte hashes
are compared in `final-integrity.json`; any unverified historical writer remains so.

## Files changed by this audit

Pre-existing Milestone 12.8/local-mail changes are preserved, not counted as new audit edits.
They became part of the concurrent `a12b93d` checkpoint; this audit did not create it.

- `.gitignore`: ignore separate E2E output.
- `apps/web/next.config.ts`: independent conditional E2E dist directory.
- `apps/web/eslint.config.mjs`: exclude generated E2E output.
- `apps/web/tsconfig.json`: Next-generated E2E type includes/formatting.
- `apps/web/playwright.config.ts`: select separate build/start output and disable auth artifacts.
- `apps/web/e2e/server.py`: opt-in real TLS mail and private fixture checks.
- `apps/web/e2e/tls_mail.py`: real TLS SMTP receipt adapter; private test-only proofs.
- `apps/web/e2e/research.spec.ts`: no-JS credential-safety regression; remove fixed screenshots.
- `apps/web/src/components/auth/auth-form.tsx`: safe native POST fallback.
- `apps/web/src/app/verify-email/page.tsx`: safe native POST fallback.
- `apps/web/src/test/build-isolation.test.ts`: build separation regression.
- `docs/local-full-system-audit.md`, this report, `docs/local-functional-test-matrix.md`.
- `docs/evidence/local-full-audit-20261020/`: sanitized receipts/inventory/results only.

Exact new evidence files (all under `docs/evidence/local-full-audit-20261020/`):

- `backend-isolation.json`
- `browser-initial-isolation.json`
- `browser-intermediate-isolation.json`
- `browser-isolation.json`
- `checks.json`
- `delivery-checks.json`
- `environment.json`
- `evaluation-summary.json`
- `final-integrity.json`
- `monitoring-summary.json`
- `native-form-proof.json`
- `preservation.json`
- `runtime-isolation.json`
- `runtime-result.json`
- `summary.json`

Final decisions: **local PARTIAL; integrated E2E PASS (offline scope); preservation
FAIL; production BLOCKED**. No claim that development data is wholly unchanged.
