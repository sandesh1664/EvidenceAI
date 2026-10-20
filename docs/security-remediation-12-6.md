# Security Remediation 12.6 — Grafana/Tempo decision

**Production release: FAIL / BLOCKED.** 2026-10-20 Asia/Dubai. Inspected current
HEAD `cc22799` (clean at start), following `b0e9782`. No candidate promoted,
security exception/suppression added, development record/storage modified,
volume reset, commit, push, purchase, DNS change or public deployment performed.
Completed database-isolation remediation is accepted; safe local verification
and hosted execution preparation are complete, security closure is not.

## Exact vulnerabilities and decision

Both HIGH findings are attached to the compiled runtime executable
`usr/share/grafana/bin/grafana`, Go module `github.com/grafana/tempo`, installed
`v1.5.1-0.20260427112133-525d1bab07e0`. They are **not merely dependencies of the
Go compiler or build tools**: module build information is present in the shipped
Grafana executable. The vulnerable server packages are a separate reachability
question. Evidence: [fresh inventory](evidence/m126/monitoring-inventory.json),
[binary inspection](evidence/m126/binary-inspection.json).

| Advisory | Affected code / consequence | Vendor fixed product versions | Status |
| --- | --- | --- | --- |
| CVE-2026-21728 / GHSA-p4r4-xvrq-gvmc; HIGH7.5 |Tempo `modules/frontend/config.go`: unrestricted query result limit can exhaust memory; vendor fix650eb1985a0776789c8564122990f588a742356f changes default maximum to262144 |2.8.4,2.9.2,2.10.2 |FAIL: still reported in complete candidate scan |
| CVE-2026-28377 / GHSA-ffqx-q65f-36jf; HIGH7.5 |Tempo `tempodb/backend/s3`: SSE-C customer encryption key exposed by `/status/config`; vendor fixbb8ca663db34a0980c9758b40d918fda3b4dbec3 uses secret-valued config and extracts the value for S3 use |2.10.3 |FAIL: still reported in complete candidate scan |

