# Operational runbook

Use an operator shell in `apps/api`. No persistent monitoring stack was deployed by Milestone 10. A disposable, offline
Grafana container validated provisioning and was removed. Configure private networking, TLS, secrets, collection, retention
and alert delivery in the deployment environment before treating these as operational SLOs.

## Routine checks

```sh
.venv/bin/python -m app.operations --readiness
.venv/bin/python -m app.operations
.venv/bin/python -m app.document_worker --status
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m pip check
```

Readiness exits nonzero on failed core dependencies; diagnostics return safe categories
rather than SQL errors. Liveness is `/api/v1/health`; public readiness is `/api/v1/ready`.
Detailed readiness and metrics require a separate OPERATIONS_TOKEN bearer. Use a protected
client config/token file; do not paste tokens into shell history, URLs, frontend env or Git.
Prometheus scrape authentication reads its private credentials file. Rotate the API token
and scrape file together, then reload/restart services through your normal change process.

Start a real worker with an operator-owned metrics directory:

```sh
.venv/bin/python -m app.document_worker --metrics-file /absolute/private/runtime/worker.prom
```

Directory creation/permissions and node_exporter configuration are deliberate operator
setup. Monitor heartbeat freshness, exporter scrape health, backlog age, expired leases,
failed states, provider failure rates and cleanup intents. Do not infer worker liveness
from an empty queue. Multiple workers need distinct textfiles. Failed metric writes are
logged and do not interrupt processing. The heartbeat marks a completed tick, including
handled tick failures; inspect failure counters as well as freshness.

## Failure recovery

- **Database unavailable/pool exhausted:** check core readiness and database_up. Default
  connection/pool budgets are 5s; DB statements default to 15s and locks to 5s. Operator
  diagnostics shorten statements to 2s/locks to 500ms. Fix connectivity/capacity, then
  retry reads. Generic database failures return sanitized 503 plus support ID. Do not
  retry ambiguous mutations blindly; reload state and reuse message idempotency keys.
- **API timeout/disconnect:** embedding/generation budgets and parser subprocess limits
  remain enforced. Async cancellation propagates with a cancelled/499 telemetry event.
  Synchronous thread/DB work is not forcibly interrupted on client disconnect. Configure
  reverse-proxy header/body/read limits and graceful shutdown budgets; an HTTP timeout
  is not proof that a mutation rolled back. Reconcile state before resubmitting uploads.
- **Worker crash/expired lease:** restart the existing worker after fixing the cause.
  Eligible expired leases are reclaimed; stale lease/generation owners cannot publish.
  PostgreSQL time drives leases. No direct SQL state reset is required. Retry exhaustion
  is surfaced as failed; authorized document/index retry endpoints preserve identities
  and existing completed vectors. Inspect configuration and storage before retrying.
- **Provider rate limit/outage:** monitor adapter failures and answer outcomes. Existing
  bounded Retry-After/backoff/deadlines and job attempt limits remain in place. Avoid
  unbounded retries. Disabled providers do not invalidate core readiness. Fake/mock
  providers are offline fixtures, not a transparent substitute for hosted semantics.
- **Storage errors/full disk:** check canonical storage root and OS permissions/capacity.
  The readiness permissions probe cannot prove capacity. Cleanup intents remain durable;
  the worker retries with bounded exponential delay. Never unlink live storage objects
  or reveal storage paths through a user-facing response.
- **Graceful shutdown:** SIGTERM/SIGINT stop new worker ticks and allow the current bounded
  operation to finish. Set the service-manager grace period above the worst configured
  extraction plus indexing work in a tick; a large document can span many batches. A
  forced kill relies on durable leases for recovery. API shutdown should drain in-flight
  work with an appropriate server budget; no custom unsafe transaction cancellation was
  added. Conversation pending leases expire/recover under existing rules.
- **Citation validation failure:** track citation_rejections_total and typed RAG outcomes.
  Reject the entire invalid answer; do not relax validators or use historical snapshots
  as fresh evidence. Reproduce with the offline evaluator before changing retrieval.

## Monitoring checks

The dashboard and scrape configuration live in `infra/monitoring`. Configure operator-only
Grafana access and a maintained Prometheus installation. Mount the documented provisioning
paths, change targets/datasource for your topology and validate before reload:

```sh
promtool check config /etc/prometheus/prometheus.yml
promtool check rules /etc/prometheus/alerts.yml
promtool check metrics < captured-private-metrics.prom
```

Six alerts cover scrape failure, DB failure, expired leases, old queues, stale/missing
worker heartbeat and HTTP server error ratio. They are rules, not configured notification
delivery; wire your existing Alertmanager/on-call policy. Read p95/p99 with sample counts.
No ordinary user can access these endpoints with their application session.

## Privacy, retention and deletion

Application logs are content-free stderr streams; there is no app-managed permanent log
store or log expiry. Set collector retention (suggested seven days), restrict operator
access, encrypt archives and review any additional instrumentation for content leakage.
Even UUID correlation and queue counts are operational data. Do not enable raw SQL,
request-body, provider-debug, access-URL or traceback logging in production. Optional OTel
exporters must receive only these safe hooks; blanket HTTP/SQL instrumentation may add
private attributes and requires separate review.

Synthetic evaluation history has no customer content and no automatic deletion. Suggested
CI retention is 30 days; release baselines can be kept intentionally. Prometheus retention
must be explicitly bounded (suggested 14 days plus size cap). These are deployment policy
recommendations, not retention jobs implemented by the API.

Conversation questions, answers and citation snapshots remain private to their owner with
current workspace authorization. Source document deletion queues physical cleanup and
removes live chunks/vectors; historical citation excerpts/source metadata remain until the
conversation is deleted. Archive retains everything. There is no automatic citation TTL,
source-wide historical purge or backup erasure feature. Conversation DELETE cascades its
messages/citations; retained backups and operator logs need their own deletion policy.
This milestone introduces no new permanent storage of private evidence.

## Verification and limits

See `milestone-10-verification.md` for observed commands/results and the known build
constraint. Migration remains `6f22cc4c46ad`; no migration was generated or applied.
All tests use disposable schemas/rollback transactions and offline transports. An active
user uploaded a development document during verification; it was preserved, and the
suite was strengthened to keep global worker queries out of development tables.

Next priorities: representative and consented evaluation with human semantic judgments,
load/capacity and failure-injection testing, backup/restore drills, deployment-specific
monitoring/alert delivery and secret rotation, lifecycle retention/source-wide erasure,
and a review of dependency advisories. No availability/security certification is claimed.

## Milestone 11 deployment operations

Deployment candidates now have separate staging/production Compose files, non-root images,
HTTPS same-origin routing, file secrets and controlled migration/rollout/rollback commands.
Keep the existing development Compose project/volume on port 5433 untouched. Use
`infra/scripts/deploy.py` with an explicit private env file; see
[deployment guide](deployment-guide.md) and [production architecture](production-architecture.md).

Container diagnostics must enter through `python -m app.container_entrypoint check` or
`status`, because a fresh docker exec does not inherit secrets injected into PID 1.
Backups stop writers, include DB plus originals, encrypt with age, and verify only against
an empty disposable restore DB. The private decryption identity is not required for normal
startup. See [backup and recovery](backup-and-recovery.md) for retention/offsite transfer,
manual new-project recovery and proposed RPO/RTO. Monitoring is an internal optional profile;
configure actual alert delivery. No production acceptance is claimed before Milestone 12.
