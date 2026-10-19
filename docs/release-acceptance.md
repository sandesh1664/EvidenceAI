# Production release acceptance — Security Remediation 12.2

**FAIL / NO-GO — production release BLOCKED.** Baseline
`0f58dcf0b0a5777acd48da738bd1aa460a9bc0ab`; clean on initial inspection. This report
supersedes the M12/12.1 release decision for the present working tree. New changes
remain uncommitted. Local execution: 2026-10-19 UTC / October 20 Dubai at completion.

| Criterion | Classification | Evidence / practical limit |
| --- | --- | --- |
| Selected runtime container policy | **FAIL** | 61 high / 0 critical / 12 distinct advisories, all Grafana; supporting-image gate exits 1. Seven other images have zero high/critical/secret findings. |
| Experimental core remediation | **FAIL** | Built in 322.33s, five findings removed, 56 high remain; local functionality passes, patched vendor-source parity NOT VERIFIED; image not selected. |
| Official compatible OpenTSDB update | **FAIL** | Rebuilt complete image with 13.0.5 still has 61 high; image not selected. |
| Local identity/application controls | **PASS** | Generic registration, proof generation/expiry/single-use/replay/binding, duplicate safety, CSRF and rate limiting preserved; synthetic TLS SMTP delivery works. |
| Real-provider SMTP and inbox acceptance | **NOT VERIFIED** | No real credentials/provider/inbox tested; operator procedure prepared. |
| Backend/frontend/types/lint/build | **PASS** | 653 backend, 53 frontend; lint/types/build passed. Initial standalone build-lock collision retained; sequential retry passed. |
| Chromium / Firefox / WebKit | **PASS** | 18 local browser cases, six per engine. |
| Python and runtime npm audits | **PASS** | 44 Python dependencies and runtime npm clean. |
| Development dependency audit | **FAIL** | Five high lint-chain nodes from one braces advisory; latest compatible 3.0.3 remains affected. |
| Grafana operational acceptance | **PASS** | Selected and experimental core images: startup/health, admin auth, anonymous/signup denied, dashboard provisioning, datasource health, two Grafana-proxied Prometheus targets up, internal-only network and no published port. Functional pass is not security acceptance. |
| Local bounded synthetic performance | **PASS** | 334 requests, zero failures, p50 9ms / p95 39ms / p99 58ms; five users, 30s, tiny corpus, fake/mock providers. |
| Local encrypted recovery | **PASS** | 22 documents/files, checksums, Alembic `91e2b6d8c410`, pgvector 0.8.7, session/fresh login, original download and pending-job recovery; 45.687s restored-app recovery. |
| Existing development data and Compose | **PASS** | All sixteen existing public-table counts and ordered row hashes unchanged; revision unchanged; development Compose unchanged. |
| Local CI/CD and migration guards | **PASS** | Actionlint, 26 deployment guard tests, Alembic current/check, fail-closed container gate and dirty-source packaging refusal. |
| Hosted CI/CD and repository protections | **NOT VERIFIED** | No workflow dispatch, SSH operation, branch/environment policy verification or public deployment. |
| Hosted model/representative capacity/production RTO/RPO | **NOT VERIFIED** | Offline providers and same-host synthetic fixture only. |
| Hosted staging, public TLS/DNS, offsite restore, key escrow and alerts | **NOT VERIFIED** | Explicit checklist prepared; no authorized hosted environment was available/exercised. |
| Current-schema rollback to an accepted predecessor | **NOT VERIFIED** | No accepted prior artifact or hosted rehearsal; historical M11 rollback does not prove compatibility with current schema. |
| Intended AMD64 and independent whole-image reproducibility | **NOT VERIFIED** | Local tests are ARM64; pinned inputs do not establish independent whole-image reproducibility. |

PASS applies only to the stated observed scope. FAIL and NOT VERIFIED never become
passes through local functional success. The unchanged formal gate evaluates
[release-result.json](evidence/m122/release-result.json) and returns **exit 1 /
BLOCKED**, with container security, hosted AI, hosted CI/CD and production
environment criteria unmet. No exception has been approved or self-issued.

The selected Grafana image remains
`grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f`.
The experimental image's smaller count is not represented as the selected
production result. All thirteen vulnerable datasource executables remain intact;
no scan suppression, severity downgrade, ignored-unfixed flag, unsigned-plugin
allowance or release-gate change was introduced.

Review the [formal 12.2 assessment](security-remediation-12-2.md),
[complete vulnerability inventory](security-remediation-12-2-inventory.json),
[verification and exact commands](security-remediation-12-2-verification.md),
[implementation source manifest](evidence/m122/source-manifest.json),
[evidence checksums](evidence/m122/evidence-sha256.json),
[release checklist](release-checklist.md) and
[hosted staging / real SMTP procedure](hosted-staging-acceptance.md).
Earlier M12 and 12.1 measurements remain historical evidence, not current passes.

Before a later release, obtain complete supported Grafana/plugin fixes, scan/test
the final artifacts on the intended architecture, complete authorized SMTP and
hosted operational acceptance, review protected exact-SHA CI and recovery/
rollback evidence, deliberately commit/review final source, and obtain named
release-authority approval. No source commit, push, public deployment, DNS change,
purchase, real external email, development data reset or Docker-volume deletion
was performed as part of 12.2.
