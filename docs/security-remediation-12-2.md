# Security remediation 12.2 — formal assessment

**Production release: BLOCKED (FAIL).** No security exception is approved.
Inspection began with a clean checkout of
`0f58dcf0b0a5777acd48da738bd1aa460a9bc0ab`. This assessment covers uncommitted
12.2 infrastructure verification and documentation changes. Tests/scans ran on
2026-10-19 UTC (2026-10-20 locally at completion), macOS ARM64 / Docker Linux ARM64.
No completed application features, development Compose, application schema,
registration logic or selected production images were changed. No commit, push,
public deployment, DNS mutation, purchase or development volume reset occurred.

## Decision and before/after

| Candidate scope | High | Critical | Distinct high/critical advisories | Selection |
| --- | ---: | ---: | ---: | --- |
| 12.1 selected runtime baseline | 61 | 0 | 12 | Prior inventory |
| 12.2 freshly scanned selected runtime | 61 | 0 | 12 | Unchanged production Compose |
| Experimental core rebuild | 56 | 0 | 7 | Not selected; incomplete fix and source parity unverified |
| Official OpenTSDB 13.0.5 overlay experiment | 61 | 0 | 12 | Not selected; no finding reduction |

Seven selected images (API/worker, web, backup, proxy, database, Prometheus,
exporter) each have zero high, critical and secret findings. Grafana alone has
61 high, zero critical and zero secret findings. These are package/advisory
occurrences, not 61 distinct CVEs. No new experimental image is represented as a
production remediation. The selected runtime count is unchanged. The core
experiment actually removes five occurrences, with no new high/critical findings;
that partial result does not qualify it for release.

Fresh Trivy 0.76.0 uses pinned scanner
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
Database metadata and all selected/experimental image IDs, configuration digests,
layer diff IDs, archive SHA-256s, scan SHA-256s, timestamps and every finding are in
[the 12.2 inventory](security-remediation-12-2-inventory.json). Scans match saved
archive configurations and live local layers; Docker Desktop OCI index IDs are
recorded separately from image configuration IDs. Full reports/archives remain
under ignored `infra/runtime/m122/`. No severity reduction, ignored-unfixed flag,
removed plugin, unsigned-plugin allowance or scanner exclusion was introduced.

## Investigation of every Grafana finding

Source image remains
`grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f`.
Its reported server is 13.2.4, patched commit
`0e79aef9d91abf3bdadae9af15763029072fb45b`. Five findings are in
`usr/share/grafana/bin/grafana`; 56 are in thirteen independent Go datasource
executables under `usr/share/grafana/data/plugins-bundled/`. Replacing the main
binary or installing a new Go toolchain does not repair the existing plugin
executables. The normalized JSON retains each full target and layer.

| Advisory | Affected package | Installed versions | Scanner fixed versions | Occurrences |
| --- | --- | --- | --- | ---: |
| CVE-2026-100349 | `github.com/getkin/kin-openapi` | v0.144.0 | 0.146.0 | 1 |
| CVE-2026-100351 | `github.com/getkin/kin-openapi` | v0.144.0 | 0.147.0 | 1 |
| CVE-2026-100352 | `github.com/getkin/kin-openapi` | v0.144.0 | 0.148.0 | 1 |
| CVE-2026-100353 | `github.com/getkin/kin-openapi` | v0.144.0 | 0.149.0 | 1 |
| CVE-2026-100354 | `github.com/getkin/kin-openapi` | v0.144.0 | 0.149.0 | 1 |
| CVE-2026-21728 | `github.com/grafana/tempo` | v1.5.1-0.20260910130453-bcfe9f230c1d | 2.8.4, 2.9.2, 2.10.2 | 1 |
| CVE-2026-28377 | `github.com/grafana/tempo` | v1.5.1-0.20260910130453-bcfe9f230c1d | 2.10.3 | 1 |
| CVE-2026-78669 | `golang.org/x/net` | v0.58.0, v0.59.0 | 0.60.0 | 13 |
| CVE-2026-84304 | `google.golang.org/grpc` | v1.83.0 | 1.83.1 | 1 |
| CVE-2026-84445 | `google.golang.org/grpc` | v1.83.0 | 1.82.2, 1.83.2, 1.84.0-dev.0.20260825144003-d5a41119e0e3, 1.85.0-dev.0.20260825072537-93e31b48545e | 1 |
| CVE-2026-78667 | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |
| CVE-2026-78669 | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |
| CVE-2026-97031 | `stdlib` | v1.26.6, v1.26.7, v1.27.1 | 1.26.9, 1.27.2 | 13 |

