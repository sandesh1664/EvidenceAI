# Security remediation 12.4 — executed verification

Date: **2026-10-20, Asia/Dubai**. Baseline:
`1ffa5ea18ca4eb73d72263efc7ac6978376f1080`, initially clean.
**Production release: FAIL / BLOCKED.** Exact argument lists/exits are in
[commands.json](evidence/m124/commands.json); full raw reports/archives remain under
ignored `infra/runtime/m124/`. Sanitized evidence is checksum-indexed separately.
No credentials, original row values, customer document contents or private file
names enter tracked evidence.

## Fresh scans and actual build results

Executed from `/Users/redmug/EvidenceAI`:

```sh
python3 infra/scripts/scan_images.py --tag m121 --support-only --directory infra/runtime/m124/support
# exit 1: selected Grafana 61 HIGH/0 CRITICAL/0 secrets; three support images zero
python3 infra/scripts/scan_images.py --tag m121 --directory infra/runtime/m124/application
# exit 0: four application images zero HIGH/CRITICAL/secrets
python3 docs/evidence/m124/scan_candidate.py --name upstream-124 --reference grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185
# exit 1: 5 HIGH/0 CRITICAL/0 secrets
```

Pinned scanner: Trivy 0.76.0,
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
Current published DB update/download times and scan timestamps are in
[inventory](security-remediation-12-4-inventory.json). The scanner checked/downloaded
intelligence during this run; unchanged published DB timestamps are recorded as
such. Every complete image archive is matched to its config digest and live
layer diff IDs. All local targets are Linux ARM64. No Docker socket or broad host
secret/document mount enters the scanner. All severities are retained.

```sh
docker build --progress=plain --target candidate -f infra/monitoring/grafana-rebuild/124.Dockerfile -t evidenceai-grafana:kin-m124 infra/monitoring/grafana-rebuild
```

Initial **exit 1**, 181.174s: `GOWORK=off` selected external promlib 0.0.8 and failed
with `undefined: parser.ParseExpr`. The source's local promlib uses the current
parser interface. Corrected recipe preserves the source-pinned go.work:
**exit 0, 207.352s**, with a 600s subprocess cap, pinned Go 1.27.2 and bounded
parallelism. Both dry-run and actual zero-fuzz patch application succeeded.
Resolved kin-openapi 0.149.0 is asserted before readonly-module compilation.
The exact source/archive/patch/module/compiler/flags/binary metadata was read back
from `/usr/share/grafana/evidenceai-build.txt` and checked against the executable.
No parser downgrade/product workaround was shipped.

```sh
python3 docs/evidence/m124/scan_candidate.py --name kin --reference evidenceai-grafana:kin-m124
# exit 1: 2 HIGH/0 CRITICAL/0 secrets; no new blocking advisory
python3 docs/evidence/m124/generate_inventory.py
# exit 0: selected images and two candidates match archives/live identities
```

The scanner's successful report-generation exit 0 is not a security pass. The
unchanged HIGH/CRITICAL/secret policy rejects both candidates. Verified absent:
CVE-2026-100352, CVE-2026-100353, CVE-2026-100354. Remaining:
CVE-2026-21728, CVE-2026-28377. Candidate OCI index:
`sha256:b148dae4dd05367a98a51097e1976b3bdb0dcfe0646aa6f42ef4b8a3c2ac3a3a`.
It is a local immutable identity, not a registry publication.

## Vendor and Tempo resolution evidence

Current official metadata was retrieved using verified HTTPS curl:

```sh
curl --fail --silent --show-error --max-time 30 https://hub.docker.com/v2/repositories/grafana/grafana/tags/12.4.13 -o docs/evidence/m124/official-124-tag.json
curl --fail --silent --show-error --max-time 30 'https://hub.docker.com/v2/repositories/grafana/grafana/tags?name=12.4&page_size=100&ordering=last_updated' -o docs/evidence/m124/branch-tags.json
curl --fail --silent --show-error --max-time 30 'https://api.github.com/repos/grafana/grafana/releases?per_page=10' -o docs/evidence/m124/releases.json
curl --fail --silent --show-error --max-time 45 https://codeload.github.com/grafana/grafana/tar.gz/refs/tags/v12.4.13 -o infra/runtime/m124/source.tar.gz
```

