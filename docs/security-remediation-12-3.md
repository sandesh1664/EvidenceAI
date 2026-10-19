# Security remediation 12.3 — production reassessment

**Formal decision: FAIL / NO-GO — production release BLOCKED.** Assessment date:
**2026-10-20, Asia/Dubai** (execution timestamps retained in UTC).
Baseline `5d4571d87b0ab866f0942c4a52bdd0cad89e264c` was clean on inspection.
12.3 changes remain uncommitted. No application feature, database migration,
development Compose, production image pin or release threshold was changed.
No development-data deletion, volume reset, public deployment, DNS mutation, infrastructure
purchase, production credential access, commit, push or exception approval occurred.

## Selected image and before/after

Selected Grafana remains **13.2.4**, immutable official reference
`grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f`.
Its live OCI digest, saved configuration digest and layer diff IDs match the fresh
scan archive. All local scans/builds/tests are **Linux ARM64** in Docker on macOS;
intended AMD64 acceptance remains NOT VERIFIED.

| Scope | 12.2 high / critical | 12.3 high / critical | Release implication |
| --- | ---: | ---: | --- |
| Selected Grafana | 61 / 0 | **61 / 0** | FAIL, unchanged selection |
| Custom core experiment | 56 / 0 | **56 / 0** | Five selected-image occurrences removed; no incremental count reduction over 12.2; unselected |
| Seven other selected runtime images | 0 / 0 | **0 / 0** | Fresh scans pass high/critical/secret policy |

The selected Grafana has **254 vulnerability occurrences** across all severities:
61 high, 175 medium, 13 low and 5 unknown; zero critical and zero secret findings.
The 61 blocking occurrences map to **12 distinct advisory IDs**. Core and combined
experiments have 56 high, 173 medium, 13 low and 5 unknown, zero critical/secrets.
Counts are inventory occurrences, not proven exploitable paths. All findings,
including lower severities, are normalized in
[the complete inventory](security-remediation-12-3-inventory.json).

Fresh intelligence: pinned Trivy 0.76.0,
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
The DB was downloaded again during 12.3; published update timestamp remains
`2026-10-19T19:08:34.442427859Z`, downloaded for the supporting baseline at
`2026-10-19T20:21:19.558070722Z`. Rechecking did not yield newer published DB data.
Report timestamps, archive/config/live identities, platform and full scan hashes
are recorded individually. Full raw JSON reports and image archives remain under
ignored `infra/runtime/m123/`; sanitized evidence and its hashes are retained.

## Complete blocking-finding classification

