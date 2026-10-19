# Milestone 12 formal release acceptance

**NO-GO — production release BLOCKED.** Date: 2026-10-19 UTC.

Exact starting revision: `02462040fec9eea53c596618c32b09cb694d60ee`; the repository
was clean on inspection. The tested changes remain **uncommitted**. This baseline
alone does not identify the complete candidate: combine it with the changed-file
hashes and fingerprint in [source manifest](evidence/m12/source-manifest.json).
No commit, push, public deployment, DNS change, purchase, development reset or
persistent volume removal was performed. No release exception was approved.

## Decision and critical criteria

PASS means verified within the stated test scope. FAIL means tested and not
satisfied. NOT VERIFIED means evidence or the required environment is missing.
Local success never promotes an unverified production requirement.

| Criterion | Classification | Evidence / limitation |
| --- | --- | --- |
| Runtime container vulnerability policy | **FAIL** | 300 high and 2 critical occurrences remain; strict gates reject candidates. |
| Application security assessment | **FAIL** | Automated authorization/storage/session controls pass; registration account enumeration remains medium severity. |
| Deterministic AI guards and offline evaluation | **PASS** | 68 units, thresholds met; one false abstention retained. |
| Hosted AI security and semantic support | **NOT VERIFIED** | No hosted model was called; citation validity does not establish entailment. |
| Backend/frontend regression | **PASS** | 642 backend and 51 frontend tests; lint/types and standalone image build pass. |
| Cross-browser acceptance | **PASS** | 18 tests across Chromium, Firefox and WebKit, including responsive UI and native keyboard form navigation; final case details linked below. |
| Local bounded performance | **PASS** | Five users/30 seconds, tiny synthetic corpus, offline providers; see benchmark. |
| Local encrypted recovery and authenticated restored operation | **PASS** | DB/documents/checksums, pgvector, migration, existing session, fresh login, downloads and pending job recovered. |
| Local rollback compatibility | **PASS** | Previous M11 backend/worker candidate on disposable restored data and return to M12. No accepted production predecessor exists. |
| Local CI/CD source controls | **PASS** | actionlint, SHA/history/CI checks, required-reviewer source guard, immutable production refs and migration/live-writer guards. |
| Hosted CI/CD, repository protection, SSH and approval execution | **NOT VERIFIED** | No workflow dispatch/push or public host operation. Actual branch protections and environment policies not queried/configured. |
| Whole-image reproducibility / intended AMD64 platform | **NOT VERIFIED** | Proxy binary rebuilt identically; all local images tested ARM64. OS repos/transitive artifacts are not fully frozen. |
| Public TLS, host hardening, offsite restore and production RTO/RPO | **NOT VERIFIED** | Private CA and same-host fixture only. |
| Existing development records and migration integrity | **PASS** | Fifteen public tables/revision privately hashed before/after; current head unchanged, no model drift. |

The [machine-readable decision](evidence/m12/release-result.json) is evaluated by
`infra/scripts/verify_release.py`; missing, FAIL or NOT VERIFIED critical criteria
produce exit 1. This report does not authorize a waiver. Infrastructure/security,
identity/product, AI, SRE, QA and repository-administrator roles must assign named
owners and obtain release-authority review after remediation.

## Final image scans

| Runtime image | High | Critical | Secret findings |
| --- | ---: | ---: | ---: |
| api | 44 | 0 | 0 |
| web | 43 | 0 | 0 |
| backup | 44 | 0 | 0 |
| proxy | 0 | 0 | 0 |
| database | 86 | 2 | 0 |
| prometheus | 8 | 0 | 0 |
| grafana | 61 | 0 | 0 |
| exporter | 14 | 0 | 0 |

These are repeated package/advisory occurrences, not distinct exploitable CVEs.
Expanded scope includes the pinned DB and monitoring images omitted from the M11
application-image gate. All eight scans have layer identities checked against the
live local image metadata. API/worker share one image. Raw Trivy reports and
archives are under ignored `infra/runtime/m12/`; normalized findings, scan hashes,
image IDs and scanner/database versions are in
[container evidence](evidence/m12/container-summary.json) and
[security assessment](security-assessment.md).

Trivy's original HIGH/CRITICAL gate actually returned API=1, web=1, backup=1,
proxy=0; the supporting-image gate also returned 1. It was not disabled, lowered,
or changed to ignore unfixed findings. New CI adds the supporting-image gate.
Patched inputs reduced the application candidates from 187 high/critical
occurrences to 131, with all five original critical occurrences removed. Expanded
supporting-runtime scans fell from 373 to 171 occurrences, including two remaining
critical findings in the DB image. Their presence independently blocks release.

Python dependency audit: zero findings, 44 pinned requirements. Runtime npm audit:
zero. Development npm audit: five high affected nodes in the lint chain, retained
and documented. Independent proxy binary rebuild SHA-256 is recorded in the image
summary; this is narrower than whole-image reproducibility.

## Environment and evidence

Local macOS 26.5.1 ARM64, Docker Desktop Linux ARM64, Docker 29.9.1; VM advertises
10 CPUs and 8,319,504,384 bytes memory. Staging reused production resource/security
settings with loopback 18080/18443, a verified private CA and unique synthetic
secrets. Its DB and restore DB use tmpfs; generated private document and monitoring
bind directories are removed after the fixture. Development PostgreSQL and
storage are outside this project. PostgreSQL candidate 17.11 / pgvector 0.8.7;
Alembic head remains `6f22cc4c46ad`. Providers are fake/mock or explicit mocked HTTP
transports. No hosted credential or customer document enters the tests.

