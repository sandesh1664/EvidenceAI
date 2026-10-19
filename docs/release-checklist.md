# Release checklist — Security Remediation 12.2

**Production promotion: FAIL / BLOCKED.** Baseline `0f58dcf`; 12.2 changes remain
uncommitted. See [formal acceptance](release-acceptance.md),
[12.2 assessment](security-remediation-12-2.md) and
[exact commands/evidence](security-remediation-12-2-verification.md).

| Requirement | Result | Remaining action / accountable role |
| --- | --- | --- |
| Exact baseline and reviewable local source | PASS | Review recorded source hashes; intentionally commit only in a separate authorized step / maintainer |
| Existing development rows, schema and Compose preserved | PASS | Sixteen table snapshots and revision compared privately; never reset volumes / maintainer |
| Runtime images have no high/critical findings | FAIL | Selected Grafana retains 61 high, 0 critical; seven other images have zero. Obtain supported fixes for core and all affected plugins / security + infrastructure |
| Experimental core security rebuild | FAIL | Build and local functionality pass; 56 high remain, vendor patched-source parity unverified. Not selected / Grafana maintainer |
| Official OpenTSDB update removes findings | FAIL | 13.0.5 complete-image candidate retains all four plugin findings and 61 overall. Not selected / Grafana maintainer |
| Python and runtime npm audits | PASS | 44 Python dependencies and runtime npm clean at scan time; repeat final candidate scans / security |
| Development lint dependency advisory | FAIL | Five high nodes from braces advisory; compatible latest 3.0.3 still affected. Track upstream without framework downgrade / frontend maintainer |
| Enumeration-safe registration and identity controls | PASS | Generic responses, proof expiry/single use/replay/binding, existing credentials preserved, CSRF and rate limits pass locally / identity maintainer |
| Real-provider SMTP / inbox / sender authentication | NOT VERIFIED | Authorized controlled-recipient procedure and redacted receipts required / identity + mail administrator |
| Backend/frontend/types/lint/build | PASS | 653 backend, 53 frontend, lint/types and final production build; retain corrected build-lock collision evidence / QA |
| Chromium / Firefox / WebKit | PASS | 18 local browser cases, six per engine / QA |
| Grafana operational configuration | PASS | Selected image and core experiment: health, admin auth, anonymous/signup denied, provisioned dashboard, datasource health, two live query targets, internal network, no host port / SRE |
| Local synthetic staging / bounded performance / encrypted recovery | PASS | Disposable private-CA fixture only; see measured results in verification / SRE |
| Real provider AI behavior / representative long soak | NOT VERIFIED | Approved provider/data evaluation and intended-host load, capacity and recovery objectives / AI + SRE |
| Production public TLS, DNS, host/firewall and storage | NOT VERIFIED | Explicit infrastructure/deployment authorization and hosted checklist evidence / infrastructure |
| Offsite restore, key escrow, production RTO/RPO | NOT VERIFIED | Independent-host restore and measured loss/duration / SRE |
| Controlled current-schema rollback to accepted predecessor | NOT VERIFIED | Reviewed accepted prior digests and schema compatibility required; do not reuse M11 rollback as proof / release engineer |
| Local workflow / migration / release guards | PASS | Actionlint, Alembic current/check, deployment regressions; supporting scan and dirty-source packaging refuse unsafe release / release engineer |
| Hosted exact-SHA CI, approval, SSH and repository protection | NOT VERIFIED | Verify actual branch rules, environment reviewers/no self-approval, host key and operator marker / repository administrator |
| Whole-image reproducibility / intended AMD64 | NOT VERIFIED | Local candidates are ARM64; independent artifact rebuild and target-architecture acceptance / release engineer |
| Release gates pass and authorized release approval exists | FAIL | Strict supporting-image and formal release gates exit 1; no exception granted / release authority |

Use [hosted staging and SMTP acceptance](hosted-staging-acceptance.md) for the
explicit pending DNS/HTTPS/routing/database/workers/storage/mail/monitoring/
backup/rollback checklist. No public deployment, real email, DNS changes, data
reset, exception approval, commit or push is authorized by this checklist.