Source archive SHA-256:
`53fb4872e64de5a9a626ef9acd60b4b84c59a54394587f488dba6bff76299924`.
Official tag, source tag/commit verification and support-policy references are
retained in [origin evidence](evidence/m124/upstream-authenticity.json).
No newer 12.4 patch/security image was available in the retrieved metadata.
Registry/digest origin is verified; independent publisher-signature and whole-image
reproducibility are NOT VERIFIED.

The five current maintainer advisories were fetched with
`curl --fail --silent --show-error --max-time 30 URL`; exact retrieved URLs and
results are in [vendor-advisories.json](evidence/m124/vendor-advisories.json).
Both Tempo product advisories list fixes, but the Go dependency tag probe fails:

```sh
docker build --progress=plain --target tempo-probe -f infra/monitoring/grafana-rebuild/124.Dockerfile infra/monitoring/grafana-rebuild
# exit 1: GOWORK=off GOPROXY=https://proxy.golang.org go get github.com/grafana/tempo@v2.10.3
```

Official Go proxy response: HTTP404 / invalid version because a module with go.mod
must satisfy the major-version `/v2` path rule. Source tag v2.10.3 declares
`module github.com/grafana/tempo`. An earlier default-proxy attempt additionally
failed its missing-Git fallback; strict proxy retry isolates the canonical version
problem. The delivered probe reproduces it. No pseudo-version text or binary
metadata was edited to fool scanning.

Actual official GitHub compare requests:

- `https://api.github.com/repos/grafana/tempo/compare/650eb1985a0776789c8564122990f588a742356f...525d1bab07e0`
- `https://api.github.com/repos/grafana/tempo/compare/bb8ca663db34a0980c9758b40d918fda3b4dbec3...525d1bab07e0`

Both returned success, status ahead, zero behind, and the fix as merge-base.
Changed source paths were retrieved from each fix's commit API. This supports a
possible version/advisory mapping discrepancy but does not prove all linked-code
behavior or rule out later reverts. Runtime applicability is NOT VERIFIED, not
silently dismissed. The two findings remain blocking. Vendor binary health reports
commit `6367d911d57309d1da370872b8fd76237b5a0ffa`; its official commit lookup returns
HTTP422/no commit found. Our public tag source is `bbc0a79...`. Full equivalence with
the vendor patched binary is NOT VERIFIED.

Actual image file hashes were collected with Docker `sha256sum` and
`find /usr/share/grafana/public -type f -exec sha256sum {} + | sort` in upstream and
patched images. All 11,551 regular frontend/native-plugin files match. The separate
external bundle directory has zero regular files/links; that empty hash is not
used as sufficient plugin coverage. Thirteen native plugins are separately checked
through Grafana's core API and real Prometheus calls.

## Operational acceptance and retained failures

First local fixture used 13.x's external-signature assumptions and returned exit 1
at the signature assertion for native core plugins. This was an acceptance-profile
mismatch. The corrected 12.4-only profile permits `internal` **only** if the plugin
also appears in the authoritative `/api/plugins?core=1` response. External unsigned,
invalid or modified plugins still fail. The 13.x external signature requirement
and vulnerability release gates are unchanged. Initial failures are retained in
[initial-failures.json](evidence/m124/initial-failures.json) and raw runtime logs.

Final actual command:

```sh
EVIDENCEAI_ACCEPTANCE=1 EVIDENCEAI_EVIDENCE_TAG=m124-final EVIDENCEAI_GRAFANA_IMAGE=grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185 EVIDENCEAI_GRAFANA_TRANSITION_IMAGE=evidenceai-grafana:kin-m124 python3 infra/scripts/smoke.py
# exit 0
```

PASS: startup/health, admin auth, anonymous 401, signup disabled, provisioned
EvidenceAI Operations dashboard, all thirteen expected native datasource IDs,
core-only native trust classification, datasource health and a real Grafana-proxied
Prometheus query with two targets up. PASS: one internal monitoring network, no
published Grafana port, protected internal metrics and public monitoring-route
denial, verified private-CA TLS/HTTP redirect/HSTS/CSRF/private storage behavior.
Public ACME/hosted ingress is NOT VERIFIED.

The owned Grafana bind/SQLite data persisted across graceful stop/restart (exit 0,
no OOM), patched-core upgrade and return to upstream 12.4.13. A separately created
synthetic dashboard retained title/version 1; auth, provisioning and actual queries
passed at each phase. Recorded server commits prove the transition and return.
No existing Grafana/DB/document volume was mounted. No 13.x-to-12.x production
in-place downgrade was attempted. External datasource service semantics and long
soak remain NOT VERIFIED.

