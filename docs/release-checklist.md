# Release checklist — Security Remediation 12.6

2026-10-20 Asia/Dubai; inspected HEAD `cc22799`. **FAIL / production BLOCKED.**
No candidate promoted; new work uncommitted. Completed isolation fix/checkpoint
accepted; no repeated remediation or gate relaxation.

| Requirement | Result | Next action / owner |
| --- | --- | --- |
| Current baseline and new immutable inventory |PASS for recorded scope |All eight selected runtime images freshly scanned; retain final SHA/platform/artifact IDs and rescan rebuilt final artifacts / release engineer |
| Selected Grafana image gate |FAIL |61 HIGH remain; obtain accepted clean supported whole image / vendor + security |
| Maintained upstream / custom experiment |FAIL |5 /2 HIGH respectively; keep unselected / security |
| Both Tempo advisories identified |PASS |21728 query-limit allocation and28377 SSE-C config exposure; exact IDs/versions in12.6 / security |
| Supported accepted module/advisory resolution |NOT VERIFIED |Vendor canonical module/backport or authoritative scanner correction; no ignores/VEX/version rewriting / vendor + scanner maintainers |
| New speculative rebuild |Not required |No changed supported input; reopen only upon verifiable new vendor fix/artifact / security |
| Managed replacement |NOT VERIFIED |Evaluate vendor Cloud migration/PDC, identity/residency/private access/plugins/security assurance; no purchase or account connection / architecture + procurement |
| Monitoring/plugins/auth/queries/private network |PASS locally |13 trusted plugin identities,2-target query and denial checks; intended host remains pending / SRE |
| Restart/same-version rollback |PASS locally |Retain synthetic dashboard checks; no13→12 production downgrade / SRE |
| Backend/frontend/build/migrations |PASS |662 backend,53 frontend, types/lint/build/head/check / QA |
| Browser acceptance |PASS final |18/18; retain initial missing-browser failure and installation receipt / QA |
| Runtime Python/npm audits / pip consistency |PASS |44 Python dependencies/0 vulnerabilities, runtime npm clean; final artifact audits still required / security |
| Development npm audit |FAIL |Five HIGH lint-chain nodes; supported compatible remediation / frontend maintainer |
| Test guards/imports/owned cleanup |PASS locally |15 refusal cases,3 runner tests, isolated public/scratch checks and container absence / QA + DBA |
| Current controlled DB/storage preservation |PASS |Committed checkpoint plus12.6 all16 table/revision/storage equality; retain private snapshots outside Git / DBA |
| Historical equality/attribution |FAIL historically / NOT VERIFIED attribution |Preserve all historical additions and failed comparisons; no inferred actor / DBA + maintainer |
| Historical evidence retention |PASS |Old tracked evidence unchanged; append-onlym126 receipts/raw archives / evidence custodian |
| Full historical custody |NOT VERIFIED |Retain original-byte recovery proof without claiming acquisition timestamps / evidence custodian |
| Local recovery/load |PASS in recorded scopes |12.6 small restore;12.5 load/full-app recovery retained, not production certification / SRE |
| Hosted overlay configuration |PASS only for config |Seven checks; never started, no default deployment behavior changed / infrastructure |
| Hosting/domain/firewall/public TLS/renewal |NOT VERIFIED |Approved isolated host and authorized DNS/ACME receipts / infrastructure + domain owner |
| Reverse proxy/workers/private storage on host |NOT VERIFIED |Execute actual hosted HTTPS flows and access controls / SRE + QA |
| Real SMTP/provider/inbox |NOT VERIFIED |Approved465 service/mailboxes, provider AND inbox receipts, sender DNS checks / mail + identity owner |
| Exact-SHA CI/protections/environment approval |NOT VERIFIED |Final committed SHA, successful hosted checks, reviewers/SSH identity/concurrency / repository administrator |
| Hosted monitoring/alerts |NOT VERIFIED |Private access, dashboard/query parity and delivered operator alert / SRE |
| Encrypted offsite backup/key escrow/restore |NOT VERIFIED |Independent host/account, fresh target, actual app/worker validation and measured RTO/RPO / SRE + key custodian |
| Accepted predecessor/schema-compatible rollback |NOT VERIFIED |Reviewed accepted artifacts and guarded host drill; no DB downgrade / release authority |
| Publisher signature/vendor parity/intended platform |NOT VERIFIED |Independent identity validation and complete final-platform acceptance / supply-chain owner |
| Hosted AI/external providers/soak |NOT VERIFIED |Separately authorized services/budget and real semantic/soak receipts / AI + SRE |
| Strict release gate and packaging refusal |PASS for protection |Gate exit1/BLOCKED; dirty-tree packaging exit1 / release engineer |
| Production approval |FAIL |Withhold until every applicable criterion passes / release authority |

Use [12.6 verification](security-remediation-12-6-verification.md),
[database acceptance](database-isolation-acceptance.md), and the
[hosted execution plan](hosted-staging-execution-plan.md). Hosted actions require
separate authorization and passing gates. Nothing here authorizes purchases,
DNS mutations, secrets in chat, commits/pushes, public deployment, volume resets,
development record edits or vulnerability suppression.
