# Hosted staging execution plan — 12.6

**Prepared; hosted acceptance NOT VERIFIED. Production FAIL / BLOCKED.**
2026-10-20, Asia/Dubai; inspected HEAD `cc22799`. No hosting, DNS, public service,
provider mail, purchase or deployment was performed. This plan grants none of
those permissions. Use synthetic accounts/documents and approved recipients only.
Never request or copy secrets into chat, Git, command arguments or evidence.

## Stop conditions and required owners

| Prerequisite / owner | Required acceptance before execution | Current result |
| --- | --- | --- |
| Security / release authority | Zero HIGH/CRITICAL/secrets for every selected immutable image; compatible maintained dependencies; no suppressions; signed/reviewed artifact provenance | FAIL: Grafana61 HIGH; candidate2 HIGH; development npm5 HIGH |
| Infrastructure | Authorized isolated staging host/account, architecture, capacity, OS patching, time sync, Docker Engine/Compose supporting `!override`, SSH fingerprint/access, firewall80/443 only and restricted SSH, egress policy | NOT VERIFIED |
| Domain owner | Approved hostname, A/AAAA ownership and addresses, ACME contact/CAA, controlled DNS change and propagation, sender SPF/DKIM/DMARC | NOT VERIFIED |
| Repository administrator | Final committed SHA, passing actual CI URLs, protected environment reviewer/no self-approval, least privilege, concurrency, approved digest manifest | NOT VERIFIED; no commit or dispatch authorized here |
| DBA / storage owner | Fresh project-owned database/document volumes, pgvector-compatible image, application least privilege, capacity and permissions; no development mounts/credentials | NOT VERIFIED on host |
| Mail owner | Compatible implicit-TLS465 provider, approved sender and test mailboxes, quota/budget, restricted credential file, actual inbox receipt | NOT VERIFIED |
| Backup / key custodians | Encrypted independent account/host destination, retention policy, separate age key escrow and approved isolated recovery target, agreed RTO/RPO | NOT VERIFIED |
| SRE / QA | Monitoring access through approved private network, operator alerts, approved predecessor/schema compatibility, external-provider/soak acceptance scope | NOT VERIFIED |

Do not substitute local passes for these receipts. Current `release-result.json`
returns BLOCKED. No start/monitoring/migration command below may run while it does.
A candidate also needs intended-platform builds, whole-image scans, dashboard/
plugin/auth/query acceptance and rollback review before promotion. The supplied
hosted overlay deliberately retains the failing selected Grafana pin; it is not a
security remediation or an approved deployment configuration.

## Prepared configuration and read-only preflight

`deploy.py --environment staging` deliberately selects the **local** staging
private-CA/loopback overlay. It cannot demonstrate public ACME/TLS. The new
`infra/compose.hosted-staging.yml` sets APP_ENV=staging while retaining the base
public80/443, public ACME import, trusted proxy address, internal networks and
separate project volumes. Seven configuration assertions pass locally; issuance,
reachability and host behavior remain NOT VERIFIED. Do not combine it with
`compose.staging.yml`. No `deploy.py` default or production gate was changed.

The authorized operator creates `/absolute/private/staging.env` outside Git,
parent0700, with a unique `DEPLOY_PROJECT=evidenceai-staging-<owned-suffix>` and
approved `SITE_HOST`, exact port443 `PUBLIC_ORIGIN=https://<host>`, `ACME_EMAIL`,
`AGE_RECIPIENT`, digest-only API/WEB/BACKUP/PROXY/DATABASE/PROMETHEUS/EXPORTER
images and `SECRETS_DIR`. No `REPLACE` or local mutable tags. The selected Grafana
Compose pin must first be remediated through normal review and strict gates.

Use operator-owned secret files `postgres_password`, `db_password`,
`operations_token`, `grafana_password`, `provider_key`, `smtp_password`; add
`age_identity` only on the authorized recovery host. Directory0700, no symlinks;
file ownership/mode must allow the specific nonroot container UID to read mounted
secrets while preventing other host users from traversing the directory. Do not
render `docker compose config` with secret-bearing settings into public logs.
`provider_key` can be empty for disabled/mock providers; no paid calls are implied.
Set SMTP_HOST/PORT465/USERNAME/SENDER, REGISTRATION_EMAIL_ENABLED=true only after
mail authorization; trusted frontend and registration origins derive from the
exact PUBLIC_ORIGIN. Schedule backups using reviewed timer/service templates in
`infra/deploy`, with alerting and offsite replication; a local volume is not offsite.

Run from the checkout on the approved host, after a separately reviewed final
commit and passing hosted CI. Substitute operator paths, no secrets:

