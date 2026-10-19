# Security remediation 12.4 — five-CVE investigation and release reassessment

Date: **2026-10-20, Asia/Dubai**. **Formal production decision: FAIL / BLOCKED.**
The latest committed revision was **`1ffa5ea18ca4eb73d72263efc7ac6978376f1080`**;
the checkout was clean before changes. 12.3 evidence, current production Compose,
scanner/release gates and build/monitoring fixtures were inspected first.
No commit, push, DNS change, purchase, public deployment, production credential
access, development reset, volume deletion or security exception was performed.

## Outcome and immutable image identities

The maintained-branch experiment reduces **five HIGH findings to two**, with no
new high/critical advisories. All three kin-openapi CVEs are absent in the complete
candidate scan. Both Tempo advisories remain blocking; no waiver or suppression
was used. The candidate is **not selected or promoted**. Production still selects
13.2.4, whose fresh scan retains 61 high findings.

| Image / role | Exact immutable identity | Before HIGH/CRITICAL | Fresh HIGH/CRITICAL | Selection |
| --- | --- | ---: | ---: | --- |
| Grafana 13.2.4 selected | `grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f` | 61/0 | 61/0 | Unchanged |
| Grafana 12.4.13 official upstream candidate | `grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` | 5/0 | 5/0 | Rejected by policy |
| Patched 12.4.13 local experiment | `evidenceai-grafana:kin-m124`, local OCI index `sha256:b148dae4dd05367a98a51097e1976b3bdb0dcfe0646aa6f42ef4b8a3c2ac3a3a` | 5/0 upstream | **2/0** | Rejected by policy |

The local index is **not a published registry digest**; no image was pushed. All
three images have zero secret findings. The seven other selected runtime images
were freshly scanned with zero high/critical/secret findings. Candidate remaining
severities are one medium and one unknown, zero low. Full normalized findings,
image configuration IDs, OCI IDs, archive/report hashes, platforms, layer identities
and scan timestamps are in [inventory](security-remediation-12-4-inventory.json).
All local image tests/builds are **Linux ARM64**; AMD64 remains NOT VERIFIED.

## Exact five-CVE remediation table

All five original findings occur in `usr/share/grafana/bin/grafana` (Go language
dependencies), not five different vulnerable services.

