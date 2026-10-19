# Security remediation 12.2 — verification record

Baseline: clean `0f58dcf0b0a5777acd48da738bd1aa460a9bc0ab`. Final decision:
**FAIL / BLOCKED**. All commands below were local; no hosted success is inferred.
Run from `/Users/redmug/EvidenceAI` unless a working directory is shown.
[Machine-readable commands](evidence/m122/commands.json) include exact arguments,
working directories, exit codes and results. Detailed raw logs/full scan JSONs and
image archives remain under ignored `infra/runtime/m122/`; reviewable summaries,
build logs, backend XML, audit JSON and file hashes are retained in
[the evidence directory](evidence/m122/).

## Regression commands and observed results

| Working directory | Executed command | Exit / observed result |
| --- | --- | --- |
| root | `git status --short` / `git rev-parse HEAD` | Initially clean / exact baseline above |
| apps/api | `EVIDENCEAI_TIMING_REPORT=/Users/redmug/EvidenceAI/docs/evidence/m122/registration-timing.json .venv/bin/python -m pytest -q --junitxml=/Users/redmug/EvidenceAI/docs/evidence/m122/backend.xml` | 0; 653 passed in 26.51s; existing Starlette/httpx deprecation warning |
| apps/api | `.venv/bin/python -m pytest -q tests/test_deployment.py` | 0; 26 passed in 0.27s after fixture changes |
| apps/api | `.venv/bin/python -m alembic current` | 0; `91e2b6d8c410 (head)` |
| apps/api | `.venv/bin/python -m alembic check` | 0; no new upgrade operations |
| apps/api | `.venv/bin/python -m pip check` | 0; no broken requirements |
| apps/web | `npm test` | 0; 53 passed / four files; final explicit-exit rerun retained |
| apps/web | `npm run lint` | 0 |
| apps/web | `npx tsc --noEmit` | 0 |
| apps/web | `npm run build` | First 1: concurrent Playwright build owned the build lock. Sequential retry 0: all routes compiled successfully. No lock force-deletion or application change. |
| apps/web | `PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers npm run test:e2e` | 0; 18 passed in 1.3m; six Chromium, six Firefox, six WebKit |
| apps/api | `/tmp/evidenceai-m11-audit-venv/bin/python -m pip_audit -r requirements.txt --format json` | 0; 44 dependencies, zero vulnerabilities |
| apps/web | `npm audit --omit=dev --json` | 0; zero runtime vulnerabilities |
| apps/web | `npm audit --json` | 1; five high development lint-chain nodes, one braces advisory |
| apps/web | `npm view braces version --json` | 0; `3.0.3`, still affected |

Backend auth coverage includes generic registration for new/existing/disabled/case
variants, salted password hashes, stored proof hashes, no preverification login,
TTL, same-browser proof, replay denial, duplicate race protection, preservation of
existing credentials/sessions, CSRF and IP/recipient budgets. Practical timing
comparison: 20 paired requests per class, existing median 30.501ms versus new
30.590ms, difference 0.089ms (unchanged bound 20ms). It is limited local evidence.
[Browser case list](evidence/m122/browser-summary.log) covers research/citations/
history, authorization, private content, expired session, responsive layout,
keyboard navigation, roles/ownership and recoverable failures in all engines.

## Container commands and strict policy

These commands exported and scanned the existing seven `m121` images and selected
pinned Grafana without rebuilding completed application features:

```sh
python3 infra/scripts/scan_images.py --tag m121 --directory infra/runtime/m122/candidates
# exit 0: API, web, backup and proxy each 0 high / 0 critical / 0 secrets
python3 infra/scripts/scan_images.py --tag m121 --support-only --directory infra/runtime/m122/support
# exit 1: database/Prometheus/exporter each 0; Grafana 61 high / 0 critical / 0 secrets
python3 docs/evidence/m122/generate_inventory.py
# exit 0: eight selected and two experimental archive/config/live identities match
```

