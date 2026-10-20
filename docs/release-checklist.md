# Release checklist — Security Remediation 12.5

Date: 2026-10-20 Asia/Dubai. Baseline `932f75f`.
**FAIL / production BLOCKED.** Remediation changes remain uncommitted.

| Requirement | Result | Next action / owner |
| --- | --- | --- |
|Source baseline, immutable digests and fresh inventory |PASS |Retain exact final source/artifact IDs and evidence / release engineer |
|Selected Grafana passes security policy |FAIL |61 HIGH remain; obtain accepted clean supported image / vendor + security |
|Experimental candidate passes policy |FAIL |2 Tempo HIGH remain; keep candidate unpromoted / security |
|Tempo supported module/advisory resolution |NOT VERIFIED |Vendor/scanner-endorsed fix or mapping correction; no local ignore/VEX/exception / vendor + security |
|Custom compiled reachability analysis |PASS, limited scope |Affected server packages absent; preserve graph without treating it as policy waiver / application security |
|Monitoring, plugins, auth, queries and network isolation |PASS locally |13 native IDs and all transition checks pass; verify intended hosted configuration / SRE |
|Restart, same-version upgrade and rollback |PASS locally |Owned synthetic data only; no13→12 production downgrade / SRE |
|Backend/frontend/build/migration regressions |PASS |662 backend,53 frontend; types/lint/build/head/check / QA |
|Browsers |PASS on rerun |18 final cases; retain initial API-connection failure and trace; root cause NV / QA |
|Runtime Python/npm audits |PASS |Repeat audits for final accepted artifact / security |
|Development lint-chain nodes |FAIL |Five HIGH nodes; obtain compatible maintained fix / frontend maintainer |
|Fail-closed DB fixture guards and cleanup |PASS locally |Owned tmpfs DB, nine isolation tests, no public fixture leaks; CI service wiring updated / QA + DBA |
|Current original rows/storage preserved |PASS |All 12 pre-existing limiter rows, other 15 whole tables/revision and private-storage bytes/metadata preserved / DBA |
|Final 12.5 whole-database equality |FAIL |One new limiter row12→13; writer NOT VERIFIED. Preserve it and retain earlier PASS plus final FAIL / DBA + maintainer |
|Historical eleven additions attributed |NOT VERIFIED |Preserve rows; seek authorized existing audit evidence; do not infer actor / DBA + maintainer |
|Historical DB equality12.4 |FAIL |A new successful comparison cannot undo historical observed additions / release authority |
|Original historical manifest retained |PASS |69 entries unchanged; four normalized hashes match disclosed audit / evidence custodian |
|Original bytes for four normalized logs |PASS for recovery |All four recovered streams match the original manifest; append-only gzip archives under m125. Full custody timestamps remain NV / evidence custodian |
|Local bounded load and encrypted recovery |PASS |341 requests / 0 failures;24 originals/documents;45.985s app recovery; corruption/nonempty rejection / SRE |
|Security/release/deployment safeguards retained |PASS |Strict scans/formal gate still reject; CI changes only test DB configuration / release engineer |
|Real SMTP/provider and inbox |NOT VERIFIED |Approved provider/recipient procedure and real delivery receipts / identity + mail owner |
|Hosted DNS/public TLS/ingress/staging |NOT VERIFIED |Separate infrastructure authorization, approved host and actual acceptance receipts / infrastructure |
|Hosted exact-SHA CI/protections/reviewer/SSH |NOT VERIFIED |Observe actual workflow and repository/host controls / repository administrator |
|Offsite restore/key escrow/production RTO-RPO |NOT VERIFIED |Independent-host rehearsal and measured loss/duration / SRE + key custodian |
|Production rollback to accepted predecessor |NOT VERIFIED |Accepted previous artifact and schema compatibility review / release authority |
|Publisher signature/vendor parity/AMD64 |NOT VERIFIED |Independent identity validation and final-platform tests / supply-chain owner |
|External providers/hosted AI/soak |NOT VERIFIED |Approved services and intended-host acceptance / AI + SRE |
|Production release approval |FAIL |BLOCKED; no security exception approved / release authority |

[Assessment](security-remediation-12-5.md),
[exact verification and hosted procedures](security-remediation-12-5-verification.md),
[database investigation](database-integrity-investigation.md), and
[standing hosted runbook](hosted-staging-acceptance.md) define evidence scope.
No row/volume reset, commit/push, DNS change, server purchase, live provider mail
or public deployment is authorized by this checklist. Never use local functional
passes to override failing scans or unexecuted hosted requirements.
