# Deployment guide

These commands are preparation instructions. Public production rollout requires Milestone
12 acceptance. Use a dedicated Linux host/account, Python 3.11+, supported Docker Engine and Compose
**2.24.4 or newer** (`!override`/`!reset` support). Local verification used Docker 29.8.2 /
Compose 5.6.0 on ARM64. GitHub runners are configured for Linux AMD64; that hosted workflow
has not been executed during this milestone. An initial 8GiB host is a proposed starting
point, not verified sizing.

## Prepare a release

From a clean committed checkout, build/test the four candidate images:

```sh
docker build -t evidenceai-api:m11 apps/api
docker build -t evidenceai-web:m11 apps/web
docker build -t evidenceai-backup:m11 infra/backup
docker build -t evidenceai-proxy:m11 infra/deploy
python3 infra/scripts/smoke.py
```

The smoke script is local-only: fixed loopback ports, unique project, synthetic account/
document, private CA, bind mounts and tmpfs. It never uses development PGDATA or deletes
Docker volumes. It stops/removes only its own containers/networks and temporary fixtures.
Its report is `/tmp/evidenceai-m11-smoke-result.json`. Do not run overlapping smoke drills
on the same fixed ports/subnet.

CI builds full-SHA candidate tags, scans them and saves images/source/provenance as review
artifacts. After acceptance, an operator publishes the exact candidates to a registry,
records each registry manifest digest, and installs a matching clean checkout under
`/opt/evidenceai/releases/FULL_SHA`. No image is automatically pushed by the CI definition.
Local image IDs are not interchangeable with registry manifest digests. Preserve previous
release digests and the prior environment file before changing anything.

## Secrets and environment

Create an operator-owned mode-0700 parent for the offline recovery identity. Generate new
secrets without printing their values or overwriting any existing file:

```sh
python3 infra/scripts/generate_secrets.py \
  --directory /absolute/private/new-evidenceai-secrets \
  --identity-output /absolute/private/offline-recovery/identity.txt
```

The tool prints only the age **public recipient**. Preserve the private identity offline,
with a separately protected second copy. Normal deployments/backups do not need it on
the application host. For an explicitly authorized restore drill, temporarily supply
`SECRETS_DIR/age_identity`; remove that host copy afterward through your key-handling policy.

Copy `infra/.env.example` into a protected operator file outside Git. Set:

| Setting | Required meaning |
| --- | --- |
| DEPLOY_PROJECT | Unique `evidenceai-staging[-suffix]` / `evidenceai-production[-suffix]`; never the development project |
| SITE_HOST | DNS hostname, no scheme or port |
| PUBLIC_ORIGIN | Exact HTTPS origin; production port 443, staging defaults 18443 |
| ACME_EMAIL | Actual certificate contact in production |
| API_IMAGE / WEB_IMAGE / BACKUP_IMAGE / PROXY_IMAGE | Exact accepted registry `@sha256:` references in production; staging accepts local tags |
| SECRETS_DIR | Absolute private directory, mode 0700; no secret values in env file |
| AGE_RECIPIENT | Age public encryption recipient |
| BACKUP_RETENTION_DAYS | 1–3650; default 14 |
| EMBEDDING_* / LLM_* | Providers disabled by default; explicit privacy opt-in/model configuration for hosting |

The secret directory contains independent `db_password`, `postgres_password`,
`operations_token`, `grafana_password`, and an empty `provider_key` unless hosting is
explicitly enabled. File-backed Compose secrets do not reliably remap UID/GID. The generator
uses readable files inside a host-private 0700 parent, and Compose mounts only specifically
granted files into each container. Confirm permissions on the target Linux host. Do not
place the recovery private key, database password or provider key in image build arguments,
NEXT_PUBLIC variables, shell history, Git or diagnostic output.

The container entrypoint injects secret files internally, validates staging/production
HTTPS settings, dedicated DB identity, one private trusted proxy IP, operator token and
private storage. Invalid setup fails before the API starts. `AUTH_ALLOW_INSECURE_HTTP=true`
is rejected. Supported container helper modes read secrets too; a raw `docker exec python
-m app.operations` does not inherit secrets injected into PID 1. Use the entrypoint wrapper.

## Staging / production commands

Always use the wrapper with an explicit env file. For example:

```sh
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env validate
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env start
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env ready
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env monitoring
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env diagnostics
```

`start` initializes only the selected deployment DB, runs one explicit migration operation,
then starts API/worker/web/proxy and checks readiness. Do not use initial `start` to upgrade
an active release. `migrate` refuses while API/worker are running. API replicas never run
migrations automatically. `stop` stops app services without deleting persistence.

For production, add `--environment production --ack-production` to modifying commands.
Validation requires immutable image digests, proper HTTPS origin and a real ACME contact.
This extra flag is an operator acknowledgement, not Milestone 12 acceptance or a substitute
for GitHub environment review. Never run these production commands during a local drill.

For an accepted upgrade, prepare next/previous env files with the **same project, origin
and secrets directory**, then run:

```sh
python3 infra/scripts/deploy.py --environment production --ack-production \
  --env-file /etc/evidenceai/production.env \
  --previous-env /etc/evidenceai/production.previous.env rollout
```

The operation locks the environment, pulls candidate images, stops writers, makes an
encrypted backup, keeps writers stopped during one migration, and starts/checks the new
release. Single-host rollout includes a maintenance window. If migration/startup fails,
inspect the safe failure state; do not blindly repeat ambiguous writes. No automatic
schema downgrade, data reset or volume removal occurs.

Application rollback uses a previous accepted env file and the `rollback` action. It first
checks the previous API image against the current schema, then replaces app containers.
If the schema check fails, use an accepted forward fix or the separate recovery procedure;
restoring app binaries does not reverse a data migration. The wrapper will not do that
implicitly.

## DNS, TLS and access

Before a future public launch, an operator must create A/AAAA records pointing SITE_HOST
to the host. Publish AAAA only if IPv6 routing/firewall and inbound 80/443 actually work.
Allow inbound 80/443 to Caddy; restrict SSH to operator networks. Do not publish DB, API,
worker, exporter, Grafana or Prometheus ports. Behind another proxy/CDN, review real-client
IP handling before changing trust; never trust arbitrary forwarded headers.

Production Caddy manages ACME issuance/renewal and HTTP→HTTPS redirects. Persistent proxy
state stores certificates/account keys. Staging imports `tls internal`; trust only that
staging CA in the test client. The milestone verified private-CA TLS locally, **not public
ACME issuance, DNS reachability or live renewal**. Staging redirects use its explicit
18443 public origin; production uses 443. Upload cap is 20MiB plus 64KiB multipart envelope.
Header/body/response time budgets and streaming proxying are configured. Private API
responses are no-store; authentication cookies and CSRF/origin enforcement remain intact.

Prometheus/Grafana run under the optional `monitoring` profile with provisioned dashboard
and alert rules. Access through an authenticated operator tunnel or an internal management
client/container, never an added public proxy route. Public `/api/v1/ops/*` is denied even
with a bearer. Wire an actual Alertmanager/on-call route before acceptance; rules alone
send no notifications.