Official [query advisory](https://grafana.com/security/security-advisories/cve-2026-21728/)
and [S3 advisory](https://grafana.com/security/security-advisories/cve-2026-28377/),
with fresh [GHSA21728](evidence/m126/21728.json) and
[GHSA28377](evidence/m126/28377.json). The advisory's semver ranges classify the
v1 pseudo-version below the v2 fixed releases. Product versions cannot simply be
substituted for a supported Go module inside Grafana. No standalone Tempo server
is configured in production Compose; upgrading an unrelated Tempo server would
not change this Grafana binary or these image findings.

Both vendor fix commits are ancestors of525d1bab07e0 according to newly fetched
GitHub comparisons. The exact pinned source was fetched separately and inspected
for the repaired limit/secret fields. This supports source-fix presence, not a
claim that every vulnerable operation is safe in every runtime. The retained
custom OSS binary's actual4269-package compile graph, read back from the immutable
image, includes only `pkg/tempopb` plus common/resource/trace protobuf packages.
Neither frontend nor S3 backend is in that graph. The Go build metadata still
embeds the module version, and fresh image scanning still fails. Source ancestry,
source lines and absent compiled packages do not establish vendor-patched binary
parity, erase findings, or authorize an ignore/VEX/version rewrite.

## Immutable artifacts and fresh scans

ARM64 full-image scans include vulnerability and secret scanning, all severities,
no ignore/VEX and unchanged HIGH/CRITICAL/secret rejection. Trivy **0.76.0**,
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
New empty-cache DB UpdatedAt **2026-10-20T13:14:22.737606427Z**, DownloadedAt
**2026-10-20T13:34:41.153238753Z**. This is newer published intelligence than12.5.

| Artifact | Exact immutable identity | HIGH / CRITICAL / secrets | Decision |
| --- | --- | --- | --- |
| Selected upstream Grafana13.2.4 |`grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f` |61 /0 /0 |FAIL; production pin unchanged |
| Maintained upstream12.4.13 |`grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` |5 /0 /0 |FAIL; unselected |
| Retained custom12.4.13 kin patch |Local OCI index `sha256:514e1e31662cf191943b983103d2fe74f9933ff0a358bc722d58213ead3bfb1b`, tag `evidenceai-grafana:kin-m125` |2 /0 /0 |FAIL; unselected, no vendor endorsement |

Registry tag metadata matches both official digests. Custom identity is local,
not proof of registry publication or publisher signing. Binary SHA256
`151b7fd5ac677a1a44c0d179767a567e2a3fb0bd1807a3ccfbca5cc483a2b20f`;
archive/report hashes, architecture and rootfs identities are in the inventory.
The other seven selected runtime images were also freshly scanned with the same
updated DB: all have zero HIGH/CRITICAL/secrets. They were not rebuilt and do not
represent exact-final-SHA hosted artifacts; see [runtime inventory](evidence/m126/runtime-inventory.json). AMD64,
independent publisher signature, custom vendor-source parity remain NOT VERIFIED.

## Supported remediation and replacement options

Fresh official releases list Grafana13.2.4,13.1.8,13.0.11 and12.4.13 as current
branch patches. The [vendor policy](https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/)
lists12.4 patch support through2027-05-24 and supported13.0/13.1/13.2 branches.
Although13.3 is scheduled for today, its exact v13.3.0 release endpoint returned404
and latest remained13.2.4 at verification. No future image was assumed available.
13.0.11/13.1.8 were identified, not freshly built/scanned or declared acceptable.

Tempo latest metadata is3.1.0 (2026-09-29); its
[recommendation policy](https://grafana.com/docs/tempo/latest/set-up-for-tracing/setup-tempo/recommended-versions/)
recommends the current3.x major, lists2.10 maintained through2027-04-26 and2.9
through2026-12-31, and2.8 EOL. Its version table lags3.1; latest-release metadata
and3.1 notes establish that release's existence.2.8.4 is an advisory fix, not a
supported deployment choice today.2.9.2 fixes only the first listed advisory;
maintained2.10 requires at least2.10.3 for both. None is automatically a valid
unversioned Tempo Go-module upgrade in this Grafana source.

| Option | Next executable acceptance / external dependency | Result |
| --- | --- | --- |
| Vendor-maintained self-hosted Grafana |Obtain an actual maintained whole-image release whose compiled dependencies/plugins pass fresh scans; verify publisher, intended architecture, provisioning/auth/queries/plugins/restart/rollback. New source/archive/compiler identities trigger a disposable build; never build mutable main. |Current evaluated images FAIL; no clean supported artifact identified |
| Vendor-compatible patch or advisory correction |Vendor supplies a canonical supported Tempo module reference/backport and Grafana patched-source parity, or authoritative advisory/scanner mapping correction. Rebuild only then in disposable BuildKit, preserve complete assets, prove binary module/hash and complete fresh scans. |NOT VERIFIED; requires vendor + scanner maintainers |
| Managed Grafana replacement |[Vendor migration](https://grafana.com/docs/grafana/latest/administration/migration-guide/manually-migrate-to-grafana-cloud/) supports resource migration; [PDC](https://grafana.com/docs/grafana-cloud/observe-and-act/connect-externally-hosted/private-data-source-connect/) supports private datasource access. Review identity/RBAC, residency/retention, egress, plugin parity, connector security and supply-chain evidence; import copies of dashboards/datasources, test actual private queries/alerts and reversible cutover. |Feasible evaluation path; procurement/account access, vendor security evidence and compatibility NOT VERIFIED; no purchase/connection made |

Removing Tempo/plugins or Grafana outright would remove required monitoring and
is not an accepted replacement. Do not publish Prometheus to make managed access
work. Managed service compliance needs explicit vendor security evidence and
reviewed gates; this task does not relax the existing image criterion to fit it.
Never reuse a13.x Grafana SQLite volume in a12.x downgrade.

No new candidate build was justified: release/source/fix inputs are unchanged,
12.5 already built the custom candidate in disposable BuildKit, and v2.10.3/v3.1.0
probes failed canonical major-version path validation. Repeating those builds
cannot supply vendor support or clear today's unchanged findings. Retained
[recipe](../infra/monitoring/grafana-rebuild/125.Dockerfile),
[build/probe evidence](security-remediation-12-5-verification.md#executed-build-and-image-scans)
and fresh compiled-image inspection are distinguished from a new build. This
avoids speculative rebuilds; no unsupported module substitution was attempted.

Vendor escalation draft (not sent): provide both official digests/local candidate
identity, ARM64 binary hash, installed pseudo-version, both GHSA/CVEs, pinned
source/ancestry and protobuf-only graph, fresh scanner/DB timestamps and reports.
Request the supported Grafana artifact or canonical module/backport and advisory
range correction; require a full scanner-accepted result without local suppression.
Reopen a build only on a changed, verifiable vendor artifact or supported fix.

## Local acceptance and remaining release conditions

**PASS locally:**662 backend26.32s;53 frontend; types/lint/build; migration head
and no drift; pip check;44-dependency Python audit with zero vulnerabilities; runtime npm audit; three runner regressions;15/15 guard
refusals; final18 browsers85.321s wrapper time. Initial browser run failed solely
because old temporary browser executables were missing; new pinned installation
and unchanged final tests pass. Full npm audit remains FAIL: five HIGH development
lint-chain nodes. The initial failure and final receipts are both retained.

Monitoring drill PASS in193.531s: actual Grafana admin auth, anonymous401/signup
refusal, dashboard/datasource provisioning,13 trusted native plugin identities,
Prometheus datasource health and actual two-target up query; no Grafana host port,
internal monitoring network, public monitoring routes denied. Restart→same-version
upstream12.4/custom transition→rollback preserves synthetic dashboard state/version
and repeats checks. No production downgrade/rollback is certified. One synthetic
document/original encrypted and restored with pgvector0.8.7/revision91e2b6d8c410;
nonempty-target/tampered-ciphertext rejection passes. Completed12.5 load/full-app
recovery was not repeated;12.6's small recovery is not new RTO/RPO certification.

**Database PASS:** committed controlled result accepted and new16-table/storage
comparison passes. Dedicated tmpfs DBs/owned local staging cleaned up and absence
independently confirmed. **Historical attribution NOT VERIFIED**, with prior12.4/
12.5 failed comparisons and original historical evidence unchanged. See
[isolation acceptance](database-isolation-acceptance.md).

**Hosted NOT VERIFIED:** approved host/architecture, domain/DNS/public ACME and
renewal, intended ingress, SMTP/provider/inbox, exact-SHA CI/protections/reviewer,
private hosted monitoring/alerts, independent offsite encrypted restore/key escrow,
RTO/RPO, accepted predecessor/rollback, hosted AI/external datasource semantics and
soak. [Execution plan](hosted-staging-execution-plan.md) is prepared; hosted overlay
passes configuration checks only and has not started. Local Playwright does not
target hosted ingress.

Formal gate remains **exit1 / BLOCKED**; dirty-source packaging refuses. Functional
passes do not override failed scans, development audit findings or unverified
hosted requirements. Strict security/release code and production image selection
are unchanged. Recommendation: **withhold production release**.

## Changed files and evidence

- Four requested reports: this assessment, [verification](security-remediation-12-6-verification.md),
  [database acceptance](database-isolation-acceptance.md), [hosted plan](hosted-staging-execution-plan.md).
- Current [release acceptance](release-acceptance.md) and [checklist](release-checklist.md).
- `infra/compose.hosted-staging.yml`: prepared public-TLS staging overlay only.
- New append-only `docs/evidence/m126/`: command harnesses/receipts, fresh vendor
  records, image inventory, backend XML, guards/cleanup/data preservation,
  monitoring result, hosted Compose validation and hashed log archive.

No application, migration, test assertion, database guard, isolated runner,
production Compose, scanner, CI workflow, deployment or release-gate logic changed.