Trivy image reference/version, DB metadata, scan times, image platform and hashes
are in [inventory](security-remediation-12-2-inventory.json). DB was updated
2026-10-19T19:08:34.442427859Z, downloaded at 20:00:17.97068243Z for supporting
scans. Counts match 12.1 despite the refreshed DB. Full reports retain lower
severities too. API/worker share one image. All local images are Linux ARM64.
Scanner containers receive narrow dedicated archive/report/cache mounts; no
Docker socket, host `.env`, provider secret or customer storage enters them.

The exact experimental core build command ran inside a Python subprocess with
`timeout=600`, not a weakened scanner policy:

```sh
docker build --progress=plain -t evidenceai-grafana:experimental-m122 infra/monitoring/grafana-rebuild
# exit 0, 322.33s; subsequent complete-image scan: 56 high / 0 critical / 0 secrets
```

The initial executed OpenTSDB build command was
`docker build --progress=plain -t evidenceai-grafana:m122 infra/monitoring/build-grafana`
(exit 0). That experimental recipe was subsequently consolidated into the rebuild
directory. Its equivalent reproducible command in the delivered tree is:

```sh
docker build --progress=plain -f infra/monitoring/grafana-rebuild/opentsdb.Dockerfile -t evidenceai-grafana:m122 infra/monitoring/grafana-rebuild
```

Downloaded official ARM64 plugin ZIP SHA-256:
`089b71a3c576dec39003ae809902428d54462c05d58d39a50f075f1180567859`, matching
catalog metadata. It declares Grafana >=12.3.0-0. Complete-image scan still reports
61 high / 0 critical / 0 secrets. Neither experiment is selected by production.

Each experimental full image was scanned with the following actual command
pattern (GROUP=`grafana-core` or `grafana-candidate`, IMAGE respectively
`evidenceai-grafana:experimental-m122` or `evidenceai-grafana:m122`):

```sh
docker save IMAGE -o infra/runtime/m122/GROUP/archives/grafana.tar
docker run --rm \
  -v /Users/redmug/EvidenceAI/infra/runtime/m122/GROUP/archives:/scan:ro \
  -v /Users/redmug/EvidenceAI/infra/runtime/m122/GROUP:/reports \
  -v /Users/redmug/EvidenceAI/infra/runtime/m122/support/trivy-cache:/root/.cache \
  aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222 \
  image --input /scan/grafana.tar --scanners vuln,secret --format json --output /reports/grafana.json
```

Export/scanner execution returned 0: this means successful report generation,
**not** security acceptance. The strict evidence evaluation rejects both reports
because high findings remain. Supporting selected-image policy itself returned
1. The preliminary plugin-only `trivy fs` attempt returned no language files and
was rejected as inadequate coverage; it is never counted as a clean plugin scan.
No suppression or gate change was introduced.

Official catalog discovery was executed for each of thirteen IDs using
`curl --fail --silent --show-error --max-time 30 https://grafana.com/api/plugins/ID/versions`;
source Go modules were fetched from their catalog commit on
`raw.githubusercontent.com`. [Catalog](evidence/m122/grafana-catalog-curl.json),
[plugin manifests](evidence/m122/grafana-plugins.json) and
[source requirements](evidence/m122/grafana-source-requirements.json) retain URLs,
versions, commits and checksums. Initial system-Python requests failed certificate
trust; the verified OS curl retry succeeded without disabling TLS checks.
`docker buildx imagetools inspect grafana/grafana:13.2.5` returned 1 / not found.
The official patched-source commit API request returned HTTP 422 / no commit found;
response retained. Upstream documentation/release links are in the assessment.

## Staging, monitoring and recovery commands

```sh
EVIDENCEAI_EVIDENCE_TAG=m122-core EVIDENCEAI_GRAFANA_IMAGE=evidenceai-grafana:experimental-m122 python3 infra/scripts/smoke.py
# exit 0, experimental core functional checks and basic encrypted recovery
EVIDENCEAI_ACCEPTANCE=1 EVIDENCEAI_EVIDENCE_TAG=m122 python3 infra/scripts/smoke.py
# exit 0, selected-image full staging, bounded load and restored-app drill
```