```sh
set -eu
export STAGING_ENV=/absolute/private/staging.env
export ACCEPTED_REPORT=/absolute/private/reviewed-release-result.json
export HOSTED_SITE_HOST=approved.staging.hostname
export PUBLIC_ORIGIN="https://$HOSTED_SITE_HOST"
# Must exit0; today's m126 report exits1 and stops here.
python3 infra/scripts/verify_release.py "$ACCEPTED_REPORT"
git diff --exit-code
test -z "$(git status --porcelain)"
# Compare git rev-parse HEAD with the approved manifest/actual CI SHA.
git rev-parse HEAD
# Validate existing staging configuration/secret-file constraints without startup.
python3 - "$STAGING_ENV" <<'PY'
import importlib.util, pathlib, re, sys
spec=importlib.util.spec_from_file_location('deploy','infra/scripts/deploy.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
v=m.configuration(pathlib.Path(sys.argv[1]),'staging')
assert all(re.fullmatch(r'.+@sha256:[a-f0-9]{64}',v[k]) for k in
 ('API_IMAGE','WEB_IMAGE','BACKUP_IMAGE','PROXY_IMAGE','DATABASE_IMAGE','PROMETHEUS_IMAGE','EXPORTER_IMAGE'))
from urllib.parse import urlsplit
assert urlsplit(v['PUBLIC_ORIGIN']).port in (None,443)
assert v['SITE_HOST'] not in {'localhost'} and not v['SITE_HOST'].endswith(('.invalid','.localhost'))
print('Private configuration constraints PASS; values withheld')
PY
# env file must contain only reviewed nonsecret settings plus secret-file paths.
# Isolate from stale ambient Compose interpolation variables.
C() {
  env -i PATH="$PATH" HOME="$HOME" docker compose \
    --env-file "$STAGING_ENV" \
    -f infra/compose.production.yml -f infra/compose.hosted-staging.yml "$@"
}
C --profile monitoring --profile operations config --quiet
dig "$HOSTED_SITE_HOST" A
dig "$HOSTED_SITE_HOST" AAAA
```

Operator compares addresses with approved infrastructure, inspects host security,
container architecture, image provenance and available disk/memory, and confirms
no existing unrelated project volumes/containers share that project name. Do not
run `up` on an existing populated project as a fresh-install shortcut. Neither
local image IDs nor these syntax checks replace registry digests/signatures.

## Authorized fresh-host bootstrap — currently blocked

These are executable operator steps **only after** security/CI/owner approvals.
The direct Compose form is required for the explicit hosted overlay; existing
`deploy.py staging` would silently choose local TLS. It retains service health,
nonroot, readonly, tmpfs and network protections. Hold the deployment lock in one
maintenance session; do not run this alongside `deploy.py` or another operator.
Existing populated-host rollout/rollback requires a separately reviewed procedure
using this same overlay and an accepted predecessor; no automatic downgrade.

```sh
# On the authorized Linux host; same lock path as deploy.py. Keep this shell open.
mkdir -p infra/runtime
exec 9>infra/runtime/staging.lock
flock -n 9
# First pull all digest-pinned services after approved registry promotion.
C --profile monitoring --profile operations pull
# Fresh, separately owned staging project only; API/workers must not be running.
C up -d --wait db
C --profile operations run --rm migrate
C up -d --wait api worker web proxy
C exec -T api python -m app.container_entrypoint check
C exec -T worker python -m app.container_entrypoint status
C --profile monitoring up -d --wait prometheus worker-exporter grafana
C ps
```

Retain redacted readiness/revision/pgvector/role receipts: Alembic must be
`91e2b6d8c410` unless the reviewed artifact explicitly changes it; query
`current_database()`, `pg_extension.extversion` for vector, and pg_roles flags
inside this staging API. Verify schema version and vector search on synthetic
rows. Application role must not be superuser/CREATEDB/CREATEROLE. No published
DB/worker/exporter/Grafana/Prometheus port; only proxy80/443. Prohibit host private
storage/development volume mounts. Track worker queue age, retries and failures.

## Acceptance commands and required receipts

After authorized DNS/TLS issuance, use verified trust (no `-k`):

```sh
openssl s_client -connect "$HOSTED_SITE_HOST:443" -servername "$HOSTED_SITE_HOST" \
  -verify_return_error -verify_hostname "$HOSTED_SITE_HOST" </dev/null
curl --fail --silent --show-error "$PUBLIC_ORIGIN/api/v1/ready"
curl --silent --show-error --head "http://$HOSTED_SITE_HOST/login"
curl --silent --show-error --head "$PUBLIC_ORIGIN/login"
for route in /metrics /api/v1/ops/metrics /grafana/api/health /docs /openapi.json; do
  curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' "$PUBLIC_ORIGIN$route"
done
```

