# Observability

Milestone 10 adds content-free backend telemetry without a schema migration. Ordinary
workspace roles do not grant operator access. Nothing is exported to a third-party
service by default.

## Correlation and logging

The browser generates a UUIDv4 for each API request, including downloads. The outer
ASGI middleware accepts exactly one lowercase canonical UUIDv4 `X-Request-ID`, replacing
missing, malformed, duplicate or oversized values. This is a support identifier, not
an identity, authorization decision, trusted distributed trace or idempotency key.
Responses expose the identifier through CORS; generic server errors include it in JSON.
Client error boxes display only validated support IDs. CORS also exposes Retry-After.

ContextVars carry the same ID through FastAPI's synchronous thread pool, SQLAlchemy
query events, retrieval and generation. Stateless ask bodies share the HTTP ID; saved
conversation replay retains its original generation ID while the new HTTP response
identifies the replay request. Upload enqueue events and worker claim/completion events
join on the document job UUID and workspace UUID. Embedding enqueue/claim events use
the same document UUID. Worker events have no originating HTTP context: join the enqueue
log to the worker log by job UUID. Correlation across restarts depends on retaining both
logs; no new customer-data column or durable trace payload is stored.

`app/core/telemetry.py` configures JSON stderr logs in the API and worker. Fields include
UTC timestamp, severity, operation, request ID, route template, HTTP status, elapsed ms,
error category, provider, outcome, and workspace/job UUIDs when available. The formatter
uses an allowlist and discards message strings, arguments, exception text, tracebacks,
SQL, parameters and arbitrary extras. Raw access-log messages are discarded. No query
strings, questions, filenames, storage keys, document bodies, tokens, passwords or
provider payloads are emitted. SQL timings contain no statement text. Existing parser
isolation remains unchanged. Configure the process manager to preserve this formatter;
adding third-party log handlers can bypass these protections.

Errors classify access, request, rate limit, database, timeout, cancelled, provider,
storage, parser, citation, unavailable and internal failures. Expected service-level
failures can return typed outcomes rather than exceptions; consult answer/job metrics
as well as transport error counts. A successful worker function return does not imply
a successful document: durable job states and `jobs_total` carry that distinction.

The existing OpenTelemetry API supplies local HTTP, service-operation and database span
hooks. Without an application-installed SDK they are no-ops. Operators may bootstrap an
SDK/exporter before loading `app.main`; neither SDK/exporter nor collector is installed
or started here. Span names are fixed, with no prompt, SQL, exception or payload
attributes. Automatic exception recording is disabled. Remote traceparent and baggage
are deliberately not extracted. Worker lineage uses log joins, not cross-process spans.

## Health and protected diagnostics

| Endpoint | Access | Meaning |
| --- | --- | --- |
| `/api/v1/health` | Public | Original configuration-independent liveness contract |
| `/api/v1/ready` | Public | Only ready/not_ready; PostgreSQL, vector extension, schema head and storage permissions |
| `/api/v1/ops/readiness` | Operator bearer | Named checks, configured provider types, queue aggregates |
| `/api/v1/ops/metrics` | Operator bearer | Prometheus text 0.0.4 |

Set a random backend-only `OPERATIONS_TOKEN` of at least 32 characters. Unset means
operator endpoints return 404. Missing/incorrect bearer credentials return 401 when
enabled. Session cookies, workspace owner/admin roles and frontend configuration do not
grant access. Use TLS or loopback/internal networking and restrict scrape clients at the
network boundary. Never put this token in `NEXT_PUBLIC_*`, a query string or Git.

Readiness never calls hosted providers. Settings already validate provider opt-in/model
configuration. Disabled providers remain reported as disabled and do not block core API
readiness. Storage probing checks the existing canonical directory and OS accessibility;
it does not create or read documents, prove available disk capacity or guarantee a
future write succeeds. Required revision is `6f22cc4c46ad`; update it with future reviewed
migrations. Queue diagnostics are separate from core readiness. Queue state alone does
not prove a worker is alive; the diagnostic explicitly says `unverified`.

