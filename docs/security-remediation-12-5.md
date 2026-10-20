# Security Remediation 12.5 — Tempo and database integrity

**Production release: FAIL / BLOCKED.** Date2026-10-20, Asia/Dubai. Inspected
baseline **`932f75f`**, initially clean. Safe local isolation changes, an actual
candidate rebuild, fresh scans, regressions, monitoring and recovery tests were
completed. No candidate was promoted, exception approved, commit/push made,
public deployment performed, DNS changed, server purchased or development record
removed. The 11 historical additions remain preserved.

## Security outcome and immutable artifacts

| Image | Immutable identity |12.4 HIGH/CRITICAL →12.5 HIGH/CRITICAL |
| --- | --- | --- |
| Selected Grafana 13.2.4 |`grafana/grafana@sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f` |61/0 →61/0 |
| Supported upstream 12.4.13 |`grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` |5/0 →5/0 |
| Previous unselected12.4 experiment |Local OCI index`sha256:b148dae4dd05367a98a51097e1976b3bdb0dcfe0646aa6f42ef4b8a3c2ac3a3a` |2/0 historical; not rescanned under this tag |
| New 12.5 experiment, `evidenceai-grafana:kin-m125` |Local OCI index`sha256:514e1e31662cf191943b983103d2fe74f9933ff0a358bc722d58213ead3bfb1b` |2/0 baseline →2/0 fresh |

Both local OCI indices are local identities, **not registry publications**. The
new image is unapproved/unselected. No additional CVE was resolved in 12.5; the
three kin-openapi fixes from 12.4 remain effective. All images above have zero
secret findings in their respective scans. The seven other selected runtime
images freshly scan zero HIGH/CRITICAL/secrets. Full all-severity findings,
config/layer/archive identities, scanner/DB timestamps and before/after counts are
in [inventory](security-remediation-12-5-inventory.json). Tests/builds are ARM64;
AMD64 remains NOT VERIFIED. Existing selected runtime application images were
rescanned, not rebuilt to claim coverage of unrelated product changes.

## Exact remaining Tempo findings

Both findings are in `usr/share/grafana/bin/grafana`, module
**`github.com/grafana/tempo v1.5.1-0.20260427112133-525d1bab07e0`**.

| Advisory | Vendor product fix | Reachability evidence | Release classification |
| --- | --- | --- | --- |
|CVE-2026-21728 /GHSA-p4r4-xvrq-gvmc |Tempo 2.8.4,2.9.2,2.10.2 |Affected frontend query-limit package absent from this custom OSS compile graph |FAIL: scanner HIGH retained |
|CVE-2026-28377 /GHSA-ffqx-q65f-36jf |Tempo 2.10.3 |Affected S3 backend configuration package absent from this custom OSS compile graph |FAIL: scanner HIGH retained |

