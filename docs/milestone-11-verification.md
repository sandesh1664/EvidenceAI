# Milestone 11 verification and completion report

Starting checkpoint: `703ec96`, clean working tree. Verified locally on 2026-10-19.
Implementation remains uncommitted. No registry push, public deployment, DNS change,
server purchase, development database reset or persistent development-volume removal was
performed. Production acceptance is explicitly deferred to Milestone 12.

## Actual results

| Verification | Observed result |
| --- | --- |
| API `python -m pytest -q` | **637 passed**, 21.05s; one existing Starlette/httpx deprecation warning |
| Final focused deployment guardrails | **20 passed**, 0.26s |
| `python -m alembic current` | `6f22cc4c46ad (head)` |
| `python -m alembic check` | No new upgrade operations detected |
| `python -m pip check` | No broken requirements found |
| Web `npm run lint` | Passed |
| Web `npx tsc --noEmit` | Passed |
| Web `npm test` | **51 passed**, four files |
| Web `npm run build` | **Passed** using supported Webpack and standalone output |
| Existing real-backend Chromium E2E | **4 passed**, 28.2s |
| API/worker Docker build | Passed: Python 3.14.6, pinned binary wheels, dependency consistency |
| Web Docker build | Passed: maintained Node 26.12.0, standalone runtime, no runtime npm |
| Backup Docker build | Passed: PostgreSQL 17 client tools and age; no inherited DB volume |
| Proxy Docker build | Passed: upstream bind capability removed; non-root/high ports |
| Staging and production Compose config | Passed; production was validated only, never started |
| Local staging private-CA HTTPS | Passed, with CA verification enabled in the client |
| Cookies / CSRF / untrusted origin / forged proxy peer | Passed: Secure/HttpOnly/__Host- cookies, forbidden mutations rejected |
| Non-root/storage/read-only runtime | API/worker/web UID 10001; live upload/download and read-only root verified |
| Dedicated database identity | Verified non-superuser, no database/role creation privileges |
| Fake/mock embedding and RAG | Indexed retrieval and cited answer passed; response/header support IDs matched |
| Monitoring | Prometheus API and worker-exporter targets both up; Grafana healthy/private, dashboard provisioning mounted |
| Encrypted backup/isolated restore | Passed: one original, revision `6f22cc4c46ad`, pgvector **0.8.7**, original checksum matched |
| Restore negative checks | Nonempty target and tampered authenticated ciphertext both rejected |
| Graceful shutdown | Proxy/API/worker stopped through Compose and fixture cleaned successfully |
| Secret generation | Private key/file permissions and no-overwrite behavior passed; values not printed |
| Workflow `actionlint` / shell checks | Passed using pinned, network-disabled linter |
| pip-audit 2.10.1 | **0 known findings**, 44 pinned requirements |
| npm audit production | **0 findings** |
| npm audit including development | **5 high**, existing development lint chain |
| Candidate image vulnerability/secret scans | Completed; **0 secret findings**, remaining vulnerability findings below |
| Strict image release gate | **Exit 1**, correctly blocks high/critical candidate findings |
| Repository `git diff --check` | Passed |
| Existing development Compose diff | Empty: original file unchanged |

The host's current Node is 26.0.0; the container's tested maintenance runtime is 26.12.0.
Local image builds/drills ran on Linux ARM64 via Docker Desktop. The GitHub workflow targets
Linux AMD64; hosted workflow execution and deployment-environment API/SSH behavior were
not run from this workspace. Source/runtime definitions were linted and locally exercised.

## Topology and runtime

Production has five normal app services: proxy, web, API, worker and PostgreSQL. Optional
monitoring adds Prometheus, a textfile exporter and Grafana. Migrations, backup and restore
verification are explicit operations/profile services. Only proxy 80/443 are public in
production; staging binds 18080/18443 to loopback and uses an isolated private CA.
Application/database/monitoring/recovery networks are internal. API/worker receive explicit
egress; proxy alone joins ingress. API trusts only its fixed proxy peer. The same browser
origin routes `/api/*` to FastAPI and everything else to Next.js. Public ops/docs/metrics
paths are denied before forwarding.

All four candidate images run as UID 10001; the worker reuses the backend image. PostgreSQL
runs as UID 999 with a separate admin secret and a restricted app role. Read-only roots,
dropped capabilities, no-new-privileges, resource/PID limits, health/readiness checks,
log rotation and graceful stop periods are configured. Private originals are a project
volume shared only by API/worker and authorized backup jobs. No application container
mounts a Docker socket.

The storage default previously assumed a deep source checkout; it now also imports safely
at `/app`. Caddy's upstream executable capability conflicted with cap_drop ALL; a small
derived image removes that capability and listens above 1024. Explicit proxy routing order
ensures the private ops block runs before API forwarding. Webpack selection resolves the
prior default build failure without weakening browser or authentication protections.

## Secrets, rollout and CI

Secrets are generated outside the source tree, stored in an operator-private directory,
and granted as files per service. No production credential is in images/Git/frontend env.
Normal startup/backup needs no private age identity; only the isolated recovery verifier
receives it. File-backed Compose secret ownership limitations are handled/documented.
Startup validates secret files, HTTPS/staging-production settings, role, proxy IP and storage.

The operation wrapper validates configuration, serializes maintenance operations, starts
staging, runs one-time migrations, checks readiness, diagnoses queues, encrypts/exports
backups, verifies isolated recovery and performs explicit rollout/rollback. Migration is
refused while API/worker are live. Rollout keeps writers stopped between backup and schema
migration. Rollback first checks old-image schema compatibility and never downgrades data.
No command invokes down --volumes or resets the development project.