- [Security assessment](security-assessment.md): findings, controls, CVE inventories, boundaries and proposed owners.
- [Performance benchmark](performance-benchmark.md): preset thresholds, endpoint p50/p95/p99, throughput, errors and sampled resources/I/O.
- [Recovery drill](disaster-recovery-test.md): measured durations, restored application, queue, integrity, rollback and RPO/RTO limits.
- [Test results](evidence/m12/test-results.json): regression and per-browser case outcomes, including retained earlier failures.
- [Release checklist](release-checklist.md): remaining dependencies and release responsibilities.
- [Evidence checksums](evidence/m12/evidence-sha256.json): integrity index for delivered evidence and formal reports.

Earlier fixture failures were retained: missing browser binaries, ambiguous alert
selectors, a nested Grafana mount failure, an incorrect benchmark SQL state column,
and expected 409 responses to accidentally duplicated load uploads. Corrections
were retested; no failed security gate was converted into a pass. The offline AI
report retains `backup-answer` as an incorrect false abstention (17/18 RAG cases),
despite passing its explicitly defined aggregate thresholds.

## Reproduction commands

Run from this source tree. The application tests require the existing loopback
PostgreSQL connection but create/drop only their own generated schemas. Never
point them at a public or production database. No command below resets dev data.

```sh
git rev-parse HEAD
git diff --check
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m pip check
.venv/bin/python -m app.evaluate --repeat 3 --output-dir evaluation/reports
cd ../web
npm run lint
npx tsc --noEmit
npm test
PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers npx playwright install chromium firefox webkit
PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers npm run test:e2e
cd ../..
docker build -t evidenceai-api:m12 apps/api
docker build -t evidenceai-web:m12 apps/web
docker build -t evidenceai-backup:m12 infra/backup
docker build -t evidenceai-proxy:m12 infra/deploy
python3 -m venv /tmp/evidenceai-m12-load
/tmp/evidenceai-m12-load/bin/pip install -r infra/load/requirements.txt
EVIDENCEAI_ACCEPTANCE=1 python3 infra/scripts/smoke.py
python3 infra/scripts/scan_images.py --directory infra/runtime/m12
# Expected exit 1 while the reported vulnerabilities remain.
python3 infra/scripts/scan_images.py --support-only --directory infra/runtime/m12/support
# Expected exit 1; pinned supporting images must be present locally.
python3 infra/scripts/verify_release.py docs/evidence/m12/release-result.json
# Expected exit 1 / BLOCKED.
```

For the additional rollback drill, supply
`EVIDENCEAI_ROLLBACK_IMAGE=evidenceai-api:m11` with `EVIDENCEAI_ACCEPTANCE=1` to
`smoke.py`. That exact preserved local candidate is the only allowed prior image.
Without it, rollback is explicitly NOT VERIFIED, not silently passed. M11 was a
blocked candidate too; this experiment verifies compatibility, not authorization
to promote it. Workflow lint used pinned
`rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667`
with only `.github/workflows` mounted read-only and no network. Audit tools were
pip-audit 2.10.1 and npm audit; Trivy version/image/DB times are in the evidence.
Networked audit databases and mutable package repositories mean later counts can
change; preserve the report/database fingerprints for comparisons.

## Deployment dependencies and rollback procedure

Before any proposed production rollout: resolve blocking vulnerabilities and
identity enrollment, review hosted AI behavior if enabled, commit/review the final
source deliberately, run hosted AMD64 CI, inspect every gate artifact, freeze
immutable image/source digests, verify encrypted offsite recovery and key escrow,
configure required reviewers/no self-approval/main protection, and provision the
operator acceptance marker and pinned SSH host identity. Configure/verify DNS,
firewall, public ACME renewal, alert delivery and named operational ownership only
under separate authorization. Current source remains uncommitted and fails the
existing clean-source release packaging prerequisite.

For a later accepted deployment, keep the previous accepted digest env file and
pre-migration encrypted recovery point. Pause writers; check the previous app
against the current Alembic schema before invoking explicit application rollback
through `infra/scripts/deploy.py` with the reviewed previous env file. Recreate
only application services, verify readiness/authentication/downloads/queue/metrics,
and keep the database and originals. Never auto-downgrade the schema or overwrite
live volumes. An incompatible schema requires a separately authorized recovery
into new isolated volumes and an audited cutover; do not attempt destructive
in-place reversal. See [backup/recovery guide](backup-and-recovery.md).

## Implemented file groups

Modified Dockerfiles for API, web, backup and proxy; production Compose and separate
Grafana provisioning; expanded Playwright config/tests; backup restore destination
guards and deployment tests; staging/load/recovery/rollback harness; CI and manual
deploy workflows. Added locked Caddy build sources, Locust workload/thresholds,
image scan/inventory and release-decision tools; five requested formal reports
and reproducible evidence. The exact code-file inventory and hashes are in the
source manifest. No application migration or existing development Compose change
was introduced.

**Formal recommendation: withhold production approval.** Re-evaluate this checklist
only after failed criteria are remediated and missing evidence is supplied by the
responsible owners. Local test success does not override the security gate.
