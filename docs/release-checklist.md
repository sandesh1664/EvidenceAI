# Release checklist — Security Remediation 12.3

Date: **2026-10-20, Asia/Dubai**. **Production: FAIL / BLOCKED.**
Baseline `5d4571d`; 12.3 changes uncommitted. See
[acceptance](release-acceptance.md), [assessment](security-remediation-12-3.md),
[inventory](security-remediation-12-3-inventory.json) and
[exact verification](security-remediation-12-3-verification.md).

| Requirement | Result | Remaining action / accountable role |
| --- | --- | --- |
| Baseline and reviewable source provenance | PASS | Review source hashes and decide a separate intentional commit / maintainer |
| Original data/migrations/dev Compose preserved | PASS | Sixteen table snapshots and schema revision match; never reset volumes / maintainer |
| No prohibited selected runtime findings | FAIL | Grafana retains 61 high/0 critical; seven other images zero. Obtain actual component fixes / security + infrastructure |
| Supported upstream artifact accepted | FAIL | Four alternatives fail with 61/15/10/5 high; no downgrade or promotion authorized / Grafana maintainer |
| Core custom build patch/provenance/operations | PASS, limited scope | Zero-fuzz actual patching, resolved modules, traceable binary and local operations verified; vendor-equivalent source and upstream full regressions NOT VERIFIED / build engineer |
| Core/combined image passes security | FAIL | 56 high remain; no further reduction versus 12.2 experiment. Not selected / security |
| Latest official Cloud Monitoring plugin resolves findings | FAIL | 12.6.3 has all six original highs; signed plugin-only 61, combined 56. Not selected / vendor + Grafana maintainer |
| Python/runtime npm audits | PASS | Repeat final artifact scans when candidate changes / security |
| Development lint-chain advisory | FAIL | Five high nodes; no framework downgrade or ignored finding / frontend maintainer |
| Backend/frontend/types/lint/build | PASS | 653/53 tests, types/lint/build, 26 deployment guard tests / QA |
| Three browser engines | PASS | Six cases each Chromium/Firefox/WebKit / QA |
| Identity/privacy/CSRF/rate limits | PASS locally | Preserve generic enrollment and single-use expiring browser-bound proof / identity maintainer |
| Grafana monitoring/plugin signatures/isolation | PASS locally | Selected, core and combined tested; external provider semantics remain NOT VERIFIED / SRE |
| Grafana stop/restart/core upgrade/rollback persistence | PASS locally | Synthetic same-version owned data only; do not infer general downgrade safety / SRE |
| Local bounded performance and encrypted restored operation | PASS | 334 requests/zero failures; 23 documents/originals restored; 45.690s restored-app recovery / SRE |
| Real SMTP delivery/inbox/sender authentication | NOT VERIFIED | Authorized controlled-recipient procedure and redacted receipts / identity + mail administrator |
| Hosted public TLS/DNS/ingress/staging | NOT VERIFIED | Explicit infrastructure/deployment authorization and observed checklist evidence / infrastructure |
| Hosted exact-SHA CI/approval/SSH/repository protections | NOT VERIFIED | Verify actual branch rules, reviewers/no self-approval, host key and accepted marker / repository administrator |
| Offsite restore/key escrow/production RTO/RPO | NOT VERIFIED | Independent host, actual loss/duration and recovery receipt / SRE |
| Hosted rollout/rollback to accepted predecessor | NOT VERIFIED | Reviewed digests and schema compatibility before change; keep DB/originals / release engineer |
| Patched vendor-source equivalence | NOT VERIFIED | Resolve unavailable embedded vendor SHA; labels alone are not attestation / vendor + supply-chain owner |
| Independent whole-image reproducibility/AMD64 | NOT VERIFIED | Freeze/rebuild artifacts and test intended architecture / release engineer |
| Hosted model quality/external datasource queries/long soak | NOT VERIFIED | Approved services/credentials/datasets and intended-host measurements / AI + SRE |
| Local security gates remain fail-closed | PASS | Supporting scans and formal release gate reject all prohibited findings; packaging rejects dirty source / release engineer |
| Authorized final release approval | FAIL | BLOCKED; no exceptions granted and no acceptable promoted candidate / release authority |

[Hosted/SMTP procedures](hosted-staging-acceptance.md) provide concrete pending
steps. None grants authorization to purchase infrastructure, mutate DNS, deploy
publicly, access production credentials, send real email, reset data, approve
exceptions, commit or push. Local functional success never overrides a failed
security gate or missing hosted evidence.