CI definitions cover pinned toolchains/dependencies, PostgreSQL tests/migrations/evaluation,
frontend checks/E2E, container builds, local staging/recovery simulation, dependency and
image scans, full-SHA tagging and checksummed review artifacts. They do not push images.
Manual deployment uses required environment reviewers/no self-approval, main-only validation,
a root/operator acceptance marker, pinned SSH host trust and a pre-installed matching
release. These remote controls must be configured/tested before use; they were not installed
or exercised on a public host.

## Recovery evidence

[Machine-readable staging evidence](milestone-11-staging-result.json) records the final
one-document drill. The archive included the application dump, manifest and original.
Encryption completed in approximately **0.030s**, restore verification in **0.049s**. These
are tiny local tool durations, excluding startup, transfer, host provisioning and approval;
they are **not achieved RPO/RTO**. Proposed targets are daily verified/offsite recovery
points (24h RPO) and 60-minute small-host recovery, pending realistic rehearsal.

The restore target is a separate empty tmpfs database on a separate network. It cannot
point at the live/development database through the verifier. The drill validated revision,
vector extension, document count and exact original bytes, then rejected reuse of a
nonempty target and rejected a deliberately altered encrypted copy. Synthetic containers,
networks and bind-mounted fixture data were cleaned; no persistent fixture volumes remain.

Actual production import into new volumes, credential/session incident handling and
cutover remain a deliberate operator procedure requiring a representative Milestone 12
rehearsal. Same-host encrypted backup storage is not offsite protection. The daily systemd
timer is provided but was not installed/enabled; offsite transfer/alert delivery need real
operator configuration.

## Security scan findings and release decision

[Machine-readable security summary](milestone-11-security-summary.json) ties each scan to
its local image/archive identifiers; filesystem layers were checked against Docker's live
image metadata. Docker containerd index IDs, image config IDs and scanner artifact IDs are
recorded separately, not confused with a published registry reference.

| Candidate | High | Critical | Secret findings | High/critical with a listed fix |
| --- | ---: | ---: | ---: | ---: |
| API / worker | 61 | 2 | 0 | 0 |
| Web | 56 | 1 | 0 | 0 |
| Backup | 61 | 2 | 0 | 0 |
| Proxy | 4 | 0 | 0 | 4 |

These are scanner finding occurrences, not distinct exploitable CVEs; shared OS packages
repeat across images. Debian updates, a current Node 26 patch and removal of unnecessary
runtime tooling reduced the initial findings. Remaining OS findings require vendor/status/
reachability review; the proxy's Go stdlib/x/net findings list newer fixed versions and
need a patched upstream/reviewed build. No blanket exception or certification is asserted.
The configured high/critical gate was actually run and rejected the candidate (exit 1).
Production is **not accepted** until remediation or narrowly reviewed, expiring exceptions
and Milestone 12 acceptance are complete. Full local reports remain under ignored
`infra/runtime/security/`; committed summaries contain no private content.

## Database preservation

No application migration/model change was added. The head remains `6f22cc4c46ad`. Before/
after counts and private hashes matched for all fifteen public development tables and the
revision, including the pre-existing document/job and conversation/messages. No private
row values were printed. The development Compose file, PostgreSQL port 5433, volumes,
authentication/session/RBAC behavior and current records were preserved.

## File inventory

Created:

- `apps/api/Dockerfile`, `.dockerignore`, `app/container_entrypoint.py`,
  `tests/test_deployment.py`.
- `apps/web/Dockerfile`, `.dockerignore`, `src/test/same-origin.test.ts`.
- `infra/compose.production.yml`, `compose.staging.yml`, `.env.example`.
- `infra/deploy/Dockerfile`, `Caddyfile`, `tls.production.caddy`, `tls.staging.caddy`,
  `init-db.sh`, `prometheus.yml`, `evidenceai-backup.service`, `evidenceai-backup.timer`.
- `infra/backup/Dockerfile`, `backup.py`.
- `infra/scripts/deploy.py`, `generate_secrets.py`, `release_manifest.py`, `smoke.py`.
- `.github/workflows/ci.yml`, `deploy.yml`.
- `docs/production-architecture.md`, `deployment-guide.md`, `backup-and-recovery.md`,
  `ci-cd.md`, `production-security.md`, this verification report and the two JSON summaries.

Modified:

- API `core/config.py`, `db/session.py`, `.env.example` for container-safe defaults and
  explicit bounded DB pools.
- Web `next.config.ts`, `package.json`, `.env.example`, `src/lib/api/client.ts`,
  `src/proxy.ts`, `src/components/layout/settings.tsx` for standalone/Webpack/same-origin.
- Root `.gitignore`, `README.md`, `docs/frontend-architecture.md`,
  `docs/operational-runbook.md`.

## Manual launch and Milestone 12

Follow the deployment guide: publish exact accepted candidates deliberately, escrow secrets
and an offline recovery key, fill a private env file, validate staging, run its drill, and
configure operator-only monitoring/offsite backup/approval protections. For a future approved
production host, configure DNS/firewall/TLS reachability and immutable digests, then invoke
the production wrapper with explicit acknowledgement. No public launch is authorized by
this report.

Milestone 12 should address scanner triage/remediation first, execute actual hosted CI and
environment approvals, test the intended CPU architecture/host, validate public ACME/renewal
and SSH controls, rehearse realistic offsite recovery/rollback, measure load/capacity and
failure recovery, verify alert delivery/retention/credential rotation and document explicit
acceptance. Managed DB/PITR/HA, external secret management, S3 migration, host disk encryption
and finer runtime DB privileges remain planned boundaries, not implemented guarantees.
