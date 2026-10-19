# Production security controls and acceptance limits

This is infrastructure preparation, not independent penetration testing or a production
readiness certification. Milestone 12 must accept the concrete release and deployment.

## Implemented boundaries

Only the reverse proxy publishes production ports. Application, database, monitoring and
recovery networks are internal; API/worker egress is explicit. The proxy replaces incoming
forwarded headers and the API trusts one fixed private proxy peer, not arbitrary clients
or an entire address range. The same HTTPS origin serves frontend and `/api/*`, preserving
Secure/HttpOnly/__Host- cookies, origin checking, CSRF headers and support IDs. HTTP redirects
point to the configured HTTPS origin. Operator/API docs/metrics routes are denied publicly;
operator bearer authentication also protects metrics inside the network.

API, worker, web, proxy and backup runtimes use UID 10001. PostgreSQL uses UID 999;
Prometheus/Grafana use their upstream non-root users. Roots are read-only, writable paths
are explicit, capabilities are dropped and no-new-privileges/PID/resource limits apply.
The proxy image removes its unused privileged-port file capability so it can execute under
these restrictions. No app container gets the Docker socket, host PID namespace, privileged
mode or a public storage mount. A compromised API/worker still has legitimate application
DB/storage authority; this is not tenant isolation by container.

The DB app role has no superuser/role/database-creation authority and a connection cap.
It currently owns schema/migration objects. Splitting migration/runtime privileges is a
future hardening step. PostgreSQL statement/error-statement logging is restricted to avoid
query payloads, with terse server errors. Application logging remains allowlisted JSON;
proxy error logs remove request structures. Container logs rotate at 10MiB × three files;
configure host/collector retention and access as separate policy. Do not enable raw SQL,
request-body, provider debug or private traceback logging.

## Secrets

Each runtime receives only its required file-backed Compose secrets. These are **not an
encrypted secret-management service**: the host directory, host backups and Docker daemon
are trusted and must be protected/encrypted. Compose file-secret UID/GID remapping is not
assumed. Files are readable inside specifically granted containers while their host parent
is mode 0700. Confirm Linux ownership and access before acceptance. Secret contents are
loaded inside the process, never baked into images or browser configuration.

Normal deployments do not require the age private identity. Keep it offline and mount it
only for a deliberate isolated recovery check. The backup job receives only the public
recipient and app DB secret. Grafana's admin password is distinct from the application
operator bearer and DB admin/app credentials. Provider keys remain backend-only, disabled
unless model settings and privacy opt-in validate. Do not reuse production secrets in CI.

Rotation procedures:

- **Operator bearer:** create a new file atomically, recreate API/worker and Prometheus
  secret mounts together, verify unauthorized requests fail and internal scrapes recover.
- **Provider key:** revoke compromised upstream credentials, write a replacement private
  file and recreate API/worker. Test provider configuration without paid automated calls.
- **DB credential:** stop writers, protect a recovery point, change the restricted role
  password through a trusted administrator with file-based input, replace its secret,
  recreate connection pools and verify readiness. Do not paste the password into SQL
  history or a docker command argument. Preserve the separately managed admin credential.
- **Grafana:** rotate through authenticated administrative controls and update bootstrap
  material. Changing the bootstrap secret alone does not reset an existing Grafana DB's
  administrator password.
- **Age recipient/identity:** generate and escrow new material, change the public recipient
  for future archives, retain old identities until their archives expire, and verify
  decryption/offsite recovery before retiring anything.
- **TLS/SSH:** preserve Caddy state for certificate management; replace compromised keys,
  verify renewed trust material out of band and update pinned host keys deliberately.

## Remaining release and host risks

Local image scans found high/critical advisories, including base OS/runtime dependencies.
Available OS updates and a maintained Node 26 patch were applied, but scan findings are
not automatically waived. See the final verification/security summary for counts. CI
blocks high/critical candidates pending remediation or explicit qualified acceptance;
zero embedded-secret findings do not establish absence of all secrets or vulnerabilities.

Required host work includes patching Docker/kernel, firewall and SSH restrictions, verified
DNS/TLS renewal, private registry access, encrypted host disks, offsite backup retention,
alert delivery, NTP/clock synchronization, operator access review and representative load/
recovery testing. App volume encryption and external secret management are not implemented
by Compose. The application already retains historical citation snapshots after source
deletion until conversation deletion; encrypted backups retain those contents for their
retention window. Source-wide erasure, WAL/PITR, high availability and managed S3 remain
outside this milestone.

The app uses bounded provider/parser/DB budgets. Proxy timeouts do not forcibly cancel
committed synchronous work. Worker stop grace can expire for large indexing jobs; durable
lease fencing is the recovery mechanism. Treat ambiguous HTTP failures with existing
idempotency/state reconciliation, not blind mutation retries. No new production acceptance
claim is inferred from a successful single-document local smoke test.

See official [Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/),
[PostgreSQL backup](https://www.postgresql.org/docs/17/backup-dump.html), and
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) documentation
for platform contracts; target-host acceptance must validate the actual topology.