Fresh [vendor21728](https://grafana.com/security/security-advisories/cve-2026-21728/)
and [vendor28377](https://grafana.com/security/security-advisories/cve-2026-28377/)
records describe respectively query-limit allocation denial of service and S3
SSE-C key exposure through Tempo's config endpoint. Product fixed versions do not
automatically constitute a valid supported Go-module update inside Grafana.

Fresh official metadata still lists Grafana 12.4.13 as the latest12.4 patch and
13.2.4 as latest released Grafana.12.4 has vendor patch support through 2027-05-24
([support policy](https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/)).
Although13.3 is scheduled for today, the retrieved release endpoint did not return
it; no unreleased image was assumed available. Fresh Tempo metadata lists3.1.0.
The actual new `tempo-v3-probe` build fails: official Go proxy rejects the
unversioned module path for v3.1.0, requiring a matching `/v3` path.12.4 already
retains the analogous v2.10.3 failure. No module path substitution, dependency
removal, version metadata forgery, advisory suppression or VEX waiver was used.

The pinned Tempo commit descends from both vendor fix commits according to the
preserved12.4 official ancestry evidence; ancestry alone did not prove runtime
behavior or scanner acceptance. The new build records its **actual 4269-package
OSS dependency graph**. Its only Tempo packages are `pkg/tempopb` and three
protobuf subpackages; `modules/frontend` and `tempodb/backend/s3` are absent.
[Build graph](evidence/m125/tempo-reachability.json). This narrows source reachability
for the custom binary. It does not establish vendor patched-binary equivalence,
prove every external/dynamic deployment safe, or change a module-version finding.
Full vendor-runtime applicability and a vendor/scanner-endorsed resolution remain
NOT VERIFIED. Both findings still fail the unchanged security policy.

Supported next paths are a maintained Grafana release with accepted complete scans,
or authoritative vendor/advisory mapping correction validated by the scanner.
Tempo server deployments must independently use fixed vendor product releases;
this project does not deploy a Tempo server. Do not silently swap in an older
Grafana on13.x production data. No acceptable production image is identified.

## Build provenance and monitoring compatibility

Added `125.Dockerfile` using the existing checksum-pinned12.4 source/kin patch,
Go 1.27.2 compiler image and immutable upstream runtime. Real build exit 0,
**42.715seconds** with existing compiler caches; source graph is copied from the
build into the candidate and read back. The v3 probe exits 1 (**15.056seconds**
measured by the command wrapper). Source/archive/compiler/module/binary hashes
are in [provenance](evidence/m125/build-provenance.txt). No Tempo source upgrade
was shipped. The pinned runtime's frontend/native plugin assets are retained by
the recipe; no plugin was removed to lower a scan count.

Official registry tag metadata matches the immutable upstream digest. The source
archive checksum is verified by Docker; public source commit is
`bbc0a79c71a946c1fd61ee4f9e0fcba812c18bd7`. The vendor binary reports a different
patched-source commit, whose full parity was not established in 12.4. Independent
publisher signature verification is **NOT VERIFIED** (`cosign` unavailable locally;
no upstream signer policy/receipt was established). TLS/digest/source metadata and
local BuildKit attestation are not represented as publisher signature verification.
The custom image has no vendor support/signature endorsement.

The owned local staging drill passes actual Grafana health/admin login/anonymous
401/signup disablement, dashboard provisioning, all 13 native plugin trust/identity
checks, provisioned Prometheus datasource health and two-target `up` queries.
Grafana has no host-published port, runs on the internal monitoring network and
public monitoring paths are refused. No unsigned-plugin allowance was added.
Restart →upstream 12.4-to-custom upgrade →rollback preserves the same synthetic
SQLite/dashboard state/version and repeats monitoring checks each time. These
are same-version local transitions, not an accepted production rollback or13→12
migration. External Tempo/provider semantics and soak remain NOT VERIFIED.

## Database integrity and historical evidence

[Investigation](database-integrity-investigation.md): the 8 limiter and3 intent
additions are in `evidenceai.public`; their contents still match12.4's after-state.
Intent creation times are21:20:24,21:22:41 and21:25:36 UTC on2026-10-19. Five limiter
keys match loopback auth actions and three match recipient actions for those
intents; no recipient/key is published. The recorded pytest run and browser event
bounds precede these intents. Historical logging/commit timestamps are unavailable.
**Writer attribution remains NOT VERIFIED.** No claim that a particular test,
worker, caller or user created the records is justified.

Fixed the isolation architecture: shared fail-closed test URL guard, separate
owned tmpfs PostgreSQL/pgvector database, explicit indirect-engine configuration,
ORM and raw-SQL scratch scoping, cleanup/empty-public-table assertions, and matching
CI job-owned service configuration. Missing configuration fails before engine
construction. No development role, row or volume was altered. URL naming is a
guard; prefer the owned runner over arbitrary manually supplied services.

**12.5 final whole-database equality FAIL:** an earlier comparison passed, but
final comparison found one additional limiter row (12→13). Its22:15 UTC bucket
and key match a loopback login action; actual insertion time/writer remain NOT
VERIFIED. All 12 pre-existing limiter rows hash-match; the other 15 whole tables,
revision and private-storage bytes/metadata remain identical. All historical
additions and this new row were preserved. Owned test fixture checks pass, but do
not identify the development writer. Both [earlier PASS](evidence/m125/data-preservation.json)
and [final FAIL](evidence/m125/data-preservation-final.json) are retained, with the
[delta investigation](evidence/m125/database-final-delta.json).

The original12.4 checksum manifest remains byte-for-byte intact (SHA256
`27f19c621d4a6e983d42b6aca6b8c41c5786db386f6e17a1d5d8780ba21b4326`). Its69
entries currently produce seven differences: four disclosed normalized historical
files (build provenance, build/lint/unit logs) and three intentionally updated
current documents (release acceptance/checklist and rebuild README). Each current file matches the normalization
audit's normalized hash. **Original byte content recovery PASS:** all four original streams were recovered
from retained runtime files and the old immutable candidate image, then matched
against the unchanged original manifest. New deterministic gzip archives are
append-only under m125. The current normalized historical paths still differ;
this does not independently authenticate all historical custody timestamps. The complete 12.4 evidence directory is unchanged from
`932f75f`. New evidence/checksums live only in `m125`; historical hashes were not
silently regenerated. A new reconstructed archive verifies all 69 original file
contents against that original manifest, including the three prior document
versions. [Snapshot recovery](evidence/m125/historical-snapshot-recovery.json). [Review](evidence/m125/historical-review.json).

## Regression, operations and remaining acceptance

Final passes: **662 backend**, **53 frontend**, TypeScript/lint/production build,
**18 browsers** (six each Chromium/Firefox/WebKit), Alembic head/check, pip check,
Python dependency audit, runtime npm audit and pinned actionlint. Five development
npm high lint-chain nodes remain FAIL. All existing tests remain present. Nine
new isolation tests pass separately as well. Initial harness/test errors and the
first browser run's17/18 result are explicitly retained; the complete browser
rerun passes 18/18 without altered assertions/timeouts. Connection-failure root
cause remains NOT VERIFIED.

Local five-user 30-second load: **341 requests, zero failures, p95 26 ms/p99 56 ms**.
Encrypted backup/restore verified **24 documents/originals**, pgvector 0.8.7 and
revision 91e2b6d8c410; restored authenticated operation and pending work in
**45.985seconds**, zero lost acknowledged synthetic writes with writers quiesced.
Nonempty-target and tampered-ciphertext restore attempts were rejected. Containers
shut down without OOM/exit 137 and owned fixtures were removed. This is a same-host
local drill, not offsite recovery or production capacity/RTO certification.

Hosted real SMTP delivery, public TLS/ingress/staging, exact-SHA CI/CD/protections,
offsite key-escrow restore and accepted production rollback are **NOT VERIFIED**.
Local SMTP is disabled; the actual private-CA SMTP fixture pass is not a provider
receipt. [Operator procedures](security-remediation-12-5-verification.md#hosted-acceptance-procedure)
require separate hosted authorization and retained redacted evidence.

Production selection, scanner, release-decision logic, deployment safeguards and
thresholds remain unchanged. Offline evaluator entry points additionally refuse
inherited development configuration; customer-facing services/routes remain intact. CI changes only wire the job-owned test database to
the new guards. Formal gate exit 1/BLOCKED; dirty-tree packaging exit 1. No security
exception was approved. Recommendation: **withhold production release** pending
accepted clean monitoring artifacts, historical attribution review and real
hosted acceptance. Exact commands, failure history and limitations follow in the
[verification record](security-remediation-12-5-verification.md).

## Files changed

- `apps/api/app/db/disposable_database.py`, `app/evaluate_retrieval.py` and
  `app/evaluate_rag.py`: shared guard and offline-only database safety.
- `apps/api/tests/conftest.py`, `test_workspace_concurrency.py`, new
  `test_database_isolation.py`, and `apps/web/e2e/server.py`: disposable database
  entry guards, raw-SQL scoping and nine new isolation/refusal cases.
- `.github/workflows/ci.yml`: explicit job-owned synthetic test DB configuration.
- `infra/testing/{database_guard.py,run_isolated.py,preservation.py,README.md}`:
  reusable owned fixture lifecycle, privacy-preserving comparisons and operator guide.
- `infra/monitoring/grafana-rebuild/125.Dockerfile` and its README: unselected
  rebuild/probe and compile-graph provenance; existing dependency patch unchanged.
- This report,12.5 inventory/verification, `database-integrity-investigation.md`,
  release acceptance/checklist and append-only `docs/evidence/m125/` receipts,
  original-byte recovery archives, command records and checksum index.

The final offline evaluator run passes68 synthetic samples/thresholds with repeat 3;
final shared-guard browser integration passes 18 cases again, and all nine guard
cases pass separately. These do not constitute hosted model-semantic acceptance.
