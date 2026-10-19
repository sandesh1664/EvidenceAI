# Release checklist — Security Remediation 12.4

Date: **2026-10-20, Asia/Dubai**. **FAIL / production BLOCKED.**
Baseline `1ffa5ea`; changes uncommitted. See [acceptance](release-acceptance.md),
[assessment](security-remediation-12-4.md) and
[reproducible verification](security-remediation-12-4-verification.md).

| Requirement | Result | Next action / owner |
| --- | --- | --- |
| Latest baseline/origin/digest reviewed | PASS | Preserve final source and image/config/archive hashes / release engineer |
| Selected image passes policy | FAIL |61 HIGH remain in selected13.2.4; do not promote / security |
| Maintained candidate passes policy | FAIL |12.4.13 upstream 5 HIGH; patched candidate 2 HIGH / security + Grafana maintainer |
| Three kin-openapi fixes | PASS locally | Library0.149.0 fixes three CVEs in unapproved candidate; keep full scan evidence / build engineer |
| Two Tempo findings | FAIL policy | Vendor product fixes/source ancestry exist, direct Go tag invalid; obtain supported resolution/advisory mapping correction, no local exemption / vendor + security |
| Native plugin trust and operations | PASS locally |13 native core IDs; dashboard/auth/query/isolation pass; external semantics NV / SRE |
| Same-version persistence/restart/upgrade/rollback | PASS locally | Owned12.4 data only; no13.x-to12.x production downgrade inferred / SRE |
| Backend/frontend/browser/build/migrations | PASS |653/53/18 tests;26 guards; types/lint/build/head/check / QA |
| Runtime audits | PASS | Python and runtime npm clean; repeat final artifact audit / security |
| Dev lint-chain advisory | FAIL | Five high nodes; track supported upstream fix / frontend maintainer |
| Local load/encrypted restore | PASS |352 requests, no failures;20 originals/docs recovered;45.961s restored-app recovery / SRE |
| Original rows/private storage preserved | PASS | All originals intact; storage bytes/metadata and revision match / maintainer |
| Entire development DB equal to baseline | FAIL |8 limiter rows +3 intents added, source NOT VERIFIED. Investigate with authorization; do not delete to force comparison / maintainer |
| Existing scanner/release/workflow gates unchanged | PASS | Strict candidate/support gates and formal release reject; no suppression / release engineer |
| Real SMTP/provider/inbox | NOT VERIFIED | Approved recipient procedure and redacted delivery receipts / mail + identity owner |
| Hosted DNS/public TLS/ingress/staging | NOT VERIFIED | Separate infrastructure authorization and observed host evidence / infrastructure |
| Hosted exact-SHA CI/branch protections/reviewer/SSH | NOT VERIFIED | Verify actual policies, workflow success and approved host marker / repository administrator |
| Offsite restore/key escrow/production RTO-RPO | NOT VERIFIED | Independent host rehearsal and measured loss/duration / SRE |
| Production rollback to accepted predecessor | NOT VERIFIED | Accepted previous digests and schema compatibility review / release engineer |
| Publisher signatures/vendor parity/AMD64/reproducibility | NOT VERIFIED | Resolve vendor source availability and independently validate final artifacts / supply-chain owner |
| Hosted AI/external datasource semantics/soak | NOT VERIFIED | Approved services/data and intended-host acceptance / AI + SRE |
| Release authority approval | FAIL | BLOCKED; no acceptable monitoring artifact or exception approved / release authority |

Concrete remaining procedures are in [hosted acceptance](hosted-staging-acceptance.md).
No commit/push, DNS mutation, infrastructure purchase, public deployment,
production credential access, real email or destructive data cleanup is authorized
by this checklist. Functional passes never override failed scans or unverified
hosted requirements. The observed DB additions remain preserved and visible.
