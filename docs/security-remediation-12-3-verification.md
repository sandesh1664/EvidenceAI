# Security remediation 12.3 — executed verification

Date: **2026-10-20, Asia/Dubai**. Starting revision:
`5d4571d87b0ab866f0942c4a52bdd0cad89e264c`; initial working tree clean.
**Production: FAIL / BLOCKED.** All hosted criteria below remain NOT VERIFIED.
Commands run from `/Users/redmug/EvidenceAI` unless a working directory is shown.
[commands.json](evidence/m123/commands.json) records exact arguments, working
directories, exits and durations where measured. Full reports/archives are retained
under ignored `infra/runtime/m123/`; sanitized retained evidence is under
`docs/evidence/m123/`, indexed by SHA-256. Original secrets and private row snapshots
are outside Git. No failures were converted to passes by lowering requirements.

## Regression and dependency checks

Executed through [run_regressions.py](evidence/m123/run_regressions.py), with
`PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers` and
`EVIDENCEAI_TIMING_REPORT=/Users/redmug/EvidenceAI/docs/evidence/m123/registration-timing.json`.
Frontend build and browser tests ran sequentially, avoiding the previous build lock
collision. Backend/browser DB fixtures own unique schemas; production/development
public rows are never reset.

| Directory | Actual command | Exit / observed result |
| --- | --- | --- |
| root | `git --no-pager log -1 --oneline` / `git status --short` | 0; requested baseline, initially clean |
| apps/api | `.venv/bin/python -m pytest -q --junitxml=/Users/redmug/EvidenceAI/docs/evidence/m123/backend.xml` | 0; **653 passed**, 32.77s; existing Starlette/httpx deprecation warning |
| apps/api | `.venv/bin/python -m pytest -q tests/test_deployment.py` | 0; **26 passed**, 0.29s after fixture changes |
| apps/api | `.venv/bin/python -m alembic current` | 0; **91e2b6d8c410 (head)** |
| apps/api | `.venv/bin/python -m alembic check` | 0; no new upgrade operations |
| apps/api | `.venv/bin/python -m pip check` | 0; no broken requirements |
| apps/web | `npm test` | 0; **53 passed**, four files |
| apps/web | `npm run lint` | 0 |
| apps/web | `npx tsc --noEmit` | 0 |
| apps/web | `npm run build` | 0; production routes compiled |
| apps/web | `npm run test:e2e` | 0; **18 passed**, six each Chromium/Firefox/WebKit, ~1.3m |
| apps/api | `/tmp/evidenceai-m11-audit-venv/bin/python -m pip_audit -r requirements.txt --format json` | 0; 44 dependencies, zero findings |
| apps/web | `npm audit --omit=dev --json` | 0; zero runtime findings |
| apps/web | `npm audit --json` | **1**; five high development lint-chain nodes; unresolved braces advisory |

Browser case names and engine results are preserved in
[browser-summary.log](evidence/m123/browser-summary.log). Identity, authorization,
CSRF, storage, research/citations/history, responsive/keyboard navigation, roles
and recoverable failure tests remain intact. No real provider email/model call is
represented by these mocked/synthetic tests.

## Fresh selected-image baseline

```sh
python3 infra/scripts/scan_images.py --tag m121 --support-only --directory infra/runtime/m123/support
# exit 1: Grafana 61 high / 0 critical / 0 secrets; other three images zero
python3 infra/scripts/scan_images.py --tag m121 --directory infra/runtime/m123/application
# exit 0: API/worker, web, backup and proxy zero high / critical / secrets
```

These commands download/check Trivy intelligence, export actual local images and
scan complete archives. The selected Grafana live digest equals the immutable
production reference `sha256:dbbc38ea21103cefb50396340cd88afec779c7e070b0a7bf5a75b4ce46651d3f`.
Report/archive configuration hashes and live layer diff IDs match. Trivy 0.76.0
and DB update/download timestamps are recorded in
[inventory](security-remediation-12-3-inventory.json). Latest published DB time
was still 2026-10-19T19:08:34.442427859Z; the supporting baseline downloaded it again
at 20:21:19.558070722Z. Historical results are not presented as fresh scans.
No application runtime rebuild was needed. All local target platforms are ARM64.

## Upstream and experimental scans

Official tags/releases were retrieved with verified HTTPS curl from:

```sh
curl --fail --silent --show-error --max-time 45 'https://hub.docker.com/v2/repositories/grafana/grafana/tags?page_size=100&ordering=last_updated' -o infra/runtime/m123/upstream-tags.json
curl --fail --silent --show-error --max-time 45 'https://api.github.com/repos/grafana/grafana/releases?per_page=30' -o infra/runtime/m123/upstream-releases.json
curl --fail --silent --show-error --max-time 30 https://hub.docker.com/v2/repositories/grafana/grafana/tags/13.0.11 -o docs/evidence/m123/upstream-130-tag.json
```

