# Production release acceptance — Security Remediation 12.3

**FAIL / NO-GO — production release BLOCKED.** Date: **2026-10-20, Asia/Dubai**.
Clean starting revision: `5d4571d87b0ab866f0942c4a52bdd0cad89e264c`.
12.3 changes remain uncommitted. This supersedes the earlier working-tree decision;
earlier reports remain historical evidence, not current verification.

| Criterion | Result | Actual evidence / limitation |
| --- | --- | --- |
| Selected runtime container policy | **FAIL** | Grafana 13.2.4 retains **61 high / 0 critical**, 12 distinct blocking advisories; seven other runtime images pass. Selected production pin unchanged. |
| Maintained upstream replacements | **FAIL** | Full scans: 13.2.4-distroless 61 high, 13.1.8 15, 13.0.11 10, 12.4.13 5; all zero critical/secrets, all security-rejected and unselected. Full replacement operational compatibility NOT VERIFIED. |
| Core rebuild security | **FAIL** | Build/patch/provenance and functionality verified; **56 high remain**, matching the previous experiment. Removes five selected-image occurrences, not five additional 12.3 fixes. |
| Current signed plugin upgrade | **FAIL** | Cloud Monitoring 12.6.3 verified ZIP/actual binary still has all six highs; plugin-only 61, combined core/plugin 56. Both unselected. |
| Build/source evidence | **PASS** for recorded scope | Actual zero-fuzz patching, resolved modules, pinned Go 1.27.2, source/patch/module/binary checksums; source commit reported verified by GitHub; frontend and original plugins byte-identical. Independent artifact attestation and patched vendor-source parity remain NOT VERIFIED. |
| Grafana local monitoring | **PASS** | Startup/health, admin auth, anonymous denial/signup disabled, provisioning, all thirteen plugin signatures, actual Prometheus queries, internal-only network/no published port and reverse-proxy route denial. Combined image also passes. |
| Local Grafana restart/upgrade/rollback | **PASS** | Same owned synthetic Grafana data: selected restart -> custom core -> selected; dashboard version/state, auth, provisioning and queries preserved. Not production/cross-version rollback authorization. |
| Backend/frontend/types/lint/build | **PASS** | 653 backend, 53 frontend; TypeScript, lint, production build; 26 deployment guard tests. |
| Chromium/Firefox/WebKit | **PASS** | 18 browser cases, six per engine. |
| Python / runtime npm audit | **PASS** | 44 Python dependencies and runtime npm clean. |
| Development dependency audit | **FAIL** | Five high lint-chain nodes remain from braces advisory. |
| Local synthetic load/recovery | **PASS** | 334 requests/zero failures; p95 31ms/p99 87ms. Encrypted restore of 23 documents/originals, session/login/downloads/pending work; restored-app recovery 45.690s. Same-host offline providers only. |
| Existing records/revision/Compose | **PASS** | All sixteen original public-table counts and full-row hashes unchanged; Alembic head `91e2b6d8c410`, no drift; migrations and dev Compose unchanged. |
| Local workflow/release controls | **PASS** | Actionlint and deployment regressions; strict container rejection and dirty-source packaging refusal preserved. |
| Patched vendor-source parity / independent reproducibility / AMD64 | **NOT VERIFIED** | Vendor embedded source SHA still unavailable (HTTP422); actual custom source is traceable but not proven vendor-equivalent; local builds/tests ARM64. |
| Real SMTP inbox delivery | **NOT VERIFIED** | Synthetic TLS SMTP passed; no provider credentials, actual internet message or inbox receipt used. |
| Hosted TLS/ingress/staging/CI/CD | **NOT VERIFIED** | No public infrastructure, DNS changes, approved-host rollout, exact-SHA hosted workflow execution or protection/approval verification. |
| Hosted offsite recovery/production RTO/RPO/rollback | **NOT VERIFIED** | No independent-host restore, key-escrow receipt, accepted predecessor or production transition. |
| Hosted AI/external datasource semantics and long soak | **NOT VERIFIED** | Fake/mock AI; Prometheus functional, all external provider queries not exercised. |

The unchanged [formal gate](../infra/scripts/verify_release.py) returns **exit 1 /
BLOCKED** for [machine-readable criteria](evidence/m123/release-result.json):
container security, hosted AI, hosted CI/CD and production environment remain unmet.
No exception was self-approved. No advisory suppression, ignored-unfixed setting,
severity threshold change, plugin removal or unsigned-plugin bypass was used.
No experimental/older upstream image was promoted.

Review the [formal assessment](security-remediation-12-3.md),
[complete normalized inventory](security-remediation-12-3-inventory.json),
[executed verification and commands](security-remediation-12-3-verification.md),
[source manifest](evidence/m123/source-manifest.json),
[evidence checksums](evidence/m123/evidence-sha256.json),
[release checklist](release-checklist.md) and
[concrete hosted/SMTP procedures](hosted-staging-acceptance.md).

Security/infrastructure owners must obtain a fully acceptable source-matched
artifact and repeat security and operational acceptance. SRE/identity/repository
owners must complete separately authorized hosted mail, TLS, CI/CD, recovery and
rollback evidence. Release authority must review the final exact source/artifact
manifest before any promotion. No commit, push, development data reset, volume
removal, public deployment, infrastructure purchase, DNS change, production
credential access or actual internet email was performed in 12.3.
