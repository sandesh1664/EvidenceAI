# Security remediation 12.1 verification

**Final recommendation: BLOCKED — do not approve production release.**
Baseline `4107cb379185f55956c37efdfc7aa4d48714f913`, inspected clean. Implementation
and reports remain uncommitted. Exact changed-source hashes and image layers are
recorded in [source evidence](evidence/m121/source-manifest.json) and
[security inventory](security-remediation-inventory.json).

## PASS / FAIL / NOT VERIFIED

| Verification | Classification | Actual result |
| --- | --- | --- |
| Original database critical findings | PASS | Both removed; new libxml2 runtime, gosu absent, root/old-cluster startup refused. |
| Seven rebuilt runtime images | PASS | Zero high/critical/secret findings; direct Trivy gates exit 0. |
| Grafana image gate | FAIL | 61 high occurrences, 12 advisory IDs; direct gate exit 1. |
| Overall runtime release policy | FAIL | No severity threshold lowered, no ignore-unfixed flag, no CVE suppressions or exceptions. |
| Registration privacy tests | PASS | Uniform202, no identity/session before proof, no chosen-password probe, existing passwords/disabled state/sessions unchanged. |
| Practical registration timing check | PASS | 20 paired observations/class; 2.65 ms median difference, bound20 ms. Synthetic loopback scope only. |
| Backend host suite | PASS | **653 passed**, 23.06s, including a final database-image rollout guard. |
| Backend actual Alpine runtime | PASS | **652 passed**, 19.07s; all runtime/security tests. The later pure deployment guard is included in the host count. |
| Frontend lint / TypeScript / unit tests | PASS | Lint and tsc pass; **53 tests passed**. |
| Frontend production build | PASS | Standalone Alpine image and Playwright's real production build completed. |
| Chromium / Firefox / WebKit | PASS | **18 flows passed**, including registration proof, login, role boundaries, documents, citations, persistence, mobile viewport, failures and keyboard interactions. |
| Alembic migration/current/check | PASS | Additive revision `91e2b6d8c410`; isolated and local checks show no model drift. |
| Python consistency/vulnerability audit | PASS | pip check passes; pip-audit2.10.1 finds zero across44 pinned requirements. |
| npm production audit | PASS | Zero findings. |
| npm development audit | FAIL | Five high lint-chain affected nodes retained and documented. |
| TLS staging, real synthetic SMTP and worker checks | PASS | Uniform acceptance, login blocked before proof, verified SMTP TLS fixture delivery, Secure cookies/CSRF/proxy/storage/metrics checks. |
| Bounded repeat load | PASS | 375 requests, zero errors; five users/30s; p50 8 ms, p95 31 ms, p99 64 ms. Tiny fake/mock corpus only. |
| Encrypted backup and restored application | PASS | 27 originals/DB documents, SHA-256 integrity, pgvector0.8.7, revision91e2b6d8c410, existing session, fresh login, downloads and pending worker job. |
| Recovery duration | PASS | 46.040s local drill; encryption helper0.059s, restore helper0.107s. Zero acknowledged synthetic writes lost; not a production RTO/RPO. |
| Negative recovery / shutdown | PASS | Populated target and altered ciphertext rejected; API143, worker0, proxy0; no OOM/SIGKILL. |
| Existing records and volumes | PASS | All original rows preserved; one additional localhost-login throttle bucket retained. New table/revision intentional; existing DB image and volumes unchanged. |
| Workflow lint and source rollout guards | PASS | actionlint passes; image-change guard refuses DB swaps before any app rollout operation. |
| Hosted CI/deployment/approval controls | NOT VERIFIED | Source checked locally; no push, dispatch, remote SSH or public rollout performed. |
| Grafana custom rebuild | NOT VERIFIED | Source dependency resolution succeeded; binary build did not complete and was stopped, never promoted. |
| Real external email delivery / production SMTP | NOT VERIFIED | No external messages sent; production setup defaults disabled and must be verified by operator. |
| Whole-image bit reproducibility / AMD64 / hosted AI / offsite production recovery | NOT VERIFIED | No new claim superseding the remaining Milestone12 boundaries. |

Automated fixtures/source review are not an independent penetration test. Local
screens/axe and keyboard tests do not certify every assistive technology or device.

## Reproduce

Use the documented Python/Node toolchains and Docker. Never point tests at a
production database. Pytest owns generated schemas; browser fixtures own a schema,
temporary originals and synthetic mail directory. The staging harness creates its
own tmpfs/bind-mounted project and private CA/SMTP sink. It never resets development
volumes. Preserve an encrypted recovery point before a real migration/cutover.