The new override affects only the disposable smoke overlay; production remains
pinned. Evidence tags separate output paths from image tags and preserve earlier
milestone results. Both fixtures verified admin authentication, 401 anonymous
search, disabled signup, provisioned dashboard, datasource health, and actual
Grafana-proxied Prometheus `up` results for two targets. Docker inspection found
one internal monitoring network, no published Grafana ports and healthy status.
Synthetic generated admin secrets entered the checker through stdin only.

The final acceptance reused production resource/security settings with private-CA
HTTPS and loopback ports, unique project, tmpfs database and fixture-only bind
storage. No development volumes were attached. The Go builds and experimental
fixture completed before the final load run. The harness invoked pinned Locust
from `/tmp/evidenceai-m12-load/bin/locust`: five users, spawn rate 1/s, 30s,
stop timeout 10s, preserved threshold file `infra/load/thresholds.json`.

Observed: **334 requests, 0 failures, 11.189 req/s; p50 9ms, p95 39ms, p99 58ms**.
Minimum 100 samples, <=1% errors, p95<=2000ms, p99<=5000ms, queue drain<=60s and
no failed jobs all passed. Full final counters/resources/DB measurements are in
[load.json](evidence/m122/load.json). Providers are fake/mock and documents tiny;
this does not establish production capacity or hosted AI quality.

Backup encrypted 22 database document records and 22 originals; backup 0.058s,
restore 0.090s. Restored schema `91e2b6d8c410` and pgvector 0.8.7, checksums,
authenticated session, fresh login, original and queued-document downloads and
pending queue recovery passed. Full restored-application recovery **45.687s**
(threshold 120s); last acknowledged write to backup completion 1.132s, zero lost
acknowledged synthetic writes with writers quiesced. Nonempty restore target and
tampered ciphertext were rejected. Their expected error log lines are successful
negative tests, not unnoticed recovery failures. No OOM or exit137; API exit143
(SIGTERM), worker/proxy exit0. Details: [staging.json](evidence/m122/staging.json).
These same-host measurements do not establish offsite production RTO/RPO.

Current-schema rollback was not invoked: the historical M11 artifact expects an
older revision and is not an accepted predecessor. Hosted rollout/rollback remains
NOT VERIFIED; the approved procedure is in the hosted checklist.

## CI/CD, preservation and final gate

```sh
docker run --rm --network none \
  -v /Users/redmug/EvidenceAI/.github/workflows:/work:ro -w /work \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 \
  -color ci.yml deploy.yml
# exit 0
python3 infra/scripts/release_manifest.py --output infra/runtime/m122/manifest.json
# expected exit 1: requires clean committed source; user prohibited committing
python3 infra/scripts/verify_release.py docs/evidence/m122/release-result.json
# exit 1 / BLOCKED
```

Deployment regressions preserve immutable production image requirements, exact-SHA
and review source guards, migration writer quiescence, separate logical DB migration,
secret paths and nondestructive restore guards. The reviewed CI still scans the
pinned Grafana under the strict supporting-image gate; both experiments remain
outside production packaging. Hosted CI, reviewer policy, branch protection, SSH
fingerprint and operator acceptance execution are NOT VERIFIED.

Private preservation commands used the project interpreter:
`PYTHONPATH=apps/api apps/api/.venv/bin/python /tmp/m122_snapshot.py before` and
`... /tmp/m122_snapshot.py after`. The helper reads deterministically ordered full
rows from sixteen hardcoded public tables, hashes them and compares counts/hashes
and revision, publishing no rows. Before/after snapshots stay outside Git.
[Aggregate preservation evidence](evidence/m122/data-preservation.json) passes all
sixteen tables, including existing rate-limit buckets and registration intents.
A system-Python attempt to format the final report lacked SQLAlchemy; using the
project interpreter corrected it and the read-only comparison passed. No data was
changed to make preservation pass. Final `git diff --check` passes; no application
or development Compose changes were made.

Hosted staging and real-provider SMTP remain **NOT VERIFIED**. The concrete
[acceptance checklist and safe mail procedure](hosted-staging-acceptance.md) cover
authorization, DNS/TLS/proxy, services, private storage, inbox receipt, isolation,
offsite restore and controlled rollback. No real email or public deployment was
performed. The selected runtime's 61 high findings alone block production release.