## Metrics

All names start with `evidenceai_`. Counters/histograms are process-local and reset on
restart. Run one ASGI process per scrape target; a load-balanced URL over multiple workers
will give inconsistent counters. Scrape each replica directly. No multiprocess registry
or durable metrics database is embedded in the application.

| Metric | Labels / interpretation |
| --- | --- |
| `http_requests_total`, `http_request_seconds` | Registered route template, fixed method, numeric status; auth/upload latency comes from corresponding POST routes |
| `http_errors_total` | Fixed error category |
| `operation_seconds`, `operations_total` | Fixed operation/outcome/provider; DB query, extraction, chunking, embedding, retrieval, generation, RAG, cleanup and worker stages |
| `provider_calls_total` | Adapter attempts, including retries; fixed provider/operation/success or failure |
| `tokens_total` | Validated reported input/output usage only; absent when unavailable |
| `retrieval_results_total` | Returned result count, including zero observations in retrieval call count |
| `answers_total`, `citation_rejections_total` | Answer outcome and rejected generation counters |
| `jobs_total`, `queue_wait_seconds` | Published document/embedding job outcomes and time since availability at claim |
| `queue_jobs`, `queue_expired`, `queue_oldest_seconds` | Durable queue/state gauges from PostgreSQL; oldest queued creation age |
| `job_retries`, `cleanup_pending` | Retained retry counts and cleanup intents; not lifetime history |
| `database_up`, `database_errors_total` | Diagnostic-query success and DB errors in this process |
| `worker_last_tick_timestamp_seconds` | Optional worker textfile heartbeat; completed tick, including handled failures |

No raw user, workspace, document or request IDs are metric labels. Histogram buckets
range from 5ms to 300s plus infinity. Grafana gates HTTP p95 on 20 observations and p99 on
100; these are approximate bucket quantiles. Operation p50 panels are descriptive and
must be interpreted with sample counts. Offline reports use exact samples and omit
p95/p99 below those counts. Queue wait is observed only when a job is claimed, and
backoff scheduling affects that duration. No complete historical job duration is inferred
from updated_at. Durations measure operations executed after instrumentation was enabled.

Aggregations return constant-sized state summaries; each SQL statement has a 2s timeout
and 500ms lock timeout in a read-only transaction. Large tables can time out rather than
provide a result. Scrape interval is 30s, timeout 20s. Database failure emits database_up=0
and omits queue gauges, rather than reporting an empty queue. The scrape itself can
succeed during a DB outage, so alert on both `up` and `database_up`.

## Monitoring configuration

`infra/monitoring/prometheus.yml`, `alerts.yml`, and Grafana provisioning/dashboard files
provide an operator dashboard and six alerts. Configure your existing Prometheus/Grafana
installation; these files do not deploy anything. API target defaults to Docker Desktop's
host alias on port 8000. Change it for your topology. Mount a token file at
`/etc/prometheus/secrets/operations_token` and alerts at `/etc/prometheus/alerts.yml`.
Use a maintained, explicitly pinned image/version in your deployment.

Run the worker with `--metrics-file` in a private operator directory, then configure an
existing node_exporter textfile collector for that directory. Only one worker may own a
file; use separate files and instance labels for multiple workers. The example worker
target is port 9100. Missing or stale heartbeat is an alert, not evidence of idle health.
The worker writes atomically with mode 0640. Ensure exporter UID/group can read it.
No exporter port should be exposed to ordinary application users.

Mount `grafana/provisioning` under `/etc/grafana/provisioning` and `grafana/evidenceai.json`
under `/var/lib/grafana/dashboards`. The datasource uses `http://prometheus:9090` and UID
`evidenceai-prometheus`; adjust to your internal deployment. Require operator login,
disable anonymous access and bind administration to an internal interface. Suggested
Prometheus retention is 14 days with a disk-size cap, configured by the operator.

Configuration follows the official [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/),
[text exposition](https://prometheus.io/docs/instrumenting/exposition_formats/) and
[Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) contracts.