Require redirect308 to exact HTTPS origin, valid public chain/SAN, HSTS and
nosniff, no-store on private API responses and404 on private routes. Test public
renewal rehearsal/expiry alerting with the host operator; local private CA does
not count. Verify no internal endpoint is exposed via direct IP/alternate host.

| Area | Execute on synthetic staging data / expected result | Evidence owner |
| --- | --- | --- |
| Browser/auth | Three engines; controlled register→verify→login, Secure/HttpOnly cookie, CSRF/foreign-origin refusal, replay/expiry/browser binding, tenant isolation and keyboard/accessibility | QA; redacted result counts, no tokens/HAR/cookies |
| Reverse proxy | Forged forwarded headers from untrusted peer refused; exact origin/routing and real frontend→API connectivity; concurrent upload limits | SRE; status/headers aggregates |
| Storage/workers | Upload controlled known hash, wait extraction and embeddings, search/ask with authorized provider or separately scoped mock, byte-exact download, cross-tenant404, pending-job restart/drain | QA/SRE; hashes/counts, no document text |
| SMTP | Follow [controlled mail procedure](hosted-staging-acceptance.md#safe-real-provider-smtp-acceptance-procedure): verified465, real provider receipt AND inbox arrival; SPF/DKIM/DMARC, latency, duplicate/replay/rate limits, revoke test credential | Mail/identity owner |
| Monitoring | Run `monitoring_check.py` inside API via approved private access, password via secret-file→stdin only; dashboard/provisioning/admin/anonymous401/signup disabled,13 plugin identities, datasource health and actual2-target `up`; inspect internal network/no ports; fire approved synthetic alert and retain operator delivery | SRE |
| Restart/rollback | Preserve dashboard/state and plugin/query results across restart; accepted predecessor/current transition only after schema compatibility check; DB/originals unchanged, no Alembic downgrade; return to approved artifact | Release/SRE |
| Soak/capacity | Apply reviewed `infra/load/thresholds.json` on intended architecture/host, measured queue drain/CPU/memory and bounded provider budget; independently review mock versus hosted semantic scope | SRE/AI owner |

Local Playwright starts its own isolated HTTP fixtures, so its18 cases do not
exercise this hosted origin. Do not point its DB URL at staging/production to
claim hosted coverage. Hosted QA must execute these flows through the actual
HTTPS origin with an explicitly scoped harness/approved controlled browser;
that hosted-origin automation is still a required operator deliverable.

## Encrypted offsite backup and isolated recovery

In the same exclusive maintenance window, stop proxy/API/worker writers, use
`C --profile operations run --rm --no-deps -e QUIESCED=1 backup`, then restart
only those writers previously running. Keep failed-backup state for investigation;
never remove volumes. `list-backups` and an operator-selected basename identify
the archive. Export ciphertext through `backup export` to a **new** restricted
file (noclobber, umask077); record SHA256, not plaintext. Transfer using an
approved authenticated channel to a genuinely independent host/storage account.
Keys must be independently escrowed; never copy the private identity into evidence.

On an approved clean recovery host, provision a fresh separate project, matching
immutable backup/database images and an empty backup volume populated only with
the selected ciphertext. Mount restricted `age_identity`, then use the recovery
services from base Compose, e.g. `C --profile recovery up -d --wait restore-db`
and `C --profile recovery run --rm --no-deps -e BACKUP_FILE="$BACKUP_BASENAME"
restore-verify`. The restore target must be `restore-db/restorecheck`, never the
live database. Reject nonempty target and tampered-copy restores only in separate
owned recovery fixtures. Verify revision/pgvector, file bytes/permissions,
authenticated app operation and pending work on an isolated restored app stack.
Current restore-verify checks alone do not execute a restored hosted application.
Record independent-host/key-access receipts and measured RTO/RPO from last
acknowledged synthetic write; compare approved objectives. Retain original
volumes/ciphertext. Local timings are not offsite certification.

## Evidence and decision handoff

For every row record owner/reviewer, source SHA, architecture, registry digests,
UTC start/end, exact command, exit, scoped PASS/FAIL/NOT VERIFIED and redacted
receipt SHA256. Store private material separately; archive raw logs without
rewriting historical hashes. Missing receipt is NOT VERIFIED; observed failure
is FAIL. Production stays **FAIL / BLOCKED** until every applicable criterion is
PASS and the release authority explicitly approves. No exception is prepared.
