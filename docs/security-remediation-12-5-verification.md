# Security Remediation 12.5 — verification record

Baseline `932f75f`, initially clean. Date: 2026-10-20 Asia/Dubai.
**FAIL / production BLOCKED.** Run from `/Users/redmug/EvidenceAI` unless a working
directory is specified. Full image reports/archives, verbose browser logs and raw
vendor downloads are retained in ignored `infra/runtime/m125/`. Published
aggregates and command exits are in [m125 evidence](evidence/m125/commands.json).
No passwords, provider credentials, email proofs or private row values are needed
to reproduce these checks. Use fresh evidence directories/tags for a new run;
archived helper scripts embed `m125` paths and must not overwrite preserved logs.

## Executed build and image scans

```sh
python3 infra/scripts/scan_images.py --tag m121 --support-only --directory infra/runtime/m125/support
# exit 1: Grafana 61 HIGH / 0 CRITICAL / 0 secrets; three support images clean
python3 infra/scripts/scan_images.py --tag m121 --directory infra/runtime/m125/application
# exit 0: four application images clean at HIGH/CRITICAL/secret policy
python3 docs/evidence/m125/scan_candidate.py --name upstream-124 --reference grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185
# exit 1: five HIGH / 0 CRITICAL / 0 secrets

docker build --progress=plain --target candidate -f infra/monitoring/grafana-rebuild/125.Dockerfile -t evidenceai-grafana:kin-m125 infra/monitoring/grafana-rebuild
# exit 0, 42.715s; includes actual go list -deps with the OSS build tags
docker build --progress=plain --target tempo-v3-probe -f infra/monitoring/grafana-rebuild/125.Dockerfile infra/monitoring/grafana-rebuild
# exit 1, 15.056s wrapper time; Go proxy rejects v3 major-version module path
python3 docs/evidence/m125/scan_candidate.py --name kin --reference evidenceai-grafana:kin-m125
# exit 1: two HIGH / 0 CRITICAL / 0 secrets
python3 docs/evidence/m125/generate_inventory.py
# exit 0; archive config hashes and layer identities match live images/scans
```

Trivy 0.76.0 is pinned to
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
Full all-severity scans are used with vulnerability and secret scanning, without
ignores or VEX. Actual published intelligence `UpdatedAt` is
`2026-10-19T19:08:34.442427859Z`; fresh cache download timestamp is
`2026-10-19T21:50:47.979035426Z`. The scanner checks published intelligence;
an unchanged publication time is not represented as a newly published database.
Image archive and report checksums, platform, local/config IDs and normalized
findings are in [inventory](security-remediation-12-5-inventory.json).
Scanner report generation succeeds but the strict policy exits 1 for all failing
Grafana images. Candidate promotion remains false.

Fresh verified-HTTPS curl argument arrays/exits for official branch/latest Tempo
and Grafana releases/advisories are in [vendor commands](evidence/m125/vendor-commands.json).
Raw large downloads were moved intact into ignored runtime storage; their original
download path, retained path and SHA256 are explicitly recorded in
[download inventory](evidence/m125/raw-vendor-downloads.json). Metadata shows no
newer released 12.4 image. No independent publisher-signature verification was
executed; `cosign` is unavailable and an applicable trusted signer policy was not
established. This remains NOT VERIFIED.