The following actual `scan_candidate.py --name NAME --reference REFERENCE`
invocations each returned **exit 1 / FAIL** after successful pull/export/scanning:

| NAME | Exact REFERENCE | High / critical |
| --- | --- | ---: |
| upstream-distroless | `grafana/grafana@sha256:ae3d3add290adbe6a88412229f5d76fd7bb82743050881698642d3d62f277e35` | 61 / 0 |
| upstream-131 | `grafana/grafana@sha256:1a8e58976a6cd349d1ffdd27a14b92053816c7c60e6b7e157013e9bf0b9cec5f` | 15 / 0 |
| upstream-124 | `grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185` | 5 / 0 |
| upstream-130 | `grafana/grafana@sha256:2abd2114bb65e4d6f0614206b7c882c1e7c6a992827ba08396aa5afc23ca07f5` | 10 / 0 |
| core | `evidenceai-grafana:experimental-m123` | 56 / 0 |
| plugins | `evidenceai-grafana:plugins-m123` | 61 / 0 |
| combined | `evidenceai-grafana:combined-m123` | 56 / 0 |

The command prefix is `python3 docs/evidence/m123/scan_candidate.py`.
The retained [scanner script](evidence/m123/scan_candidate.py) and
[machine-readable commands](evidence/m123/commands.json) reproduce each full
argument list, including Docker pull/save and scanner mounts. Every image had
zero secret findings. Report-generation exit 0 means the scanner completed;
subsequent unsuppressed HIGH/CRITICAL/secret policy evaluation returns 1 for all
Grafana experiments. The script uses the pinned scanner, dedicated per-image
archive/report mounts and a narrow shared cache; no Docker socket or secret mount
is passed to Trivy. It does not modify CI or production image selection.

## Build, patch and provenance commands

```sh
docker build --progress=plain -t evidenceai-grafana:experimental-m123 infra/monitoring/grafana-rebuild
# exit 0; bounded subprocess timeout 600s, observed 32.579s
docker build --progress=plain -f infra/monitoring/grafana-rebuild/stackdriver.Dockerfile -t evidenceai-grafana:plugins-m123 infra/monitoring/grafana-rebuild
# exit 0
docker build --progress=plain -f infra/monitoring/grafana-rebuild/stackdriver.Dockerfile --build-arg BASE_IMAGE=evidenceai-grafana:experimental-m123 -t evidenceai-grafana:combined-m123 infra/monitoring/grafana-rebuild
# exit 0
```

Core build log shows both zero-fuzz patch dry-run and actual application to
`go.mod` and `go.sum`, followed by assertions of resolved kin-openapi 0.149.0 /
jsonschema 6.0.3, then actual compilation with Go 1.27.2. Build flags, module versions,
compiler and checksums were read back using
`docker run --rm --network none --entrypoint cat evidenceai-grafana:experimental-m123 /usr/share/grafana/evidenceai-build.txt`.
Actual executable checksum was separately obtained with `--entrypoint sha256sum`.
Full provenance and build output are retained. Source tag/commit API metadata
and the HTTP422 patched-vendor-source response distinguish our traceable source
from unverified equivalence with the vendor's patched binary. Recorded labels are
not claimed to be signed vendor provenance.

For selected and core images, actual regular-file hashes were collected with:
`docker run --rm --network none --entrypoint sh IMAGE -c 'find PATH -type f -exec sha256sum {} + | sort'`,
where PATH was `/usr/share/grafana/public` or
`/usr/share/grafana/data/plugins-bundled`. The 11,864 frontend and 686 plugin files
match exactly. Raw hash manifests stay under runtime; summary hashes are retained
in [asset-parity.json](evidence/m123/asset-parity.json).

For all thirteen plugin IDs, current releases were retrieved with
`curl --fail --silent --show-error --max-time 30 https://grafana.com/api/plugins/ID/versions`.
The Cloud Monitoring 12.6.3 ARM64 ZIP was downloaded via its recorded catalog URL,
SHA-256 verified, and built into plugin-only/combined candidates with complete
signed metadata retained. Actual new executable bytes match the verified ZIP;
all six high findings nevertheless remain. No unsigned-plugin flag or plugin
removal is used. Twelve blocking advisory records were refreshed through their
recorded vendor/Go URLs, without substituting lower vendor severity for scanner
severity. [Vendor evidence](evidence/m123/vendor-advisories.json) and
[catalog evidence](evidence/m123/plugin-catalog.json) record requests/results.

```sh
python3 docs/evidence/m123/generate_inventory.py
# exit 0: all eight selected images and seven experiments match archives/live layers
```

The normalized inventory includes all severities, binary/layer/functional scope,
fix versions, original vendor URLs and verification status. None is automatically
marked false positive based on unproven reachability.

## Monitoring, transitions and staging