The kin-openapi findings cover request/response/schema validation denial of
service and path-decoding authentication bypass. Go/http2 and gRPC findings cover
HTTP/2, Range, RPC and TLS denial of service. Tempo findings concern large-query
DoS and status-config disclosure of an S3 encryption key. These are scanner
advisory descriptions, not demonstrated application exploits. Bundling a Tempo
library does not establish that the Tempo server's config endpoint is reachable
through Grafana. Conversely, nonprovisioned datasources and private networking do
not establish safety or authorize a waiver. The provisioned Prometheus binary
was actually executed by acceptance tests and retains four high findings.

| Bundled datasource | Installed plugin version | High occurrences | Published source commit / build manifest |
| --- | --- | ---: | --- |
| elasticsearch | 12.9.2 | 4 | [`a4b9ec92456c`](https://raw.githubusercontent.com/grafana/grafana-elasticsearch-datasource/a4b9ec92456c705a5b3ff81c538c19293a5ee88e/go.mod) |
| grafana-postgresql-datasource | 13.0.4 | 4 | [`4d167c25053d`](https://raw.githubusercontent.com/grafana/grafana-postgresql-datasource/4d167c25053dc0444178451abf8a3f171e9e4471/go.mod) |
| grafana-pyroscope-datasource | 13.0.7 | 4 | [`fcc51a6c9f04`](https://raw.githubusercontent.com/grafana/grafana-pyroscope-datasource/fcc51a6c9f04f446e7d6ff0a7b3a288e3ca8c52e/go.mod) |
| influxdb | 13.1.7 | 4 | [`030eec102c9c`](https://raw.githubusercontent.com/grafana/grafana-influxdb-datasource/030eec102c9cfab314b73c87a2599ba8bb80bc40/go.mod) |
| jaeger | 13.0.5 | 4 | [`f2e2b7c6e0c2`](https://raw.githubusercontent.com/grafana/grafana-jaeger-datasource/f2e2b7c6e0c2504cac5d30141e4a2f7b4990fe63/go.mod) |
| loki | 13.2.2 | 4 | [`6d076df3d695`](https://raw.githubusercontent.com/grafana/grafana-loki-datasource/6d076df3d695f5fda342fbbad1f52547b55a96e2/go.mod) |
| mssql | 13.0.7 | 4 | [`e0ad61ae0451`](https://raw.githubusercontent.com/grafana/grafana-mssql-datasource/e0ad61ae045182f7869ba35afd1c48069b6add43/go.mod) |
| mysql | 13.1.4 | 4 | [`453ec30a1245`](https://raw.githubusercontent.com/grafana/grafana-mysql-datasource/453ec30a1245e539974d869a62f1c09bb5b9dfa9/go.mod) |
| opentsdb | 13.0.4 | 4 | [`2e3dc74ef71f`](https://raw.githubusercontent.com/grafana/grafana-opentsdb-datasource/2e3dc74ef71fe4b57b24170bd2c35612bc69ac25/go.mod) |
| prometheus | 13.2.3 | 4 | [`6d21418acde6`](https://raw.githubusercontent.com/grafana/grafana-prometheus-datasource/6d21418acde6ce31c9f7a6418a88758842a881bb/go.mod) |
| stackdriver | 12.6.2 | 6 | [`cb0dadba1d04`](https://raw.githubusercontent.com/grafana/grafana-cloudmonitoring-datasource/cb0dadba1d04a4697a344d134d92dc520411bb7c/go.mod) |
| tempo | 13.2.4 | 6 | [`cdacb742bae9`](https://raw.githubusercontent.com/grafana/grafana-tempo-datasource/cdacb742bae90fbf62c48c5cca0eacdc08fd2acd/go.mod) |
| zipkin | 12.4.9 | 4 | [`4f1d9629b22e`](https://raw.githubusercontent.com/grafana/grafana-zipkin-datasource/4f1d9629b22e2bae0c887e20d82360786b4f34b6/go.mod) |

[Source requirements](evidence/m122/grafana-source-requirements.json) show Go
1.26.6, 1.26.7 or 1.27.1 requirements and the relevant module dependencies at each
catalog release commit. Actual binary versions from scanning take precedence
over source declarations: some source manifests already declare newer gRPC while
the distributed binary still embeds 1.83.0. Patched rebuilds require Go 1.26.9 or
1.27.2, x/net 0.60.0, gRPC 1.83.2, compatible fixed Tempo module usage and
kin-openapi 0.149.0. A blind Tempo major-version substitution is not validated.
Plugin frontend artifacts, executable name/architecture, SDK protocol, plugin
manifest/signature and Grafana compatibility must also be preserved. Independent
plugin source builds require their own Go modules and upstream tests; Grafana's
root source build does not build these extracted plugins.

The official [Grafana support policy](https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/)
identifies maintained 12.4.x, 13.0.x, 13.1.x and 13.2.x branches at the UTC scan
date; 13.3.x is scheduled for October 20. The published latest-release endpoint
still resolves to [13.2.4](https://github.com/grafana/grafana/releases/tag/v13.2.4).
A scheduled release is not an available, tested image. `grafana/grafana:13.2.5`
was checked and not found. Older maintained branches are not established as clean
or compatible candidates here; downgrade/migration and security acceptance remain
NOT VERIFIED. No complete compatible supported fix was verified in this run.

The [official catalog evidence](evidence/m122/grafana-catalog-curl.json) records
latest plugin releases, source commits, compatibility and download checksums for
all thirteen plugins. Twelve installed versions are the latest catalog versions;
OpenTSDB has a compatible newer 13.0.5. It was downloaded, SHA-256 verified and
built as a complete-image experiment. All four OpenTSDB findings remain in its
binary, leaving 61 overall. It was not selected. Initial `trivy fs` discovery found
zero language files; that result was rejected as coverage evidence and replaced
by the complete image scan, which detected the affected executable.

## Custom core rebuild and actual runtime verification

The interrupted 12.1 attempt did not prove compilation incompatibility. The
12.2 recipe pins v13.2.4 source by SHA-256, applies a reviewable module/checksum
patch, builds with pinned Go 1.27.2 and reusable dedicated caches, and overlays
only the main executable onto the pinned image. A bounded 600-second attempt
completed successfully in **322.33 seconds**. The resulting full scan has
**56 high / 0 critical / 0 secrets**, removing the five kin-openapi occurrences.

The experimental core image passed real local startup, container health, admin
authentication, anonymous dashboard denial (401), disabled signup, provisioned
`evidenceai-operations` dashboard, datasource health and a Grafana-proxied `up`
query returning both API and worker exporter at 1. Docker inspection verified one
internal monitoring network and no published Grafana port. See
[actual rebuilt-image fixture](evidence/m122/staging-core.json).

It remains unselected: 56 high findings independently fail policy, and the source
tag commit `af4a33e...` does not establish parity with the patched distribution.
The official GitHub commit API returned HTTP 422 / no commit found for the
embedded patched SHA; [response](evidence/m122/grafana-patched-source-response.txt).
This is a source-availability/provenance gap, not proof of a malicious image or
proof the tag lacks any particular fix. Full vendor regression/security parity
and all datasource fixes are NOT VERIFIED. Recipes and limitations are retained
in [the experimental rebuild directory](../infra/monitoring/grafana-rebuild/README.md).
Production Compose and strict scan/release scripts continue selecting/gating the
original pinned image. No experimental image is deployed publicly.

## Identity and SMTP

Registration-enumeration controls remain intact. The 653-test backend suite and
18 browser cases preserve generic 202 responses, case-normalized duplicate
protection, no usable preverification account/session, independent 256-bit email
and browser proofs stored only as hashes, expiration (default 1800 seconds),
locked single use, replay/browser binding, CSRF and per-IP/per-recipient limits.
Existing password, display name, disabled state and sessions survive repeated
verified requests. Unit SMTP checks require certificate and hostname validation;
exceptions return the same public response without credential/token/provider
logging. Timing comparison used 20 paired samples/class; medians were 30.501ms
(existing) and 30.590ms (new), difference 0.089ms under the unchanged 20ms bound.
This limited test does not prove absence of all timing side channels.

Production Compose supplies registration origin from HTTPS `PUBLIC_ORIGIN`,
SMTP host/port/user/sender via operator config and password via
`/run/secrets/smtp_password`. Entry-point secret loading uses SecretStr; implicit
TLS SMTP_SSL defaults to port 465 with verified system trust, optional additive
CA and no plaintext fallback. Registration email is disabled by default. Only
source configuration/templates were inspected: no production host or real
provider credential/delivery was verified. Development `.env` was not exposed or
changed. The local synthetic TLS SMTP sink passes registration delivery and
browser-bound verification; it is not an internet provider or inbox receipt.

**Real-provider SMTP, sender DNS/reputation and inbox delivery: NOT VERIFIED.**
A concrete authorized-recipient procedure and hosted acceptance checklist are in
[hosted staging acceptance](hosted-staging-acceptance.md). Operators must explicitly
authorize real sending and provide configuration; no password/token/API key is
stored in tracked evidence. Provider failure is publicly generic but current
code supplies no verified operational delivery-success alert; establish provider
monitoring and controlled receipts before enabling production enrollment.

## Files changed

Modified existing files: `infra/scripts/smoke.py`, `docs/release-acceptance.md`
and `docs/release-checklist.md`. Added the three requested 12.2 assessment,
inventory and verification documents; `docs/hosted-staging-acceptance.md`;
`infra/testing/monitoring_check.py`; four experimental rebuild files under
`infra/monitoring/grafana-rebuild/` (two Dockerfiles, checksum/module patch and
README); and reproducible evidence under `docs/evidence/m122/`. The implementation
file hashes are in the source manifest and report/evidence hashes are separately
indexed. Application code, existing tests, production Compose, CI workflows,
deployment/release gates and development Compose were preserved.

## Release assessment and remaining work

[Verification](security-remediation-12-2-verification.md) records exact executed
commands and observed results, including failed attempts. [Formal acceptance](release-acceptance.md)
and [checklist](release-checklist.md) distinguish local PASS from hosted NOT VERIFIED.

Infrastructure/security owners must obtain a source-matched supported Grafana
artifact with every actual plugin binary fixed, scan the entire image on the
intended architecture and repeat the operational checks. No security exception
has been requested or approved by this agent. Identity/SRE owners must complete
real-provider SMTP and approved hosted staging, offsite encrypted recovery,
rollback compatibility, public TLS and operational alerting. Repository owners
must verify hosted exact-SHA CI, branch/environment protections and manual
approval execution. Whole-image reproducibility and intended AMD64 acceptance
remain NOT VERIFIED. The dev-only lint dependency chain still has five high
affected nodes (one braces advisory), with latest compatible braces 3.0.3 still
affected; runtime npm and Python audits are clean. Do not downgrade the completed
framework to bypass that finding.

**FAIL / NO-GO: production release remains BLOCKED.** Local functional passes do
not override container policy or missing hosted evidence.
