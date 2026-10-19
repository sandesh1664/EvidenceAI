# Milestone 10 observed verification

Verified on 2026-10-19 against starting Git revision `5dc0cd1` (Milestone 09). No commit,
push, production deployment, volume reset, customer-record deletion, paid API call or
schema migration was performed. The complete changes remain in the working tree.

## Results

| Actual command/check | Observed result |
| --- | --- |
| API `.venv/bin/python -m pytest -q` | **617 passed**, 21.22s; one existing Starlette/httpx deprecation warning |
| `.venv/bin/python -m alembic current` | `6f22cc4c46ad (head)` |
| `.venv/bin/python -m alembic check` | No new upgrade operations detected |
| `.venv/bin/python -m pip check` | No broken requirements found |
| Web `npm run lint` | Passed |
| Web `npx tsc --noEmit` | Passed |
| Web `npm test` | **50 passed**, three files |
| Web `npm run build` | Failed: Turbopack loader subprocess socket binding returns EPERM in this environment, including escalation retry |
| Web `npm run build -- --webpack` | **Passed** production build, all private routes dynamic |
| Chromium existing flows plus request-ID assertions | **4 passed**, 3.3m, real API/workers and disposable schema; test-only Webpack build override removed afterward |
| Offline `python -m app.evaluate --repeat 3` | **68 scored units**, all configured thresholds passed |
| Same runner with `--compare docs/milestone-10-evaluation.json` (relative path adjusted from apps/api) | All metric deltas zero; thresholds passed; unique new artifact preserved |
| `python -m app.operations --readiness` | Ready: PostgreSQL, vector, schema, storage all true; both providers disabled |
| `python -m app.document_worker --status` | Safe JSON queue diagnostics, no source rows or private fields |
| Cached Prometheus `promtool check config` | Scrape config accepted; six alert rules accepted |
| Cached Prometheus `promtool check metrics` | Final actual protected-endpoint output parsed and linted with exit 0 |
| Disposable cached Grafana, network disabled/no published ports | Dashboard provisioned and read through authenticated API: **17 panels**; container removed |
| `git diff --check` | Passed |

The original 595 backend tests are retained. Twenty-two observability cases cover JSON
allowlisting/redaction, strict identifiers, context/header propagation, DB-safe 503,
error classification, cancellation, histogram/count accuracy, provider failures, protected
operator access, readiness, real queue aggregation/expired leases/retries/age, DB outage,
atomic worker textfiles, graceful SIGTERM, nonfatal metric-write failures, nDCG, threshold
failures, sample gating/history, and extended RAG guards. Existing queue lease recovery,
stale fencing, retry exhaustion, provider backoff, storage failure and transaction tests
continue to pass. The frontend adds one support-ID test and E2E correlation assertions.

## Evaluation evidence

The committed [machine-readable report](milestone-10-evaluation.json) contains eight
retrieval gold queries repeated three times for each of two fake profiles, 18 RAG cases,
and two real access/deletion guards. Per profile: recall/precision@2 0.9375, MRR 1.0,
nDCG@2 0.951643, no empty rankings, all isolation/filter checks passed. RAG: 17/18 exact
labels, five emitted claims/citations all matching their gold support, zero unsupported
emitted claims and 6/6 insufficiency cases detected. Both guards passed. Backup-region
retrieval still falsely abstains. Semantic entailment is unverified.

Local timing samples: 24 per retrieval profile, p50 3.021/3.021ms and p95 5.799/5.769ms;
18 RAG observations, p50 7.566ms. No group has enough samples for p99; RAG has no reported
top-level p95. These measurements are sequential synthetic local runs, not production
latency or concurrency results. The repeat command preserves all historical output files.

## Database and isolation

No model/migration DDL changed. Diagnostics are read-only and statement/lock bounded.
Initial development data included an existing account, workspace and session. Concurrent
use during verification added a document/job and later a conversation/messages and touched
the session. Those changes were preserved. A new session-wide disposable test schema
prevents unscoped legacy worker queries from selecting development records, even while
users are active. Existing per-test outer transactions/savepoints remain in that schema.
After the concurrent activity, hashes/counts of all fifteen development tables and the
migration revision matched the follow-up baseline exactly across isolated verification.
A later final check saw one additional authentication-rate-limit row during continued
application use; the other fourteen tables still matched their hashes and the migration
revision was unchanged. No development records were deleted or reset. No private row
values were printed. All owned evaluation/test/E2E schemas were removed (zero remaining).

## File inventory

New implementation:

- `apps/api/app/core/telemetry.py`: JSON formatter, context, ASGI correlation/errors,
  OpenTelemetry API span hooks, SQL timing events, bounded Prometheus registry/stage wrappers.
- `apps/api/app/operations.py`: protected metrics/readiness, public aggregate readiness,
  bounded queue aggregation and operator CLI.
- `apps/api/app/evaluate.py`, `apps/api/evaluation/thresholds.json`: versioned reports,
  profile comparisons, sample-gated latency and CI regression rules.
- `apps/api/tests/test_observability.py`, `apps/web/src/test/correlation.test.tsx`.
- `infra/monitoring/prometheus.yml`, `alerts.yml`, `grafana/evidenceai.json`, and Grafana
  datasource/dashboard provisioning YAML.
- `docs/observability.md`, `evaluation-framework.md`, `operational-runbook.md`, this file,
  and `milestone-10-evaluation.json`.

Modified implementation:

- API `main.py`, `core/config.py`, `core/browser_security.py`, `db/session.py`, `.env.example`.
- `document_worker.py`, `evaluate_retrieval.py`, `evaluate_rag.py`.
- Services: `document_service.py`, `document_jobs.py`, `document_parsing.py`,
  `document_chunking.py`, `embedding_jobs.py`, `embedding_providers.py`, `search_service.py`,
  `llm_providers.py`, `rag_service.py`.
- Tests: `conftest.py`, `test_auth.py`, `test_workspaces.py`, `test_embeddings.py`, `test_rag.py`.
- Web `src/lib/api/client.ts`, `src/components/ui.tsx`, `e2e/research.spec.ts`.
- `.gitignore`, `README.md` and existing API, security, document, retrieval, RAG and frontend docs.

## Practical limits and Milestone 11

Operator endpoints are disabled until a random backend token is configured. Prometheus,
Grafana access control, textfile exporter, alert delivery and retention require deployment
setup. Counters are process-local; scrape each ASGI replica directly. Worker heartbeat is
optional; database queues alone report worker liveness as unverified. OTel hooks are present,
but no SDK/exporter/collector or remote trace extraction was deployed. Worker correlation
uses enqueue/job log joins and does not persist an originating request ID in the DB.

No forced cancellation of synchronous DB/mutation work is introduced. Configure gateway
body/read timeouts and service shutdown budgets; keep existing idempotency for ambiguous
outcomes. Storage readiness checks permissions, not disk capacity. Queue aggregation scans
can time out on large installations. This is not a load test, backup/restore test, hosted
semantic evaluation or security certification. Historical citation retention/source-wide
erasure limitations remain. The existing frontend development dependency advisories were
not changed by this milestone.

Milestone 11 should prioritize a consented representative evaluation corpus with human
semantic review, measured concurrency/load and chaos testing, backup/restore drills,
deployment monitoring and alert delivery, source-wide retention/deletion policy, secret
rotation and dependency remediation, and investigation of the default Turbopack socket
constraint without weakening application security.