| Vendor advisory | Package | Installed | Reported fixed | Occurrences |
| --- | --- | --- | --- | ---: |
| [CVE-2026-100349](https://github.com/getkin/kin-openapi/security/advisories/GHSA-74vm-87hj-r66f) | `github.com/getkin/kin-openapi` | v0.144.0 | 0.146.0 | 1 |
| [CVE-2026-100351](https://github.com/getkin/kin-openapi/security/advisories/GHSA-23vg-4cjm-66q5) | `github.com/getkin/kin-openapi` | v0.144.0 | 0.147.0 | 1 |
| [CVE-2026-100352](https://github.com/getkin/kin-openapi/security/advisories/GHSA-rj39-cv6w-8wv7) | `github.com/getkin/kin-openapi` | v0.144.0 | 0.148.0 | 1 |
| [CVE-2026-100353](https://github.com/getkin/kin-openapi/security/advisories/GHSA-vrcc-3ch7-hppw) | `github.com/getkin/kin-openapi` | v0.144.0 | 0.149.0 | 1 |
| [CVE-2026-100354](https://github.com/getkin/kin-openapi/security/advisories/GHSA-g8cf-rcjf-c8cf) | `github.com/getkin/kin-openapi` | v0.144.0 | 0.149.0 | 1 |
| [CVE-2026-21728](https://grafana.com/security/security-advisories/cve-2026-21728) | `github.com/grafana/tempo` | v1.5.1-0.20260910130453-bcfe9f230c1d | 2.8.4, 2.9.2, 2.10.2 | 1 |
| [CVE-2026-28377](https://grafana.com/security/security-advisories/cve-2026-28377) | `github.com/grafana/tempo` | v1.5.1-0.20260910130453-bcfe9f230c1d | 2.10.3 | 1 |
| [CVE-2026-78667](https://pkg.go.dev/vuln/GO-2026-6609) | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | `golang.org/x/net` | v0.58.0, v0.59.0 | 0.60.0 | 13 |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |
| [CVE-2026-84304](https://github.com/grpc/grpc-go/security/advisories/GHSA-vp52-pcj8-j9qc) | `google.golang.org/grpc` | v1.83.0 | 1.83.1 | 1 |
| [CVE-2026-84445](https://github.com/grpc/grpc-go/security/advisories/GHSA-2v4p-qf9q-27wj) | `google.golang.org/grpc` | v1.83.0 | 1.82.2, 1.83.2, 1.84.0-dev.0.20260825144003-d5a41119e0e3, 1.85.0-dev.0.20260825072537-93e31b48545e | 1 |
| [CVE-2026-97031](https://pkg.go.dev/vuln/GO-2026-6607) | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |

Root causes: five kin-openapi occurrences in the server binary; 39 vulnerable Go
stdlib occurrences plus 13 x/net occurrences across thirteen plugin executables;
two gRPC occurrences in Cloud Monitoring; two Tempo-module occurrences in the
Tempo plugin. The Go stdlib/x/net roots account for **52 of 61** occurrences and
require rebuilding/replacing the actual plugin executables, not installing a new
compiler beside them. Prometheus is provisioned and executed in acceptance.
Other datasource reachability varies with configuration; their presence is not
waived. Tempo server advisory applicability to an embedded library is not proven
or disproven by absence of a demonstrated route. No false-positive classification
or exception is issued.

The JSON includes advisory, scanner severity/source, vendor severity when supplied,
package/versions, binary/target, layer, OS/language ecosystem, runtime functionality,
vendor URL, fix availability and verification status for every occurrence. Repeated
package/advisory occurrences retain their individual binary targets. All twelve
blocking advisory records were retrieved afresh from the relevant maintainer,
Go vulnerability database or Grafana site; see
[vendor records](evidence/m123/vendor-advisories.json). Some maintainer severities
(e.g. medium for CVE-2026-100349) differ from Trivy's high classification. Both are
recorded; the release gate continues using the unsuppressed scanner classification.

## Supported upstream comparison

Current [vendor release metadata](https://github.com/grafana/grafana/releases/latest)
returned 13.2.4 as latest during execution. [Grafana's support policy](https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/)
lists maintained 12.4, 13.0, 13.1 and 13.2 lines; a scheduled newer release is not
treated as an available tested image. Official GitHub release and Docker Hub
metadata were freshly retrieved, with immutable digests preserved before pulls.
The official [security advisory index](https://grafana.com/security/security-advisories/)
was reviewed alongside package-maintainer advisories. A supported version alone
is not a clean vulnerability result.

| Evaluated image | Exact scanned reference | High | Critical | Policy / selection |
| --- | --- | ---: | ---: | --- |
| core | `evidenceai-grafana:experimental-m123` | 56 | 0 | FAIL / not selected |
| plugins | `evidenceai-grafana:plugins-m123` | 61 | 0 | FAIL / not selected |
| combined | `evidenceai-grafana:combined-m123` | 56 | 0 | FAIL / not selected |
| upstream-distroless | `grafana/grafana@sha256:ae3d3add290adbe6a88412229f5d76fd7bb82743050881698642d3d62f277e35` | 61 | 0 | FAIL / not selected |
| upstream-131 | `grafana/grafana@sha256:1a8e58976a6cd349d1ffdd27a14b92053816c7c60e6b7e157013e9bf0b9cec5f` | 15 | 0 | FAIL / not selected |
| upstream-124 | `grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` | 5 | 0 | FAIL / not selected |
| upstream-130 | `grafana/grafana@sha256:2abd2114bb65e4d6f0614206b7c882c1e7c6a992827ba08396aa5afc23ca07f5` | 10 | 0 | FAIL / not selected |

Upstream names map to 13.2.4-distroless, 13.1.8, 12.4.13 and 13.0.11 respectively;
`core` is the custom 13.2.4 server, `plugins` the official 12.6.3 Cloud Monitoring
overlay, and `combined` both changes. Every complete-image scan and strict
HIGH/CRITICAL/secret policy result is retained. No floating tag is used in final
production definitions. Published tags are discovery inputs only.

The maintained 12.4.13 image has the lowest observed count (five), but still has
three kin-openapi and two Tempo findings. 13.1.8 has 15; 13.0.11 has ten;
distroless 13.2.4 has 61. None meets security acceptance. These rejected upstream
alternatives were **not** substituted into production or pointed at existing
Grafana data. Their full dashboard/plugin/authentication/provisioning/upgrade
compatibility remains **NOT VERIFIED**; a lower count is not permission to
downgrade the current Grafana database. Distroless also needs separate validation
of the existing shell/wget health-check contract. No plugins were removed, and no
alternative architecture was used to evade scanning. Prefer an upstream artifact
once it actually meets both security and operational acceptance.

## Actual custom build and provenance improvements

The existing module patch is unchanged. The recipe now requires both zero-fuzz
`patch --dry-run` and **actual** `patch` success. Build output records checks and
patching of both `go.mod` and `go.sum`, without fuzz/offset fallback. Read-only Go
module resolution asserts kin-openapi **0.149.0** and jsonschema **6.0.3** before
compilation. The disposable build succeeded in **32.579 seconds** using existing
isolated compiler/module caches and pinned Go **1.27.2**.

Source archive SHA-256 is
`fdd57503b5f591e951ea3dff80ab53a41487c3373dc89370da2e36e7bf752f52`;
patch SHA-256 is
`560a737d2ff94f9b9e2d929f19f5e406d13be2287a7b2da2614710b001dec634`.
The annotated v13.2.4 tag resolves to commit
`af4a33e3786594ad72f72d97e6744010330c2977`. GitHub reports that commit verified;
the annotated tag object's verification is unsigned. No independent signing-key
or Docker publisher-signature verification is claimed. The binary embeds the
actual source commit and an explicit experimental branch. Build flags retain OSS,
CGO, trimpath, read-only modules and bounded compilation; compiler, module sums,
flags and executable SHA-256 are in
[actual build provenance](evidence/m123/core-build-provenance.txt), copied from the
built image and checked against the running-image executable bytes.

The rebuilt core's **11,864 regular frontend files and 686 bundled-plugin files**
match the pinned vendor image byte-for-byte:
[asset parity](evidence/m123/asset-parity.json). Frontend assets and original
signed plugin versions were retained, not regenerated from mismatched frontend
sources. This establishes distribution-asset identity, not complete vendor
server/security parity. The server binary changes and its full scan removes the
five kin-openapi advisories; all 56 plugin highs remain. That reduction was also
achieved in 12.2, so 12.3 adds reproducibility/provenance and operational evidence,
not a further five reductions against the prior experiment.

The distributed image reports patched server SHA
`0e79aef9d91abf3bdadae9af15763029072fb45b`; the refreshed official commit lookup
still returns HTTP 422 / no commit found. [Response](evidence/m123/vendor-patched-source-response.txt).
Our source/patch/binary chain is evidenced, but equivalence with that unavailable
patched vendor source and complete upstream security regression remain **NOT VERIFIED**.
Local build metadata and BuildKit attestations are not represented as a vendor
signature or independent reproducible-build attestation. Custom images remain
unapproved and unselected.

## Official signed-plugin remediation attempt

The current [catalog snapshot](evidence/m123/plugin-catalog.json) lists Cloud
Monitoring (`stackdriver`) 12.6.3, compatible with Grafana >=12.3.0-0. Its official
ARM64 ZIP was downloaded and checksum-verified:
`5ac8bf252f415b5709c3e9f315919e1bdf152b70ee5b69c83bd9f1a1d41db0bd`.
A separate recipe overlays the complete official signed plugin. It preserves the
signature manifest, all other datasource capabilities and authentication settings;
no unsigned-plugin allowance was introduced. Both plugin-only and combined
core/plugin images were built and scanned in full. The actual image executable
matches the verified ZIP and differs from the older executable, proving this was
not an accidentally stale overlay. Nevertheless **all six Cloud Monitoring high
findings remain**, with old stdlib, x/net and gRPC versions still embedded.
See [binary identity evidence](evidence/m123/stackdriver-binary-parity.json).
Plugin-only stays at 61 high; combined stays at 56. No further security reduction
is claimed. AMD64 download checksums are pinned but AMD64 execution is unverified.
OpenTSDB 13.0.5 remains catalog latest; its earlier nonremediating experiment is
historical evidence, not a newly claimed clean scan.

## Functional and operational acceptance

The upgraded local harness verifies all thirteen expected bundled plugins are
present with valid signatures, records versions/server commit, checks authenticated
admin access and anonymous denial, disabled signup, provisioned dashboard,
datasource health and a real Grafana-proxied Prometheus `up` query (two healthy
targets). It inspects Docker health, one internal monitoring network and no
published Grafana port. Internal protected API/worker metrics and public denial
of monitoring routes are exercised through a verified private-CA HTTPS reverse
proxy. HTTP redirect, HSTS, Secure cookies, CSRF and private storage checks remain.
No public TLS certificate or internet ingress is claimed.

The selected image was stopped gracefully (exit 0, no OOM), restarted, upgraded
to the rebuilt core, then rolled back to the selected image on the **same owned
Grafana database/bind directory**. A separately created synthetic dashboard
retained title/version through every transition; admin authentication, signatures,
provisioning and real datasource queries passed after each transition. Server
commit evidence confirms the actual image change and return. This is a local
same-version Grafana transition, not production rollout authorization or general
cross-version downgrade compatibility. [Transition evidence](evidence/m123/staging.json).

The second signed-plugin/combined-image fixture also **passed** startup/health,
admin authentication/anonymous denial, provisioning, all thirteen valid signatures
(including Cloud Monitoring 12.6.3), private isolation, actual Prometheus queries
and basic encrypted recovery. [Evidence](evidence/m123/staging-signed.json). Live Cloud Monitoring provider
queries, every external datasource's semantic correctness and long operational
soak remain **NOT VERIFIED** without their approved services/credentials. Valid
plugin signatures and a healthy Prometheus query do not establish those results.

## Regression, recovery and hosted status

Backend **653 passed**; frontend **53 passed**; lint, TypeScript, production build
and **18 browser tests** (six each Chromium/Firefox/WebKit) passed. Alembic current
is `91e2b6d8c410`, check reports no new operations, pip check passes. Python audit:
44 dependencies/zero findings; runtime npm zero; development npm retains five
high lint-chain nodes from the braces advisory. Actionlint and 26 deployment guard
tests pass. Exact commands/exits/logs are in
[verification](security-remediation-12-3-verification.md).

Bounded local load: **334 requests, zero failures, 11.351 requests/s; p50 8ms,
p95 31ms, p99 87ms**, unchanged five-user/30-second thresholds and offline
providers. Queue drain and no-failed-job criteria pass. Encrypted backup restored
23 documents/originals and checksums, revision/pgvector 0.8.7, existing session,
fresh login, downloads and pending work. Backup 0.057s, restore 0.092s; restored-app
recovery **45.690s**, zero lost acknowledged synthetic writes with writers
quiesced. Tampered ciphertext/nonempty target were rejected; no OOM/exit137.
Same-host tiny synthetic tests do not establish production capacity or RTO/RPO.

Real SMTP inbox delivery, hosted TLS/ingress/staging, hosted exact-SHA CI/CD,
repository protection/approval execution, offsite restore/key escrow, intended
AMD64 and independent whole-image reproducibility remain **NOT VERIFIED**.
[Concrete pending operator procedures](hosted-staging-acceptance.md) cover
approved recipients and verified TLS, public certificate/routing checks, reviewed
digest-only deployment, exact-SHA CI/approval evidence, independent encrypted
restore and controlled rollback. No real external email or public deployment was
performed. Existing identity protections were preserved; no product rewrite was
needed. Production stays blocked until prohibited findings and hosted acceptance
are resolved by authorized owners.

## Files and formal decision

Changed: core experimental Dockerfile and README; monitoring checker; smoke
harness; hosted acceptance procedure; release acceptance/checklist. Added:
`stackdriver.Dockerfile`, `infra/testing/grafana_fixture_state.py`, the three
requested 12.3 reports and sanitized reproducible evidence under `docs/evidence/m123/`.
Existing application code, tests, migrations, production/development Compose,
CI/CD workflows and release/scanner thresholds are preserved. Implementation hashes
and evidence checksums accompany the report. All sixteen original development tables have identical before/after counts and
ordered full-row hashes; revision is unchanged. Private row data is not published;
[aggregate preservation evidence](evidence/m123/data-preservation.json) records PASS.

**PASS**: stated local regression/monitoring/recovery controls.
**FAIL**: every evaluated Grafana image's strict security policy and production
release. **NOT VERIFIED**: patched vendor-source parity, hosted and architecture
criteria above. No exceptions approved. The unchanged formal gate returns
**exit 1 / BLOCKED**; functional success never overrides that result.
