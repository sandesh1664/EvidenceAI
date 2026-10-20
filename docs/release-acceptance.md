# Production release acceptance — Security Remediation 12.6

**FAIL / NO-GO — production release BLOCKED.** 2026-10-20 Asia/Dubai.
Inspected current HEAD `cc22799`, clean at start. New12.6 work is uncommitted;
no image promoted or selected production pin changed.

| Criterion | Result | Evidence / precise scope |
| --- | --- | --- |
| Selected Grafana security |FAIL |Fresh61 HIGH/0 CRITICAL/0 secrets on unchanged13.2.4 digestdbbc38ea…; other seven selected images freshly pass strict policy |
| Maintained upstream12.4.13 |FAIL |Fresh5 HIGH/0 CRITICAL/0 secrets, digest41bbc1b5… |
| Retained custom candidate |FAIL |Fresh2 HIGH/0 CRITICAL/0 secrets, local OCI514e1e31…; unselected |
| Exact Tempo investigation |PASS for identification |CVE-2026-21728/GHSA-p4r4-xvrq-gvmc and CVE-2026-28377/GHSA-ffqx-q65f-36jf in grafana runtime binary, modulev1.5.1-0.20260427112133-525d1bab07e0 |
| Vendor/scanner-accepted remediation |NOT VERIFIED |Vendor source fixes present; affected server packages absent from custom compile graph; module-version findings retained. No supported clean artifact identified; no redundant speculative build |
| Publisher signature/vendor parity/AMD64 |NOT VERIFIED |Local compiled metadata and official tag digest checks do not establish these |
| Monitoring/auth/plugins/Prometheus/isolation |PASS locally |13 expected plugin identities, provisioning, admin/anonymous/signup checks,2-target query, internal network/no ports/private-route denials |
| Restart/same-version transition/rollback |PASS locally |Synthetic dashboard state retained across upstream12.4→custom→upstream; production downgrade/rollback NOT VERIFIED |
| Backend/frontend/types/lint/build |PASS |662 backend26.32s;53 frontend; types/lint/build exit0 |
| Browsers |PASS on final run |18/18 across3 engines; initial missing-/tmp-binaries failure retained, pinned install then unchanged rerun85.321s |
| Migration/package/runtime npm |PASS locally |head91e2b6d8c410/no drift; pip check;44-dependency Python audit0 vulnerabilities; runtime npm audit0 findings |
| Development npm audit |FAIL |Five HIGH lint-chain nodes; no unreviewed downgrade applied |
| Current controlled database equality |PASS |Committedcc22799 checkpoint accepted; new12.6 comparison also16/16 hashes/counts/revision and storage content/metadata equal |
| Fail-closed test entry points/cleanup |PASS locally |15/15 missing/development/production refusals;3 runner regressions; all owned DBs public-empty/schema-clean; independent container absence |
| Historical12.4/12.5 equality observations |FAIL historically |Earlier additions/12.5 final limiter delta preserved unchanged; a new PASS does not erase prior observed changes |
| Historical write attribution/custody |NOT VERIFIED |No actor inferred; historical investigation/evidence retained |
| Historical evidence retention |PASS |Prior tracked evidence unchanged fromcc22799; new evidence onlym126; recovered originals/old manifests preserved |
| Local recovery |PASS, limited |12.6 one document/original encrypted/restored, pgvector0.8.7; tampered/nonempty targets rejected.12.5 load/full-app recovery retained, not repeated or represented as hosted certification |
| Prepared hosted overlay |PASS for configuration |Seven assertions; explicit public-TLS staging overlay never started; local deploy.py defaults unchanged |
| Real host/DNS/TLS/ingress/SMTP/inbox |NOT VERIFIED |No public deployment, issuance, DNS change or mail sent |
| Exact-SHA hosted CI/protections/reviewer |NOT VERIFIED |No commit/push/dispatch; no actual final-SHA approval receipt |
| Independent offsite recovery/key escrow/RTO-RPO |NOT VERIFIED |No independent host/account restore or production objective certification |
| Accepted production predecessor/rollback |NOT VERIFIED |Local same-version fixture transitions are insufficient |
| Hosted AI/external datasource semantics/soak |NOT VERIFIED |Local mock/fake providers/Prometheus only |
| Security/release gate preservation |PASS |Strict image policy unchanged; formal gate rejects with exit1/BLOCKED; dirty-tree packaging refuses |

[12.6 assessment](security-remediation-12-6.md) includes full digests, advisory
identities and supported remediation/replacement choices. [Verification](security-remediation-12-6-verification.md),
[database acceptance](database-isolation-acceptance.md),
[hosted execution plan](hosted-staging-execution-plan.md),
[fresh image inventory](evidence/m126/monitoring-inventory.json), and
[formal result](evidence/m126/release-result.json) define scope. Previous12.5
reports/evidence remain historical records.

Withhold release until clean supported artifacts and dependency audit resolution,
required historical review and every applicable hosted receipt are accepted.
No waiver, record deletion, volume reset, commit, push, purchase, DNS change or
public deployment is authorized by this acceptance record.
