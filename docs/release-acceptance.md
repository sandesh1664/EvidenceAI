# Production release acceptance — Security Remediation 12.4

**FAIL / NO-GO — production release BLOCKED.** Date: **2026-10-20, Asia/Dubai**.
Baseline `1ffa5ea18ca4eb73d72263efc7ac6978376f1080`, initially clean. Changes are
uncommitted; no experimental image was selected or promoted.

| Criterion | Result | Evidence / scope |
| --- | --- | --- |
| Selected Grafana security policy | FAIL | Unchanged 13.2.4 digest retains 61 HIGH/0 CRITICAL; seven other runtime images freshly scan clean at high/critical/secret policy. |
| Maintained upstream five-CVE candidate | FAIL | Official 12.4.13 digest `sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` still5 HIGH/0 CRITICAL. |
| Three kin-openapi CVEs remediated locally | PASS | Patched12.4.13 candidate removes CVE-2026-100352/100353/100354; no new high/critical finding. |
| Patched candidate passes complete security policy | FAIL | Two Tempo HIGH findings remain; candidate unapproved/unselected. |
| Official origin and maintained release | PASS, limited scope | Official registry tag/release and immutable digest match;12.4 supported through 2027-05-24. Independent publisher-signature verification NOT VERIFIED. |
| Custom build compatibility/provenance | PASS, limited scope | Correct source workspace builds; zero-fuzz patch, locked module checksums, pinned compiler, binary provenance and retained frontend/native assets. Full vendor patched-source parity NOT VERIFIED. |
| Tempo runtime applicability / supported scanner-endorsed resolution | NOT VERIFIED | Source commit descends from both vendor fix commits; direct fixed-tag Go resolution fails major-version path validation. No false-positive exemption; scanner policy still FAIL. |
| Native plugin/dashboard/auth/Prometheus operations | PASS locally | All 13 expected native core IDs/trust, provisioning, admin auth, anonymous denial, real two-target query, internal network/no published port and private-CA ingress checks. |
| Local same-version restart/upgrade/rollback | PASS | Original synthetic dashboard state/version and auth/provisioning/queries preserved across12.4 upstream -> patched -> upstream on owned data. No 13.x downgrade attempted. |
| Backend/frontend/types/lint/build/browsers | PASS | 653 backend,53 frontend,26 deployment guards; types/lint/build;18 browser cases, six per engine. |
| Runtime dependency audits | PASS | Python44 dependencies and runtime npm clean. |
| Development npm audit | FAIL | Five high lint-chain nodes unresolved. |
| Local bounded performance / encrypted recovery | PASS |352 requests, zero failures, p95 33ms/p99 91ms;20 documents/originals restored; session/login/download/pending work;45.961s restored-app recovery. |
| Original development records and private storage | PASS | All original rows preserved;14 whole tables/revision identical; original4 limiter rows separately hash-matched; recursive storage bytes/metadata unchanged. |
| Entire development database unchanged | FAIL |8 limiter rows and3 registration intents added; attribution NOT VERIFIED, no matches to owned staging/browser UUID identities. Preserved, not erased to force a pass. |
| Local release-gate preservation | PASS | Scanner/gate/workflow/production pin unchanged; strict scans and formal gate still reject. Packaging refuses dirty source. |
| Hosted SMTP/TLS/ingress/staging/CI/CD | NOT VERIFIED | No real internet delivery, public host, exact-SHA workflow or repository/approval/SSH execution. |
| Hosted offsite recovery/production RTO-RPO/accepted rollback | NOT VERIFIED | Same-host synthetic recovery only; no independent host/key-escrow or accepted predecessor receipt. |
| Vendor-build equivalence/AMD64/whole-image reproducibility | NOT VERIFIED | Vendor binary commit6367d911... unavailable through official API; custom public tag sourcebbc0a79...; local ARM64 only. |
| External datasource semantics/hosted AI/long soak | NOT VERIFIED | Native identity and Prometheus operations exercised; external provider behavior not verified. |

The unchanged formal gate returns **exit 1/BLOCKED**. The unexplained development
DB additions are a separate failed assessment condition requiring attribution and
review. Do not represent original-row preservation as whole-database equality.
No advisory suppression, severity reduction, unsigned-plugin allowance, version
metadata forgery or security exception was used. No older/custom image was put
into production Compose.

[Complete report](security-remediation-12-4.md) ·
[Five-CVE/full inventory](security-remediation-12-4-inventory.json) ·
[Exact executed verification](security-remediation-12-4-verification.md) ·
[Source manifest](evidence/m124/source-manifest.json) ·
[Evidence checksums](evidence/m124/evidence-sha256.json) ·
[Release checklist](release-checklist.md) ·
[Pending hosted procedures](hosted-staging-acceptance.md).

Recommendation: withhold production approval until Tempo findings receive an
accepted supported resolution, final artifacts pass policy, observed development
state changes are reviewed and hosted acceptance is completed. Source/artifact
review and any commit or promotion require separate deliberate authorization.
No commit, push, DNS change, purchase, public deployment, production credential
access, development reset or volume deletion occurred.