PASS local bounded load: **352 requests, 0 failures, p50 8ms/p95 33ms/p99 91ms**,
11.774 requests/s, five users/30s and unchanged minimum/error/latency/queue thresholds.
Builds/scans completed before load. PASS encrypted recovery: **20 documents/originals**,
checksums, schema `91e2b6d8c410`, pgvector 0.8.7, session, fresh login, downloads and
pending-job recovery. Backup 0.055s, restore 0.085s, restored-app recovery **45.961s**,
last acknowledged write to backup completion 1.187s, zero lost acknowledged synthetic
writes with writers quiesced. Nonempty target and tampered ciphertext correctly
rejected; API SIGTERM 143, worker/proxy 0, no OOM/exit 137. Same-host tiny offline
provider tests do not establish production RTO/RPO or independent offsite recovery.
See [staging.json](evidence/m124/staging.json) and [load.json](evidence/m124/load.json).

## Application, browser and infrastructure regressions

Executed from the indicated directories through the retained
[runner](evidence/m124/run_regressions.py), with
`PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers` and timing-report output in
`docs/evidence/m124/registration-timing.json`. Build and browsers ran sequentially.

| Directory | Command | Result |
| --- | --- | --- |
| apps/api | `.venv/bin/python -m pytest -q --junitxml=/Users/redmug/EvidenceAI/docs/evidence/m124/backend.xml` | exit 0, 653 passed |
| apps/api | `.venv/bin/python -m pytest -q tests/test_deployment.py` | exit 0, 26 passed |
| apps/api | `.venv/bin/python -m alembic current` / `... alembic check` | exit 0, head91e2b6d8c410, no new operations |
| apps/api | `.venv/bin/python -m pip check` | exit 0 |
| apps/web | `npm test` | exit 0, 53 passed |
| apps/web | `npm run lint` / `npx tsc --noEmit` / `npm run build` | each exit 0 |
| apps/web | `npm run test:e2e` | exit 0, 18 passed; six each Chromium/Firefox/WebKit |
| apps/api | `/tmp/evidenceai-m11-audit-venv/bin/python -m pip_audit -r requirements.txt --format json` | exit 0, 44 dependencies/zero findings |
| apps/web | `npm audit --omit=dev --json` | exit 0, zero runtime findings |
| apps/web | `npm audit --json` | exit 1, five high development lint-chain nodes |

Pinned offline actionlint command and exact arguments/exits are in commands.json;
it returned0. No application code, migration or completed feature was changed.

## Development records and private storage — mixed result

**PASS:** all original rows preserved; 14 full tables and revision match, and all
private file bytes/size/mtime/mode/owners/link state match. **FAIL:** full development
DB equality: auth_rate_limits4->12 and registration_intents0->3. The four original
limiter rows are proven byte-identical by finding the exact original whole-row hash
among current rows; no original intent existed. Added records' source is **NOT VERIFIED**.
Aggregate checks found no intent matching owned staging identities or browser/unit
UUID fixture patterns. This does not prove another actor or establish causality.
No added record was deleted, modified or automatically cleaned to force a pass.

Private snapshot commands used the project interpreter with
`PYTHONPATH=apps/api apps/api/.venv/bin/python /tmp/m124_snapshot.py before` and
`... /tmp/m124_snapshot.py after`. The after equality assertion actually failed;
private hash/subset analysis separated additions from original data preservation.
Snapshots remain outside Git, mode0600. The report explicitly retains this failure:
[data-preservation.json](evidence/m124/data-preservation.json). Attribution and
whole-state signoff require further review; do not claim the entire DB unchanged.

## Release gates and hosted limits

```sh
python3 infra/scripts/release_manifest.py --output infra/runtime/m124/manifest.json
# exit 1: clean committed source required; no commit authorized
python3 infra/scripts/verify_release.py docs/evidence/m124/release-result.json
# exit 1 / BLOCKED
```

Scanner/release code, CI/CD workflows, production pin and development Compose
remain unchanged. No severity threshold, ignore flag, advisory suppression,
unsigned-plugin allowance or exception was introduced. The unexplained database
additions are an additional failed assessment condition, separate from the strict
container gate. Hosted SMTP inbox, public TLS/ingress/staging, exact-SHA hosted CI,
reviewer/SSH protection, offsite recovery/key escrow, production RTO/RPO, intended
AMD64 and full vendor-build provenance remain NOT VERIFIED. Existing concrete
operator procedures remain linked in the release checklist. No real email, public
deployment, DNS change, purchase, commit or push occurred.
