# Production release acceptance — Security Remediation 12.5

**FAIL / NO-GO — production release BLOCKED.** Date: 2026-10-20 Asia/Dubai.
Baseline `932f75f`, initially clean; this remediation remains uncommitted.
No Grafana candidate was selected or promoted.

| Criterion | Result | Evidence / precise scope |
| --- | --- | --- |
|Selected Grafana security policy |FAIL |Unchanged 13.2.4 digest retains 61 HIGH/0 CRITICAL; seven other selected runtime images freshly pass HIGH/CRITICAL/secret scans. |
|Maintained upstream candidate |FAIL |Official 12.4.13 remains 5 HIGH/0 CRITICAL. |
|New custom candidate |FAIL |Rebuilt local `evidenceai-grafana:kin-m125`, OCI index `sha256:514e1e31662cf191943b983103d2fe74f9933ff0a358bc722d58213ead3bfb1b`, remains 2 HIGH/0 CRITICAL/0 secrets. Unselected. |
|Tempo source reachability assessment |PASS, limited scope |Actual custom OSS compile graph includes four protobuf packages; neither affected frontend nor S3 backend package is compiled. This does not waive scanner results or prove vendor-binary parity. |
|Supported, scanner-accepted Tempo remediation |NOT VERIFIED |Vendor Tempo product fixes exist; v2 historical and v3 fresh module-tag probes fail canonical path validation. No authoritative mapping correction or supported clean Grafana artifact. |
|Publisher signature/vendor patched-source parity/AMD64 |NOT VERIFIED |Registry digest/source checksum verified; independent publisher signature, full patched-source parity and AMD64 acceptance unavailable. |
|Monitoring/plugin/auth/Prometheus/isolation |PASS locally |13 native plugin trust checks, provisioning, admin auth, anonymous denial, real two-target query, no published Grafana port and monitoring-route denials. |
|Same-version restart/upgrade/rollback |PASS locally |Synthetic dashboard state/version retained through upstream 12.4→custom→upstream transitions. Production rollback remains NOT VERIFIED. |
|Backend/frontend/types/lint/build |PASS |662 backend,53 frontend; TypeScript/lint/production build; existing deployment tests retained. |
|Browser E2E |PASS on complete rerun |18 final cases, six per engine; initial17/18 and connection failure retained, cause NOT VERIFIED. Assertions/timeouts unchanged. |
|Migration/package consistency/runtime audits |PASS |Disposable DB head91e2b6d8c410, check/no drift, pip check,44-dependency Python audit and runtime npm clean. |
|Development npm dependency audit |FAIL |Five HIGH lint-chain nodes retained. |
|Final 12.5 whole-database equality |FAIL |Earlier PASS superseded by a new limiter row12→13. Loopback-login bucket/action matches; writer NOT VERIFIED. All 12 original limiter rows, other 15 whole tables, revision/storage and historical additions preserved; no deletions. |
|Historical12.4 additions attributed |NOT VERIFIED |Eight limiter and three intent rows remain in evidenceai.public; route/loopback correlations and timestamps do not identify the writer. Historical DB equality remains FAIL. |
|Test DB isolation/cleanup |PASS locally |Dedicated owned tmpfs DB; explicit fail-closed URL guards; scoped raw SQL/ORM; negative guards and nine new tests; zero leaked schemas/public fixture rows; owned containers removed. |
|Historical evidence preservation |PASS for retention/review |Original69-entry manifest and whole m124 directory unchanged from 932f75f; four normalized hashes match disclosed audit. Three intentionally updated current documents differ separately; all 69 original contents are recoverable from the new verified archive. |
|Original historical byte recovery |PASS |All four raw streams recovered from retained runtime files/old immutable image; append-only gzip archives match original manifest SHA256. Normalized historical paths still differ; complete custody timestamps remain NOT VERIFIED. |
|Local load/encrypted recovery |PASS |341 requests/zero failures, p95 26 ms/p99 56 ms;24 documents/originals restored;45.985s restored-app operation; tamper/nonempty-target rejection. |
|Security/release/deployment gate preservation |PASS |Scanner/gate/production pin unchanged; expected scans and formal gate reject; dirty-tree packaging refuses. CI changes only disposable DB wiring; actionlint passes. |
|Real SMTP/public TLS/ingress/hosted staging |NOT VERIFIED |Only local private-CA transport/staging executed; no real provider/inbox or public-host evidence. |
|Hosted exact-SHA CI/CD/protections/SSH |NOT VERIFIED |No hosted final-SHA workflow or deployment executed. |
|Offsite key escrow/restore, production RTO-RPO/rollback |NOT VERIFIED |Same-host synthetic drill only; no accepted production predecessor or independent-host receipt. |
|Hosted AI/external datasource semantics/soak |NOT VERIFIED |Mock/fake providers and Prometheus locally; external/provider and long-duration acceptance unexecuted. |

The unchanged formal gate returns **exit 1 / BLOCKED**. Original-row/storage preservation PASS does not erase either whole-database
equality FAIL or identify a writer. The earlier passing comparison is retained
alongside the final one-row delta. The manifest and normalized paths are retained; recovered originals are separately
archived and verified, without rewriting historical hashes. Functional monitoring
success does not clear image policy. No exception was approved.

[Complete assessment](security-remediation-12-5.md) ·
[Full inventory](security-remediation-12-5-inventory.json) ·
[Executed commands and hosted procedures](security-remediation-12-5-verification.md) ·
[Database investigation](database-integrity-investigation.md) ·
[Evidence checksums](evidence/m125/evidence-sha256.json) ·
[Checklist](release-checklist.md).

Withhold production approval until accepted clean artifacts, historical data and
evidence review, and required hosted acceptance are complete. No commit, push,
DNS change, purchase, public deployment, development reset or record deletion was
performed. Nothing in this assessment grants those authorizations.