## Regression and isolation commands

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125 -- python3 docs/evidence/m125/run_suite.py
# initial fixture readiness timeout: exit 1, owned container removed
# corrected tmpfs ownership: wrapper exit 0, but child test failures below;
# this inherited helper's exit propagation was then corrected
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/backend-retry -- python3 docs/evidence/m125/run_regressions.py backend
# exit 0: 660 backend tests at this stage; final 662 rerun is recorded below
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/browser-retry -- python3 docs/evidence/m125/run_browser.py
# exit 0: all 18 browser cases pass
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/isolation-final -- python3 docs/evidence/m125/run_isolation_checks.py
# exit 0: seven cases at this stage; final nine-case rerun is recorded below
```

Child commands and observed results:

| Working directory | Command | Final observed result |
| --- | --- | --- |
|`apps/api` |`.venv/bin/python -m pytest -q --junitxml=/Users/redmug/EvidenceAI/docs/evidence/m125/backend.xml` |PASS: 662 tests, no failures/errors/skips |
|`apps/api` |`.venv/bin/python -m alembic current` |PASS: `91e2b6d8c410 (head)` in disposable migrated DB |
|`apps/api` |`.venv/bin/python -m alembic check` |PASS: no new upgrade operations |
|`apps/api` |`.venv/bin/python -m pip check` |PASS |
|`apps/web` |`npm test` |PASS: 53 tests |
|`apps/web` |`npm run lint`; `npx tsc --noEmit`; `npm run build` (separate commands) |PASS: each exit 0 |
|`apps/web` |`npm run test:e2e` |PASS on complete rerun: 18; six each Chromium/Firefox/WebKit |
|`apps/api` |`/tmp/evidenceai-m11-audit-venv/bin/python -m pip_audit -r requirements.txt --format json` |PASS: 44 dependencies, no reported advisories |
|`apps/web` |`npm audit --omit=dev --json` |PASS: zero vulnerabilities |
|`apps/web` |`npm audit --json` |FAIL: five HIGH development lint-chain nodes, exit 1 |
|repo root |Pinned actionlint Docker invocation in `audits-commands.json` |PASS: exit 0 |

Browser binaries use `PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m12-browsers`.
No test assertion, retry setting or timeout was weakened. The first backend run
has 658 passes, one failure and one fixture error in **new** tests: wrong expected
name length and missing fixture import. Both were corrected and the entire backend
suite rerun. Its initial XML/commands are retained. The first browser run has17
passes and one Chromium login API-connection failure. The original trace/error
context remains in ignored `browser-initial-artifacts`; final complete rerun passes
without product changes. Root cause of that transient connection failure is NOT
VERIFIED. [Failure history](evidence/m125/initial-failures.json).

Both entry points also fail closed without `EVIDENCEAI_TEST_DATABASE_URL`:
pytest `--collect-only -q` exits 4; `e2e/server.py` exits 1. No application engine is
constructed before refusal. [Negative guards](evidence/m125/fail-closed.json).
Final isolation cleanup uses a label-verified owned container, observes no scratch
schemas and no public fixture users/intents/limiter rows, then removes it. The
initial suite wrapper's zero exit is explicitly **not** evidence its child tests
passed; the new helper now propagates unexpected exits.

Development preservation command:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --compare /tmp/evidenceai-m125-before.json --report docs/evidence/m125/data-preservation.json
# exit 0: 16 whole table hashes/counts, revision and private storage match
python3 docs/evidence/m125/verify_historical.py
# exit 0: historical directory retained; four normalized historical mismatches
# plus three intentional current documentation updates; originals archived separately
```

The private before-snapshot was captured before tests using the retained private
`/tmp/m125_snapshot.py before` helper (read-only development DB/storage). The new
reusable `preservation.py --snapshot /tmp/NEW_PRIVATE_PATH` supports future runs
and refuses overwrite. The current comparison cannot erase historical additions
or restore the four original normalized log byte streams. Initial review correctly found four normalized-path mismatches. Subsequent
read-only recovery located all four original streams; new gzip archives match the
unchanged original manifest. Historical normalized files/audit remain unchanged.
See `historical-review-initial.json` and `historical-recovery.json` for the explicit
before/recovery sequence. Complete custody timestamps remain NOT VERIFIED.
Read-only database/correlation methods and limitations are in the
[investigation](database-integrity-investigation.md).

## Local staging, monitoring and encrypted recovery

```sh
EVIDENCEAI_ACCEPTANCE=1 EVIDENCEAI_EVIDENCE_TAG=m125 EVIDENCEAI_GRAFANA_IMAGE=grafana/grafana@sha256:41bbc1b5e04416f81891806076db2a2ff60a5d4da5f78d36a88b033a8c199185 EVIDENCEAI_GRAFANA_TRANSITION_IMAGE=evidenceai-grafana:kin-m125 python3 infra/scripts/smoke.py
# exit 0; stdout/stderr retained at infra/runtime/m125/staging.log
```