```sh
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m pip check
cd ../web
npm run lint
npx tsc --noEmit
npm test
npm run build
PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers npx playwright install chromium firefox webkit
PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers npm run test:e2e
cd ../..
docker build -t evidenceai-api:m121 apps/api
docker build -t evidenceai-web:m121 apps/web
docker build -t evidenceai-backup:m121 infra/backup
docker build -t evidenceai-proxy:m121 infra/deploy
docker build -t evidenceai-database:m121 infra/database
docker build -t evidenceai-prometheus:m121 infra/monitoring/build-prometheus
docker build -t evidenceai-exporter:m121 infra/monitoring/build-exporter
python3 infra/scripts/scan_images.py --tag m121 --directory infra/runtime/m121/candidates
# Expected exit0 for the current seven patched candidates; first command scans four app images.
python3 infra/scripts/scan_images.py --tag m121 --support-only --directory infra/runtime/m121/support
# Expected exit1: Grafana remains included and blocking.
python3 -m venv /tmp/evidenceai-m12-load
/tmp/evidenceai-m12-load/bin/pip install -r infra/load/requirements.txt
EVIDENCEAI_ACCEPTANCE=1 python3 infra/scripts/smoke.py
```

For repeatable timing capture set `EVIDENCEAI_TIMING_REPORT` to an owned absolute
output path when running `tests/test_auth.py`. The test contains the predefined
sample count/order/bound and writes no identities, tokens or passwords.

The complete Alpine run used the Dockerfile `dependencies` target, a sanitized
read-only source tree (no `.env`/private data), UID10001, and the network namespace
of the disposable tmpfs PostgreSQL instance, with only its loopback test connection.
No dependency/test package was added back to the production runtime.

Workflow validation used network-disabled pinned actionlint. Trivy used its pinned
0.76.0 image, newly downloaded DB (updated2026-10-19T13:35:30Z), narrow image-archive
mounts and no Docker socket in the scanner. Strict per-image gates used
`--scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1` and a fresh cached
DB; all results are retained in [strict gates](evidence/m121/strict-gates.json).
A future vulnerability DB refresh can change counts; compare stored scan hashes,
DB metadata, source hashes and layer IDs rather than relying on tag names alone.

## Retained failures and limitations

The first Alpine database still contained gosu; its scan found the critical Go
finding and led to actual executable removal plus root refusal. A secure-cookie
test initially used HTTP and correctly received403; it was corrected to HTTPS,
not by weakening middleware. A fixture cleanup attempt failed on read-only SMTP
key files and was corrected/retested. One load run collected81 requests after a
long execution gap, below the unchanged minimum100, and is retained in
[failed load evidence](evidence/m121/interrupted-load.json). The final repeat passed
375 requests; no production capacity is asserted. The uncompleted Grafana build
was stopped, not reported as successful or as evidence of API incompatibility.

The additive migration was applied locally only after isolated migration/runtime
verification. Before/after private row hashes prove original rows unchanged;
[data preservation](evidence/m121/data-preservation.json) explicitly records the
extra throttle bucket and revision transition. No original row or existing volume
was deleted/restored to make this check pass.

## Changed files and evidence

Modified authentication schemas/routes/service/settings and file-secret injection;
frontend auth/API/verification flow and test fixtures; API/web/backup Dockerfiles;
production Compose/deployment/env/secret-generation/manifest/scan/CI definitions;
backup/readiness revision guards; staging harness and tests. Added registration
model/migration/service, verification page, guarded PostgreSQL build, locked
Prometheus/exporter builds and the private SMTP test fixture.

The source manifest lists every changed/new code file and its SHA-256. Additional
evidence includes baseline/final image inventory, registration samples, backend
JUnit, browser cases, audits, stage/load/recovery outputs, database guards and
report checksums. Full private/raw scan reports, candidate archives and failed
build logs remain under ignored `infra/runtime/m121/`.

Production acceptance requires a fully patched/tested Grafana core **and bundled
plugins**, real operator SMTP acceptance, remaining hosted infrastructure/approval
checks and named release/security review. Existing M12 application rollback must
first pass schema compatibility checks; the new revision is not silently treated
as compatible with an older image's hard-coded readiness/backup revision. Keep
matching old backup tooling for old encrypted archives. App rollout forbids database
image changes; migrating glibc data to Alpine requires a separately reviewed
fresh-volume logical restore and collation/index/application validation.

**No commit, push, public deployment, real email delivery, DNS change, purchase,
existing-volume reset or vulnerability exception was performed. Release BLOCKED.**