| Advisory | Package | Installed upstream | Scanner/vendor fixed versions | Observed remediation status |
| --- | --- | --- | --- | --- |
| [CVE-2026-100352](https://github.com/getkin/kin-openapi/security/advisories/GHSA-rj39-cv6w-8wv7) | `github.com/getkin/kin-openapi` | v0.147.0 | 0.148.0 | PASS: absent after build; resolved v0.149.0 |
| [CVE-2026-100353](https://github.com/getkin/kin-openapi/security/advisories/GHSA-vrcc-3ch7-hppw) | `github.com/getkin/kin-openapi` | v0.147.0 | 0.149.0 | PASS: absent after build; resolved v0.149.0 |
| [CVE-2026-100354](https://github.com/getkin/kin-openapi/security/advisories/GHSA-g8cf-rcjf-c8cf) | `github.com/getkin/kin-openapi` | v0.147.0 | 0.149.0 | PASS: absent after build; resolved v0.149.0 |
| [CVE-2026-21728](https://grafana.com/security/security-advisories/cve-2026-21728) | `github.com/grafana/tempo` | v1.5.1-0.20260427112133-525d1bab07e0 | 2.8.4, 2.9.2, 2.10.2 | FAIL policy: still reported; source applicability NOT VERIFIED |
| [CVE-2026-28377](https://grafana.com/security/security-advisories/cve-2026-28377) | `github.com/grafana/tempo` | v1.5.1-0.20260427112133-525d1bab07e0 | 2.10.3 | FAIL policy: still reported; source applicability NOT VERIFIED |

The three kin-openapi findings affect schema/decoder validation denial of service.
The Tempo advisories concern query-limit memory allocation and S3 encryption-key
exposure through Tempo's status/config endpoint. These vendor descriptions do not
establish that Grafana exposes those Tempo server handlers. No finding is dismissed
merely because an exploit path was not demonstrated. Every finding retains the
scanner HIGH classification, installed version, binary/layer and vendor reference.

## Authenticity, support and newer upstream releases

**PASS, registry/release origin:** verified HTTPS official Docker Hub tag metadata
matches the exact pulled/saved 12.4.13 digest; official GitHub release metadata
identifies v12.4.13 as a non-prerelease/non-draft release. The source tag resolves
to `bbc0a79c71a946c1fd61ee4f9e0fcba812c18bd7`; GitHub commit verification metadata is
retained. [Origin evidence](evidence/m124/upstream-authenticity.json).
Independent publisher-signature verification and bit-for-bit vendor build
reproducibility are **NOT VERIFIED**; registry TLS/digest and commit metadata are
not represented as such proofs.

[Grafana's support policy](https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/)
lists 12.4 patch support through **2027-05-24**. Fresh official branch tags still
show **12.4.13** as newest; the current [latest-release endpoint](https://github.com/grafana/grafana/releases/latest)
returns **13.2.4**. No newer 12.4 security/patch image was available in the retrieved
metadata. The prior 12.3 comparison of maintained 13.0/13.1/13.2 images remains
historical, not newly claimed fresh testing. The selected 13.2.4 itself was
rescanned. No floating tag was introduced in deployment definitions.

## Safe local build and component fixes

Added a separate checksum-pinned `124.Dockerfile` and reviewable
`dependencies-124.patch`. Source archive SHA-256:
`53fb4872e64de5a9a626ef9acd60b4b84c59a54394587f488dba6bff76299924`.
The patch upgrades kin-openapi 0.147.0 -> **0.149.0** and required jsonschema 6.0.2
-> **6.0.3**, retaining Go module checksums. Both actual and dry-run patch application
must succeed with zero fuzz; readonly module resolution asserts the intended
version. Compilation uses pinned Go **1.27.2**, OSS/CGO/trimpath flags, bounded
parallelism and the source-pinned **go.work** with its local Prometheus library.

The first GOWORK=off attempt failed with external promlib 0.0.8's obsolete
`parser.ParseExpr`. Using the release source workspace corrected that build issue,
without a parser downgrade or product workaround. The corrected build succeeded
in **207.352s**. Source/patch/module/compiler/build-flag and actual executable
checksums are recorded inside the image and read back in
[build provenance](evidence/m124/build-provenance.txt). Metadata labels identify a
custom experiment; it is not a vendor-supported rebuilt release or independent
signed attestation. The vendor binary health reports source commit
`6367d911d57309d1da370872b8fd76237b5a0ffa`; the official API lookup returns HTTP422
([response](evidence/m124/vendor-patched-source-response.txt)). Full equivalence
with that patched distribution remains NOT VERIFIED.

All **11,551 regular frontend/native-plugin asset files** match the upstream
runtime byte-for-byte. The separate external bundled-plugin directory is empty in
this vendor layout; an empty hash is not treated as plugin coverage. Native plugin
identity is additionally checked through Grafana's core-only API and actual
Prometheus operations. No datasource was removed. [Asset identity](evidence/m124/asset-parity.json).
The complete scan verifies removal of CVE-2026-100352, CVE-2026-100353 and
CVE-2026-100354. This is a real component-level fix in an unapproved local candidate;
it does not establish a clean supported upstream binary or change the selected
production count.

## Tempo findings: supported fixes and unresolved policy

Vendor Tempo product fixes exist: [CVE-2026-21728](https://grafana.com/security/security-advisories/cve-2026-21728/)
identifies 2.8.4/2.9.2/2.10.2 branches; [CVE-2026-28377](https://grafana.com/security/security-advisories/cve-2026-28377/)
requires 2.10.3. A direct Go dependency update to `github.com/grafana/tempo@v2.10.3`
was actually attempted. The official Go proxy returns HTTP404: the module contains
a go.mod whose path does not satisfy the v2 major-version path requirement.
A strict proxy-only build probe independently reproduces that error; no binary
version metadata was forged and no major-version source substitution was shipped.
The initial default probe also hit a missing-Git fallback; that environmental
failure is retained separately from the proxy's definitive module-path response.

Importantly, official GitHub compare results show the pinned pseudo-version commit
**525d1bab07e0** descends from **both** referenced Tempo fix commits, with each fix
as merge-base and zero commits behind. [Ancestry](evidence/m124/tempo-source-ancestry.json).
The fix paths concern Tempo frontend limits and S3 backend config masking:
[scope evidence](evidence/m124/tempo-fix-scope.json). This is evidence of a possible
advisory/version-mapping issue, not a blanket false-positive verdict. Ancestry
alone does not rule out later reverts, prove compiled behavior, or demonstrate
Grafana's exposure. Full applicability and a vendor/scanner-endorsed resolution
remain **NOT VERIFIED**. Both findings remain **FAIL under release policy**.
Upstream should validate the module mapping/source applicability and publish a
supported scan-clean artifact or corrected authoritative advisory data. No local
ignore rule, VEX waiver or self-approved exception is introduced.

## Operational and regression acceptance

The corrected isolated fixture **passed** native plugin trust, startup/health,
same-data restart/upgrade/rollback, provisioning, dashboard persistence, admin
authentication/anonymous denial, actual Prometheus queries, TLS and network
isolation. All thirteen expected datasources identify as native internal core
plugins in this 12.4 layout. The patch does not introduce an unsigned-plugin
allowance. Load passed: 352 requests, zero failures, p95 33ms/p99 91ms. Encrypted
recovery restored 20 documents/originals, authenticated operation and pending work
in 45.961s. Full observed results are in
[verification](security-remediation-12-4-verification.md). Initial
build/probe and acceptance-profile failures are retained and distinguished from
final results. The 13.x plugin-signature checks remain unchanged; 12.4 native core
plugins must identify as internal **and** appear in `/api/plugins?core=1`.
External unsigned/invalid/modified plugins remain rejected. This adjusts a version-
specific functional assertion, not the vulnerability gate.

Fresh regressions: **653 backend tests**, **53 frontend tests**, TypeScript, lint,
production build, **18 browser tests** across Chromium/Firefox/WebKit, migration
current/check, dependency audits and infrastructure guards. See exact exits/logs
in the verification record; development npm still has five high lint-chain nodes.
No existing feature, test or migration was deleted or weakened.

Development preservation has mixed results. **PASS:** every original row is intact,
14 whole tables and revision match, and private storage contents/size/mtime/
permissions/owners/link state match exactly. The four original limiter rows were
separately proven intact by matching the original whole-row hash against a subset
of current rows. **FAIL:** whole development-database equality; eight limiter rows
and three registration intents were added during the session. Attribution remains
**NOT VERIFIED**: intent addresses do not match owned staging IDs or source-defined
browser/unit UUID patterns. No added record was deleted or rewritten to force a
pass. Private values/filenames/snapshots remain outside Git; see
[aggregate evidence](evidence/m124/data-preservation.json). This observed delta must
be reviewed before any release signoff; no claim that the entire DB was unchanged
is made.

## Release recommendation and hosted requirements

The existing scanner, formal release gate, CI/CD workflows, production image pin
and development Compose remain unchanged. The formal gate returns **exit 1 /
BLOCKED**. The unexplained development-data additions are a separate failed
assessment condition; original data was preserved but whole-state equality was not. Do not substitute an older image on existing Grafana data merely because
its count is smaller. The local same-version experiment is not authorization for
a 13.x-to-12.x downgrade or production rollout.

Real SMTP delivery/inbox authentication, hosted DNS/TLS/ingress/staging, hosted
exact-SHA CI and reviewer/SSH protections, offsite encrypted restore/key escrow,
production RTO/RPO and rollback to an accepted predecessor remain **NOT VERIFIED**.
The [existing concrete operator procedures](hosted-staging-acceptance.md) still
apply after separate authorization; none was fabricated as passed.

**Recommendation: withhold production approval.** Three CVEs were resolved in the
local candidate, two scan blockers remain, and the selected image still has 61.
No acceptable monitoring image has passed the existing security release policy.
Files added: the 12.4 recipe/patch, three requested 12.4 reports and sanitized
reproduction evidence. Updated: native-plugin compatibility probe, experimental
README, release acceptance and checklist. Application code, migrations, deployment
configuration and security gates are preserved; source/evidence hashes accompany
the report. No exception, commit, push or public deployment was authorized here.