Unique project `evidenceai-staging-smoke15d413a897` uses generated synthetic data,
private-CA local TLS, temporary storage and a disposable DB. Production Compose is
validated, never started. Authentication/CSRF/private storage/workers, mock RAG,
real private-fixture SMTP transport and internal monitoring isolation pass.
Dashboard version/state persists through restart, custom upgrade and rollback;
13 native plugin IDs/trust and actual Prometheus queries pass at each step. No
published Grafana port or public monitoring route is allowed. The candidate stays
outside production configuration despite these functional passes.

Five users / 30 seconds: 341 requests, zero failures, 11.461requests/s, p50 8 ms,
p95 26 ms, p99 56 ms; queue drained 1.35seconds. Thresholds are unchanged. Encrypted
backup 0.066seconds, verification 0.094seconds; 24 documents/originals, pgvector 0.8.7,
revision 91e2b6d8c410. Restored application operation/session/fresh login/downloads/
pending work passes at 45.985seconds; last acknowledged write-to-backup 1.272seconds,
zero synthetic acknowledged writes lost with writers quiesced. Nonempty-target
and tampered-ciphertext restores are refused. No OOM or exit 137; graceful shutdown
and owned-fixture cleanup pass. [Full sanitized result](evidence/m125/staging.json).
Production rollback to an accepted predecessor remains NOT VERIFIED.

## Release gates and scope

```sh
python3 infra/scripts/release_manifest.py --output infra/runtime/m125/manifest.json
# expected exit 1: uncommitted source cannot be packaged
python3 infra/scripts/verify_release.py docs/evidence/m125/release-result.json
# exit 1: BLOCKED
```

Scanner policy, deployment guards, formal release decision code, production image
pin, migrations and customer-facing services/routes/frontend remain unchanged.
Offline evaluator functions now share the disposable-database guard. CI changes only
its disposable DB configuration; actionlint and existing deployment tests pass.
Actual hosted CI checks, branch protections and deployment remain NOT VERIFIED.
Functional test success does not override failed image scans, unresolved historical
attribution or unverified historical custody.

## Hosted acceptance procedure

All rows below remain **NOT VERIFIED**. Use the existing
[hosted runbook](hosted-staging-acceptance.md), with explicit infrastructure and
controlled-recipient authorization before execution. This task does not authorize
DNS changes, purchases, hosted deployment, credential access or live email.

| Area / owner | Procedure and required redacted evidence |
| --- | --- |
|Real SMTP / mail and identity owner |Use approved provider/domain/mailboxes; operator supplies least-privilege secret outside Git. Validate implicit TLS465 with hostname/CA checks. Submit generic202 request over hosted HTTPS, verify pre-proof login denial; retain provider receipt **and actual inbox arrival**, UTC latency and SPF/DKIM/DMARC results. Test browser binding, expiration, single-use/replay, duplicate protection, CSRF/rate limits. Never retain URL fragment/token, password, recipient identity or auth headers. Revoke test credential afterward. |
|TLS/DNS/ingress / infrastructure owner |After separate authorization, retain DNS resolution and ACME issuance evidence for the approved host. Validate public chain/hostname/renewal, HTTP→HTTPS, HSTS, security headers and proxy routing. Prove readiness through ingress and Next.js↔FastAPI connectivity; keep monitoring/DB/storage private. Private-CA local success is insufficient. |
|Hosted staging / SRE and QA |Deploy only reviewed immutable artifacts after security blockers clear. Verify Alembic/pgvector, least-privilege DB, registration/mail, worker extraction/embedding jobs, private uploads/download authorization, mocked or separately approved AI flow, monitoring/dashboard targets, restart and isolated external access denials. Retain exact source/artifact IDs and timestamped receipts. |
|Hosted CI/CD / repository administrator |For the final committed SHA, retain real workflow URLs/conclusions, mandatory scan/audit results, protected environment reviewer and branch-protection evidence, least-privilege deployment/SSH host verification and concurrency/rollback safeguards. Syntax validation and local gate rejection are insufficient. Do not bypass failing checks. |
|Offsite recovery / backup and key custodians |Copy encrypted synthetic staging backup to an approved independent host/storage account. Separate key custody/escrow; restore into an empty owned target; verify ciphertext hashes, schema/pgvector, originals/permissions, authenticated app and worker continuation. Measure real RTO/RPO with acknowledged writes. Reject corruption/nonempty targets; preserve live data. Retain redacted independent-host and key-access receipts. |
|Controlled rollout/rollback / release authority |Obtain an accepted predecessor and schema compatibility review. On authorized staging perform guarded application rollback/readiness checks while preserving DB/originals; no automatic schema downgrade or volume overwrite. Demonstrate return to the selected approved release. No accepted production predecessor currently exists. |