```sh
EVIDENCEAI_ACCEPTANCE=1 EVIDENCEAI_EVIDENCE_TAG=m123 EVIDENCEAI_GRAFANA_TRANSITION_IMAGE=evidenceai-grafana:experimental-m123 python3 infra/scripts/smoke.py
# exit 0: selected -> restart -> custom-core upgrade -> selected rollback; load/recovery
EVIDENCEAI_EVIDENCE_TAG=m123-signed EVIDENCEAI_GRAFANA_IMAGE=evidenceai-grafana:combined-m123 python3 infra/scripts/smoke.py
# exit 0: combined core/official signed plugin; functional monitoring and basic recovery
```

Both fixtures use unique projects, bounded tmpfs databases and synthetic bind
storage/secrets, with loopback HTTPS and a verified private CA. No existing
Grafana, PostgreSQL or document volume is reused. The first fixture retains its
own Grafana SQLite data across transitions, proving persistence of a separately
created nonprovisioned synthetic dashboard (title/version 1), not merely loading
provisioning again. Every transition verifies health, admin auth, anonymous denial,
no signup, provisioning, all thirteen valid plugin signatures, datasource health
and two actual Prometheus `up` results through Grafana. Recorded server commits
prove the upgrade and return. Initial graceful Grafana stop exits 0/no OOM.

The combined image reports Cloud Monitoring **12.6.3**, all thirteen signatures
valid, healthy datasource and successful actual Prometheus query. Other external
datasource queries, Cloud Monitoring provider credentials, long soak, cross-version
Grafana downgrade and hosted rollout/rollback remain NOT VERIFIED. The older
upstream branches were security-rejected and received no full operational signoff.

Docker inspection verifies no published Grafana port, one internal monitoring
network and healthy status. Protected API/worker metrics remain internally
accessible; `/metrics`, `/grafana/api/health` and private ops metrics are denied
through the loopback TLS proxy. HTTP redirect, HSTS, readiness, Secure cookies,
CSRF, private upload/download, worker processing and fake/mock RAG checks pass.
Generated fixture passwords enter the checker via stdin only.

The first fixture's Locust 2.43.1 run used unchanged five-user/30-second thresholds:
**334 requests, 0 failures, 11.351 requests/s, p50 8ms/p95 31ms/p99 87ms**.
Queue drain/no failed jobs, minimum sample size and latency/error criteria pass.
Competing core builds and upstream scans completed before this bounded load;
subsequent Cloud Monitoring builds occurred after it. Resource/DB samples and
final counts are retained in [load.json](evidence/m123/load.json).

Encrypted recovery restored **23 documents/originals**, checksums, schema head and
pgvector 0.8.7. Backup 0.057s, restore 0.092s; restored-app recovery **45.690s**,
last acknowledged write to backup completion 1.147s. Existing session, fresh login,
original and pending-document downloads and queued work recovered. Zero lost
acknowledged synthetic writes with writers quiesced. Nonempty restore target and
tampered ciphertext correctly fail. API exit143 (SIGTERM), worker/proxy exit0;
no OOM/exit137. The combined fixture additionally passed its smaller one-document
basic encrypted restore. These are same-host synthetic results, not production
capacity/RTO/RPO or offsite restoration receipts.

## CI/CD, data integrity and final gate

```sh
docker run --rm --network none -v /Users/redmug/EvidenceAI/.github/workflows:/work:ro -w /work rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 -color ci.yml deploy.yml
# exit 0
python3 infra/scripts/release_manifest.py --output infra/runtime/m123/manifest.json
# expected exit 1: clean committed source required; committing was prohibited
python3 infra/scripts/verify_release.py docs/evidence/m123/release-result.json
# exit 1 / BLOCKED
```

Deployment/scanner/release gate source, workflows and production image pin remain
unchanged. Local guard tests pass; actual hosted branch protection, no-self-approval
policy, exact-SHA CI and SSH execution remain NOT VERIFIED. No workflow dispatch
was performed. The failed supporting-image gate still blocks CI success.

Private before/after snapshot commands were
`PYTHONPATH=apps/api apps/api/.venv/bin/python /tmp/m123_snapshot.py before` and
`... /tmp/m123_snapshot.py after`. All sixteen existing public tables' counts and
deterministically ordered full-row hashes match; revision remains `91e2b6d8c410`.
[Aggregate evidence](evidence/m123/data-preservation.json) publishes no original
rows/customer file contents. No state was changed to force a pass. Development
Compose and existing migration files remain unchanged. Final diff and checksum
consistency checks are retained.

**Hosted SMTP delivery, public TLS/ingress/staging, hosted CI/CD and independent
backup/restore: NOT VERIFIED.** [Concrete procedures](hosted-staging-acceptance.md)
cover approval, controlled recipients, TLS validation, exact-SHA gates, offsite
key/restore acceptance and controlled rollback. No public deployment, DNS change,
production credential access, internet email, data reset, commit or push occurred.
The selected image's 61 high findings independently keep production BLOCKED.