Each operator receipt must include scope, exact SHA/digests, UTC times, command,
exit/result, owner/reviewer and redacted evidence hash. Mark FAIL on observed failure,
NOT VERIFIED if unexecuted, and PASS only for the precise executed scope. Current
local SMTP settings are disabled with no host/credential configured; no real
production delivery receipt or hosted deployment is claimed.

## Final shared-guard integration checks

A final architecture review extended the same explicit URL policy to offline
retrieval/RAG evaluation functions. The policy moved to
`apps/api/app/db/disposable_database.py`; the infrastructure module re-exports it.
Evaluator settings and cached-engine URLs must both equal the explicit disposable
URL before creating schemas. Nine new guard cases are included in the final 662-test
backend pass. The prior 660-test pass/XML remains preserved separately.

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/backend-final -- python3 docs/evidence/m125/run_regressions.py backend
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/evaluation-final -- python3 docs/evidence/m125/run_evaluation.py
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/browser-final -- python3 docs/evidence/m125/run_browser_final.py
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/isolation-guard-final -- python3 docs/evidence/m125/run_isolation_checks_final.py
```

The evaluator child runs `.venv/bin/python -m app.evaluate --repeat 3` from
`apps/api`, writing only synthetic reports into the ignored runtime directory.
Final exits and cleanup results are recorded alongside these commands. These
local structural/mock evaluation checks do not verify hosted model semantics.

## Original-byte recovery and custody

The original four streams were recovered read-only from
`infra/runtime/m124/{build,lint,unit}.log` and
`/usr/share/grafana/evidenceai-build.txt` in the old immutable
`evidenceai-grafana:kin-m124` image. All four match their original manifest
SHA256 exactly. New `m124-original-*.gz` files retain them without editor whitespace
conversion. A reconstructed `m124-original-evidence.tar.gz` additionally contains
all 69 original manifest file contents, using Git932f75f versions for the other
files; every extracted content hash was verified. Archive metadata is newly
generated and not claimed historical. The original m124 manifest/audit/files
remain unchanged.

The current original-manifest comparison has seven differences: four normalized
paths plus release acceptance/checklist/rebuild README intentionally updated in
12.5. Their old bytes are verified from Git and included in the recovered archive.
No historical checksum was silently replaced. Original content recovery is PASS;
complete historical acquisition/custody timestamps remain NOT VERIFIED.

## Final development delta — supersedes the earlier equality PASS

After all final guard/evaluator/browser checks, the final read-only preservation
command (same before-snapshot, output `data-preservation-final.json`) returned
**exit1 / FAIL**: auth_rate_limits12→13. All other 15 table hashes/counts, revision
and private-storage bytes/metadata match. An ordered-subset hash check proves all
12 pre-existing limiter rows remain identical. The one new row has a 22:15 UTC
bucket, one attempt and a source-defined loopback login action hash; no key or
private identity is emitted. Actual insertion time/writer are NOT VERIFIED.

The earlier passing comparison remains published; it is not the final result.
No development role/configuration was changed, process killed or record removed
to force a pass. Owned test database cleanup is independently PASS and cannot alone
identify this writer. Both historical 11 additions and the new row remain preserved.
See `database-final-delta.json`; read-only investigator source is included in the
evidence directory. Release remains BLOCKED.

The final consistency audit also caught accidental pytest discovery of the first
utility filename (`test_safety.py`): its URL-returning helper appeared as a663rd
case and produced a ReturnNotNone warning. The utility and function were renamed
(`disposable_database.py`), and the complete meaningful662-case suite was rerun
in `backend-verified`. The663-case XML/command receipt is retained separately.
This was collection hygiene, not deletion of an existing test.

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m125/backend-verified -- python3 docs/evidence/m125/run_regressions.py backend
```

`original-log-bytes.tar.gz` additionally retains exact new log/provenance streams
without modifying their readable originals; its separate byte index prevents an
editor's whitespace conversion from destroying the only recoverable copy.
